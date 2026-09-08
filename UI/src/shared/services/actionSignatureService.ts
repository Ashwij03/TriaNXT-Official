/**
 * Action Signature Service — 21 CFR Part 11 e-signature gate.
 * ============================================================
 *
 * Every mutating action on documents / folders / subject files must be
 * authorized by the acting user typing their printed name, captured with a
 * timestamp as a SignaturePayload BEFORE the mutation commits (Task 1).
 *
 * This module is the shared backing service:
 *   * `openSignature({ ... })` shows the one ESignatureModal instance
 *     mounted in App.tsx and resolves only after a valid signature.
 *   * `signEntity(...)` records an append-only audit trail of every signed
 *     action in localStorage (same pattern as folderService.ts /
 *     fileService.ts audit stores) and, in API mode, best-effort syncs to
 *     the backend audit surface when one exists (fail-soft, never throws).
 *   * `signatureSummary(...)` produces the human-readable remarks string
 *     embedded in records' `remarks` fields (e.g. fileService.ts).
 */

import {
  getUserDisplayName,
  getCurrentUser,
  getEffectiveUser,
} from "./roleService";
import { isApiEnabled, api } from "./api/client";

/** Captured electronic signature (typed name + stamp + timestamp + meaning). */
export interface SignaturePayload {
  printedName: string;
  signatureStamp: string;
  signedAt: string; // ISO timestamp
  /** Why the user is signing (approval / review / authorship / verification). */
  meaning?: string;
  signerIdentity?: SignerIdentity;
}

/** Who is signing (resolved from the signed-in session). */
export interface SignerIdentity {
  displayName: string;
  email: string;
  role: string;
  userId: string;
}

/** Request consumed by the ESignatureModal (set via openSignature). */
export interface SignatureRequest {
  /** Audit action key, e.g. "document:delete", "folder:create". */
  actionKey?: string;
  entityType?: string;
  entityName?: string;
  meta?: Record<string, any>;
  title: string;
  description: string;
  /** When set (e.g. "DELETE") the user must type this exact word before
   *  the Sign button enables — destructive actions combine the are-you-sure
   *  and sign steps into ONE modal. */
  requireTypedConfirmation?: string;
  /** Signature meaning taxonomy (defaults via defaultMeaningForAction). */
  meaning?: string;
  /** Selectable meanings for the modal picker (defaults to SIGNATURE_MEANINGS). */
  meanings?: Array<{ value: string; label: string; description?: string }>;
  onSigned: (signature: SignaturePayload) => void | Promise<void>;
  onCancel?: () => void;
}

/** Append-only localStorage audit trail of signed actions. */
const SIGNATURES_STORAGE_KEY = "trianxtActionSignatures";

/* ----------------------------------------------------------------------
   Imperative modal registry — components call openSignature() and the
   single <ESignatureModal /> rendered in App.tsx picks the request up.
---------------------------------------------------------------------- */

let activeRequest: SignatureRequest | null = null;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

export function openSignature(request: SignatureRequest): void {
  activeRequest = request;
  notify();
}

export function closeSignature(): void {
  activeRequest = null;
  notify();
}

export function getSignatureRequest(): SignatureRequest | null {
  return activeRequest;
}

