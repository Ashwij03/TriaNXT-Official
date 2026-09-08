/**
 * Signature Request Service — multi-signer signature workflows.
 * =============================================================
 *
 * Backs the Signature Requests workspace (shared/pages/signatures).
 * A signature request is one-or-more signers asked to sign a document;
 * the backend persists requests in the ctms_signature_requests /
 * ctms_signature_request_signers tables and appends each completed
 * signature to the ctms_electronic_signature ledger.
 *
 * Dual-mode (same pattern as every shared service):
 *   * API mode  — the FastAPI backend is the source of truth
 *     (GET/POST /api/signature-requests, POST .../{id}/sign);
 *   * offline   — requests are mirrored to localStorage so the workspace
 *     stays usable without a backend (signing records the stamped
 *     signature locally; it cannot be verified server-side until the
 *     backend is reachable).
 *
 * Every mutation is fail-soft: a backend error never throws to the UI —
 * the local mirror still stands and the error message is returned so the
 * page can surface it.
 */

import { isApiEnabled, api } from "./api/client";
import { getUsers } from "./adminService";
import { getCurrentUser } from "./roleService";

/** localStorage mirror of requests (used when the API is unreachable). */
const STORAGE_KEY = "trianxtSignatureRequests";
export const SIGNATURE_REQUESTS_EVENT = "trianxt-signature-requests-updated";

/** Request statuses the backend understands. */
export const SIGNATURE_REQUEST_STATUSES = {
  DRAFT: "DRAFT",
  SENT: "SENT",
  COMPLETED: "COMPLETED",
} as const;

/** Signer statuses the backend understands. */
export const SIGNER_STATUSES = {
  PENDING: "PENDING",
  SIGNED: "SIGNED",
} as const;

/* ----------------------------------------------------------------------
   Local mirror helpers
---------------------------------------------------------------------- */

function readLocalStore(): any[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocalStore(requests: any[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(requests));
    window.dispatchEvent(new CustomEvent(SIGNATURE_REQUESTS_EVENT));
  } catch {
    // Storage unavailable — best-effort mirror.
  }
}

function notifyChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(SIGNATURE_REQUESTS_EVENT));
}

/** Deterministic local id for offline-created requests (no backend row yet). */
function localRequestId() {
  return `local-${Date.now()}`;
}

/** Normalize a backend or local request payload to the UI shape. */
export function normalizeSignatureRequest(request: any = {}): any {
  const signers = Array.isArray(request?.signers)
    ? request.signers
    : request?.signerList || [];
  return {
    ...request,
    requestId:
      request.requestId ??
      request.id ??
      request.request_id ??
      localRequestId(),
    documentId: request.documentId ?? request.document_id ?? null,
    studyId: request.studyId ?? request.study_id ?? null,
    title: request.title || "Untitled signature request",
    status: String(request.status || SIGNATURE_REQUEST_STATUSES.DRAFT).toUpperCase(),
    requestedBy: request.requestedBy ?? request.requested_by ?? null,
    sentAt: request.sentAt ?? request.sent_at ?? null,
    expiresAt: request.expiresAt ?? request.expires_at ?? null,
    completedAt: request.completedAt ?? request.completed_at ?? null,
    createdAt: request.createdAt ?? request.created_at ?? null,
    signers: signers.map((signer: any) => normalizeSigner(signer)),
  };
}

/** Normalize a signer payload to the UI shape. */
export function normalizeSigner(signer: any = {}): any {
  return {
    ...signer,
    signerId: signer.signerId ?? signer.signer_id ?? null,
    requestId: signer.requestId ?? signer.request_id ?? null,
    userId: signer.userId ?? signer.user_id ?? null,
    signerName: signer.signerName ?? signer.signer_name ?? "Unknown signer",
    signerRole: signer.signerRole ?? signer.signer_role ?? "",
    status: String(signer.status || SIGNER_STATUSES.PENDING).toUpperCase(),
    meaning: signer.meaning ?? null,
    signedAt: signer.signedAt ?? signer.signed_at ?? null,
    verificationStatus:
      signer.verificationStatus ?? signer.verification_status ?? null,
  };
}

/* ----------------------------------------------------------------------
   Directory (signer picker source)
---------------------------------------------------------------------- */

/**
 * Directory users available as signers. In API mode the backend
 * accounts_user directory is the source of truth (matched by email with
 * the localStorage directory as a fallback); offline, the localStorage
 * users store is used. Only approved/active users are returned.
 */
export async function fetchDirectoryUsers(transport: any = api): Promise<any[]> {
  if (isApiEnabled()) {
    try {
      const res: any = await transport.get("/api/accounts/users/?page_size=100");
      const results = (res && (res.results || res)) || [];
      if (Array.isArray(results) && results.length > 0) {
        return results
          .filter((user: any) => {
            const status = String(user?.account_status ?? user?.accountStatus ?? "").toLowerCase();
            return !status || status === "active";
          })
          .map((user: any) => ({
            id: user.id,
            userId: user.id,
            email: user.email || "",
            name:
              [user.first_name, user.last_name].filter(Boolean).join(" ") ||
              user.username ||
              user.name ||
              user.email,
            role: user.role || user.role_name || "",
          }));
      }
    } catch {
      // Backend unreachable — fall through to the local directory.
    }
  }
  return getUsers()
    .filter((user: any) => {
      const approval = String(user.approvalStatus || "").toLowerCase();
      const status = String(user.accountStatus || "").toLowerCase();
      return (
        (!approval || approval === "approved") &&
        (!status || status === "active")
      );
    })
    .map((user: any) => ({
      id: user.id,
      userId: user.id,
      email: user.email || "",
      name: user.name || user.username || user.email,
      role: user.role || "",
    }));
}

/** Current user as a directory entry (id, name, role). */
export function getCurrentUserEntry(): any {
  const user = getCurrentUser();
  return {
    id: user?.id ?? null,
    userId: user?.id ?? null,
    email: user?.email || "",
    name: user?.name || user?.username || user?.email || "",
    role: user?.role || "",
  };
}

/* ----------------------------------------------------------------------
   Requests
---------------------------------------------------------------------- */

/**
 * List signature requests, newest first. API mode reads the backend;
 * offline it reads the localStorage mirror.
 */
export async function getSignatureRequests(
  transport: any = api,
): Promise<any[]> {
  if (isApiEnabled()) {
    try {
      const res: any = await transport.get("/api/signature-requests");
      if (Array.isArray(res)) {
        return res.map(normalizeSignatureRequest);
      }
    } catch {
      // Backend unreachable — fall back to the local mirror.
    }
  }
  return readLocalStore().map(normalizeSignatureRequest);
}

/** One signature request by id (requestId, or local "local-…" id). */
export async function getSignatureRequest(
  requestId: string | number,
  transport: any = api,
): Promise<any | null> {
  const isLocal = String(requestId).startsWith("local-");
  if (isApiEnabled() && !isLocal) {
    try {
      const res: any = await transport.get(`/api/signature-requests/${requestId}`);
      if (res && res.requestId) {
        return normalizeSignatureRequest(res);
      }
    } catch {
      // Fall back to the local mirror.
    }
  }
  const found = readLocalStore().find(
    (entry) => String(entry.requestId ?? entry.id) === String(requestId),
  );
  return found ? normalizeSignatureRequest(found) : null;
}

/**
 * Create a signature request.
 *
 * @param input { documentId, studyId?, title?, signers: [{userId, signerName, signerRole?}], status? }
 * @returns { request, error? } — request is the created/normalized request;
 *          error is set when the backend rejected it (local mirror still stands).
 */
export async function createSignatureRequest(
  input: any,
  transport: any = api,
): Promise<{ request: any; error?: string }> {
  const status = String(
    input.status || SIGNATURE_REQUEST_STATUSES.DRAFT,
  ).toUpperCase();

  if (isApiEnabled()) {
    try {
      const res: any = await transport.post("/api/signature-requests", {
        documentId: input.documentId,
        studyId: input.studyId,
        title: input.title,
        status,
        signers: (input.signers || []).map((signer: any) => ({
          userId: signer.userId ?? signer.id,
          signerName: signer.signerName || signer.name || "",
          signerRole: signer.signerRole || signer.role || "",
        })),
      });
      if (res && res.requestId) {
        return { request: normalizeSignatureRequest(res) };
      }
      throw new Error("Backend returned no signature request.");
    } catch (err: any) {
      // The backend rejected the payload (e.g. missing documentId) — surface
      // the error rather than silently writing a broken local mirror.
      return { request: null, error: err?.message || "Could not create the signature request." };
    }
  }

  // Offline mirror: build the request locally so the workspace stays usable.
  const now = new Date().toISOString();
  const request = normalizeSignatureRequest({
    requestId: localRequestId(),
    documentId: input.documentId,
    studyId: input.studyId,
    title: input.title,
    status,
    requestedBy: getCurrentUser()?.id ?? null,
    sentAt: status === SIGNATURE_REQUEST_STATUSES.SENT ? now : null,
    createdAt: now,
    signers: (input.signers || []).map((signer: any) => ({
      userId: signer.userId ?? signer.id,
      signerName: signer.signerName || signer.name || "",
      signerRole: signer.signerRole || signer.role || "",
      status: SIGNER_STATUSES.PENDING,
    })),
  });
  writeLocalStore([request, ...readLocalStore()]);
  return { request };
}