export function subscribeSignatureRequest(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Current user's display name, used to default the printed-name field. */
export function getDefaultSigningName(): string {
  try {
    return getUserDisplayName(getCurrentUser()) || "";
  } catch {
    return "";
  }
}

/* ----------------------------------------------------------------------
   Audit recording
---------------------------------------------------------------------- */

/** Read the append-only signed-actions trail (mirrors folderService reads). */
export function getSignedActions(): any[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(SIGNATURES_STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/**
 * Record that `signature` authorized `actionKey` against entityType /
 * entityName, plus any extra meta. Persisted to localStorage (append-only)
 * and, in API mode, best-effort synced to the backend audit surface —
 * fail-soft: an unreachable backend never throws to the UI.
 */
export async function signEntity(
  actionKey: string,
  entityType: string,
  entityName: string,
  signature: SignaturePayload,
  meta: Record<string, any> = {},
): Promise<void> {
  const entry = {
    actionKey,
    entityType,
    entityName,
    ...meta,
    signature: { ...signature },
    recordedAt: new Date().toISOString(),
  };

  try {
    if (typeof window !== "undefined") {
      const existing = getSignedActions();
      localStorage.setItem(
        SIGNATURES_STORAGE_KEY,
        JSON.stringify([...existing, entry]),
      );
      window.dispatchEvent(
        new CustomEvent("trianxt-signature-recorded", { detail: entry }),
      );
    }
  } catch {
    // Storage unavailable — the signing UI already validated; audit is best-effort.
  }

  // Fail-soft backend mirror: POST the signature record (now including the
  // SHA-256 stamp + meaning) to /api/audit/signatures — persisted by the
  // backend into the ctms_electronic_signature ledger. Never throws.
  if (isApiEnabled()) {
    try {
      await api.post("/api/audit/signatures", {
        actionKey,
        entityType,
        entityName,
        meta,
        meaning: signature.meaning || defaultMeaningForAction(actionKey),
        signature: {
          printedName: signature.printedName,
          signatureStamp: signature.signatureStamp,
          signedAt: signature.signedAt,
          meaning: signature.meaning || defaultMeaningForAction(actionKey),
        },
      });
    } catch {
      // Backend unreachable / not authenticated — local trail still stands.
    }
  }
}

/**
 * Human-readable audit remark embedded into record `remarks` fields, e.g.
 *   signatureSummary(sig, "Uploaded") -> "Uploaded by Jane Doe on 2026-09-05T10:00:00Z"
 */
export function signatureSummary(
  signature: SignaturePayload,
  verb: string,
): string {
  const name = signature?.printedName || "Unknown user";
  const at = signature?.signedAt || new Date().toISOString();
  return `${verb} by ${name} on ${at}`;
}

/* ----------------------------------------------------------------------
   Signature meaning taxonomy (21 CFR Part 11 — WHY the user is signing)
---------------------------------------------------------------------- */

/** Canonical signature meanings. Each captures the signer's intent so the
 *  audit trail is defensible: approval vs review vs authorship vs
 *  verification are legally distinct acts. */
export const SIGNATURE_MEANINGS = [
  {
    value: "approval",
    label: "Approval",
    description: "I approve this action for the stated purpose.",
  },
  {
    value: "review",
    label: "Review",
    description: "I have reviewed the change and its contents.",
  },
  {
    value: "authorship",
    label: "Authorship",
    description: "I authored / take ownership of this change.",
  },
  {
    value: "verification",
    label: "Verification",
    description: "I verified this change's integrity and authenticity.",
  },
] as const;

export const SIGNATURE_MEANING_LABELS: Record<string, string> =
  Object.fromEntries(
    SIGNATURE_MEANINGS.map((m) => [m.value, m.label]),
  );

export function signatureMeaningLabel(meaning?: string): string {
  return (
    (meaning && SIGNATURE_MEANING_LABELS[meaning]) ||
    meaning ||
    "Approval"
  );
}

/** Sensible default meaning per action kind. */
export function defaultMeaningForAction(actionKey?: string): string {
  const key = String(actionKey || "").toLowerCase();
  if (/(create|upload|new|import|duplicate)/.test(key)) {
    return "authorship";
  }
  if (/(delete|remove|archive|expire|reject)/.test(key)) {
    return "approval";
  }
  if (/(edit|save|rename|replace|update|move|approve|sign)/.test(key)) {
    return "review";
  }
  return "approval";
}

/** Button label per action kind, e.g. "Upload & Sign", "Delete & Sign". */
export function confirmLabelForAction(actionKey?: string): string {
  const key = String(actionKey || "").toLowerCase();
  const verb =
    key === ""
      ? "Sign"
      : /(create|upload|import)/.test(key)
        ? "Upload"
        : /(delete|remove)/.test(key)
          ? "Delete"
          : /(rename|edit|update|save|replace|move)/.test(key)
            ? "Save"
            : "Sign";
  return `${verb} & Sign`;
}

/* ----------------------------------------------------------------------
   Cryptographic integrity stamp (SHA-256 over a canonical payload)
---------------------------------------------------------------------- */

export const SIGNATURE_STAMP_ALGORITHM = "SHA-256";

/** Recursively sort object keys so the same logical payload always
 *  canonicalises the same way (contract with the backend's
 *  _canonical_json in apps/eisf/services.py). */
export function canonicalJson(payload: any): string {
  const sorted = (value: any): any => {
    if (Array.isArray(value)) {
      return value.map(sorted);
    }
    if (value && typeof value === "object") {
      return Object.keys(value)
        .sort()
        .reduce((acc: Record<string, any>, key) => {
          acc[key] = sorted(value[key]);
          return acc;
        }, {});
    }
    return value;
  };
  return JSON.stringify(sorted(payload));
}

/** SHA-256 hex digest via the browser's native crypto.subtle. */
export async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest(SIGNATURE_STAMP_ALGORITHM, data);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

/** Build the tamper-evident stamp over the canonical signing payload. */
export async function buildActionStamp({
  actionKey,
  entityType,
  entityName,
  meaning,
  signerIdentity,
  timestamp,
  meta,
}: {
  actionKey: string;
  entityType: string;
  entityName: string;
  meaning: string;
  signerIdentity: SignerIdentity;
  timestamp: string;
  meta?: Record<string, any>;
}): Promise<string> {
  const payload = {
    actionKey,
    entityType,
    entityName,
    meaning,
    signerIdentity,
    timestamp,
    meta: meta || {},
  };
  return sha256Hex(canonicalJson(payload));
}

/** Resolve who is signing from the effective session. */
export function getSignerIdentity(): SignerIdentity {
  const effective = getEffectiveUser(getCurrentUser());
  return {
    displayName: effective?.displayName || getUserDisplayName(effective) || "",
    email: effective?.email || "",
    role: effective?.role || "",
    userId: String(effective?.id ?? ""),
  };
}

/** Main entry point: resolve identity + build the stamp + return a complete
 *  signature record. The backend recomputes the same stamp over the same
 *  canonical payload (apps/eisf/services.py build_signature_stamp) so a
 *  submitted stamp can be cryptographically verified, not blindly trusted. */
export async function createActionSignature({
  actionKey = "sign",
  entityType = "",
  entityName = "",
  meaning,
  signerIdentity,
  timestamp,
  meta,
  printedName,
}: {
  actionKey?: string;
  entityType?: string;
  entityName?: string;
  meaning?: string;
  signerIdentity?: SignerIdentity;
  timestamp?: string;
  meta?: Record<string, any>;
  printedName: string;
}): Promise<SignaturePayload> {
  const resolvedMeaning = meaning || defaultMeaningForAction(actionKey);
  const identity = signerIdentity || getSignerIdentity();
  const signedAt = timestamp || new Date().toISOString();
  const signatureStamp = await buildActionStamp({
    actionKey,
    entityType,
    entityName,
    meaning: resolvedMeaning,
    signerIdentity: identity,
    timestamp: signedAt,
    meta,
  });
  return {
    printedName,
    meaning: resolvedMeaning,
    signatureStamp,
    signedAt,
    signerIdentity: identity,
  };
}

/* ----------------------------------------------------------------------
   Display helpers + record embedding
---------------------------------------------------------------------- */

/** Short display form of the SHA-256 stamp, e.g. "a1b2…c3d4". */
export function formatSignatureStamp(stamp?: string): string {
  const value = String(stamp || "");
  if (!value) return "—";
  if (value.length <= 16) return value;
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

/** Human-readable local time from an ISO timestamp. */
export function formatSignatureTime(iso?: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso);
  return date.toLocaleString();
}

/** Embed a signature onto an arbitrary record before persisting it. */
export function attachSignatureToRecord(record: any, signature: SignaturePayload): any {
  const signatures = Array.isArray(record?.signatures) ? [...record.signatures] : [];
  signatures.push({ ...signature });
  return {
    ...(record || {}),
    signatures,
    lastSignature: { ...signature },
  };
}

/* ----------------------------------------------------------------------
   Signature ledger (filterable, append-only)
---------------------------------------------------------------------- */

/** Filter the signed-actions trail by study/subject/document/etc. */
export function getSignatureLedgerEntries(scope: Record<string, any> = {}): any[] {
  const entries = getSignedActions();
  const keys = Object.keys(scope || {});
  if (keys.length === 0) return entries;
  return entries.filter((entry) =>
    keys.every((key) => String(entry?.[key] ?? "") === String(scope[key] ?? "")),
  );
}

/** Append a signature-ledger entry (records the same shape signEntity
 *  writes, including meaning + SHA-256 stamp). */
export function recordSignatureLedgerEntry(
  entry: Record<string, any>,
): void {
  try {
    if (typeof window === "undefined") return;
    const existing = getSignedActions();
    localStorage.setItem(
      SIGNATURES_STORAGE_KEY,
      JSON.stringify([
        ...existing,
        { ...entry, recordedAt: entry.recordedAt || new Date().toISOString() },
      ]),
    );
    window.dispatchEvent(
      new CustomEvent("trianxt-signature-recorded", { detail: entry }),
    );
  } catch {
    // Best-effort — the signing UI already validated.
  }
}

const ActionSignatureService = {
  openSignature,
  closeSignature,
  getSignatureRequest,
  subscribeSignatureRequest,
  getDefaultSigningName,
  signEntity,
  signatureSummary,
  getSignedActions,
  SIGNATURE_MEANINGS,
  SIGNATURE_MEANING_LABELS,
  signatureMeaningLabel,
  defaultMeaningForAction,
  confirmLabelForAction,
  SIGNATURE_STAMP_ALGORITHM,
  canonicalJson,
  sha256Hex,
  buildActionStamp,
  createActionSignature,
  getSignerIdentity,
  formatSignatureStamp,
  formatSignatureTime,
  attachSignatureToRecord,
  getSignatureLedgerEntries,
  recordSignatureLedgerEntry,
};

export default ActionSignatureService;