/**
 * Sign a signature request as the current user. In API mode the backend
 * marks the user's signer row complete and appends an ESignature ledger
 * row; offline, the local mirror is updated with the stamped signature.
 *
 * @returns { request, error? }
 */
export async function signSignatureRequest(
  requestId: string | number,
  signature: any,
  transport: any = api,
): Promise<{ request: any; error?: string }> {
  const isLocal = String(requestId).startsWith("local-");
  const body = {
    meaning: signature?.meaning || "approval",
    signature: {
      printedName: signature?.printedName || "",
      signatureStamp: signature?.signatureStamp || "",
      signedAt: signature?.signedAt || new Date().toISOString(),
    },
  };

  if (isApiEnabled() && !isLocal) {
    try {
      const res: any = await transport.post(
        `/api/signature-requests/${requestId}/sign`,
        body,
      );
      if (res && res.requestId) {
        return { request: normalizeSignatureRequest(res) };
      }
      throw new Error("Backend returned no updated signature request.");
    } catch (err: any) {
      return {
        request: null,
        error:
          err?.message ||
          "The signature could not be recorded. You may not be a signer on this request.",
      };
    }
  }

  // Offline mirror: mark the current user's signer row signed.
  const all = readLocalStore();
  const index = all.findIndex(
    (entry) => String(entry.requestId ?? entry.id) === String(requestId),
  );
  if (index < 0) {
    return { request: null, error: "Signature request not found." };
  }
  const current = getCurrentUser();
  const userId = current?.id;
  const now = new Date().toISOString();
  const updated = {
    ...all[index],
    signers: (all[index].signers || []).map((signer: any) =>
      String(signer.userId ?? signer.id) === String(userId)
        ? {
            ...signer,
            status: SIGNER_STATUSES.SIGNED,
            meaning: signature?.meaning || "approval",
            signedAt: signature?.signedAt || now,
            verificationStatus: signature?.signatureStamp ? "verified" : "recorded",
          }
        : signer,
    ),
  };
  const allSigned = (updated.signers || []).every(
    (signer: any) => String(signer.status).toUpperCase() === SIGNER_STATUSES.SIGNED,
  );
  if (allSigned && updated.signers.length > 0) {
    updated.status = SIGNATURE_REQUEST_STATUSES.COMPLETED;
    updated.completedAt = now;
  }
  const next = [...all];
  next[index] = updated;
  writeLocalStore(next);
  return { request: normalizeSignatureRequest(updated) };
}

/* ----------------------------------------------------------------------
   UI helpers
---------------------------------------------------------------------- */

/** Is the current user a pending signer on this request? */
export function currentUserCanSign(request: any): boolean {
  const userId = getCurrentUser()?.id;
  if (userId === null || userId === undefined) return false;
  return (request?.signers || []).some(
    (signer: any) =>
      String(signer.userId) === String(userId) &&
      String(signer.status).toUpperCase() !== SIGNER_STATUSES.SIGNED,
  );
}

/** Status badge label for a request. */
export function requestStatusLabel(status?: string): string {
  switch (String(status || "").toUpperCase()) {
    case SIGNATURE_REQUEST_STATUSES.DRAFT:
      return "Draft";
    case SIGNATURE_REQUEST_STATUSES.SENT:
      return "Sent";
    case SIGNATURE_REQUEST_STATUSES.COMPLETED:
      return "Completed";
    default:
      return String(status || "Draft");
  }
}

/** Progress: "2 of 3 signed". */
export function signerProgress(request: any): string {
  const signers = request?.signers || [];
  const signed = signers.filter(
    (signer: any) => String(signer.status).toUpperCase() === SIGNER_STATUSES.SIGNED,
  ).length;
  return `${signed} of ${signers.length} signed`;
}

const SignatureRequestService = {
  SIGNATURE_REQUEST_STATUSES,
  SIGNER_STATUSES,
  SIGNATURE_REQUESTS_EVENT,
  normalizeSignatureRequest,
  normalizeSigner,
  fetchDirectoryUsers,
  getCurrentUserEntry,
  getSignatureRequests,
  getSignatureRequest,
  createSignatureRequest,
  signSignatureRequest,
  currentUserCanSign,
  requestStatusLabel,
  signerProgress,
};

export default SignatureRequestService;