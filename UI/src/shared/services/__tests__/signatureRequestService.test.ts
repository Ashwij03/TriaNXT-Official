/**
 * Unit tests for signatureRequestService (Signature Requests workspace).
 *
 * Covers: payload normalization (backend snake_case -> UI shape), pure
 * display helpers, the signer-can-sign check, API-mode create/sign/list
 * against a fake transport, and the offline localStorage mirror.
 */

import {
  SIGNATURE_REQUEST_STATUSES,
  createSignatureRequest,
  currentUserCanSign,
  fetchDirectoryUsers,
  getSignatureRequests,
  normalizeSignatureRequest,
  normalizeSigner,
  requestStatusLabel,
  signSignatureRequest,
  signerProgress,
} from "../signatureRequestService";
import { isApiEnabled } from "../api/client";
import { getUsers } from "../adminService";

vi.mock("../api/client", () => ({
  isApiEnabled: vi.fn(),
  api: {},
}));

vi.mock("../adminService", () => ({
  getUsers: vi.fn(),
}));

function makeBackendRequest(overrides: any = {}) {
  return normalizeSignatureRequest({
    requestId: 7,
    documentId: 101,
    studyId: 202,
    requestedBy: 1,
    title: "Approve ICF v2.0",
    status: "SENT",
    sentAt: "2026-09-01T10:00:00",
    createdAt: "2026-09-01T09:00:00",
    signers: [
      {
        signerId: 11,
        requestId: 7,
        userId: 5,
        signerName: "Jane Doe",
        signerRole: "PI",
        status: "PENDING",
        meaning: null,
        signedAt: null,
        verificationStatus: null,
      },
      {
        signerId: 12,
        requestId: 7,
        userId: 6,
        signerName: "John Smith",
        signerRole: "Sponsor",
        status: "SIGNED",
        meaning: "approval",
        signedAt: "2026-09-02T12:00:00",
        verificationStatus: "verified",
      },
    ],
    ...overrides,
  });
}

describe("normalization", () => {
  it("maps backend snake_case payloads to the UI shape", () => {
    const request = makeBackendRequest();
    expect(request.requestId).toBe(7);
    expect(request.documentId).toBe(101);
    expect(request.status).toBe("SENT");
    expect(request.signers).toHaveLength(2);
    expect(request.signers[0].status).toBe("PENDING");
    expect(request.signers[1].meaning).toBe("approval");
  });

  it("defaults missing fields safely", () => {
    const request = normalizeSignatureRequest({});
    expect(request.requestId).toBeDefined();
    expect(request.title).toBe("Untitled signature request");
    expect(request.status).toBe("DRAFT");
    expect(request.signers).toEqual([]);
  });

  it("keeps the local mirror shape intact", () => {
    const request = normalizeSignatureRequest({
      requestId: "local-123",
      title: "Local draft",
      status: "draft",
      signers: [{ signerName: "A", status: "pending" }],
    });
    expect(request.requestId).toBe("local-123");
    expect(request.status).toBe("DRAFT");
    expect(request.signers[0].status).toBe("PENDING");
  });

  it("normalizes a signer row", () => {
    const signer = normalizeSigner({
      signer_id: 9,
      user_id: 4,
      signer_name: "Sam",
      status: "signed",
      verification_status: "verified",
    });
    expect(signer.signerId).toBe(9);
    expect(signer.userId).toBe(4);
    expect(signer.signerName).toBe("Sam");
    expect(signer.status).toBe("SIGNED");
    expect(signer.verificationStatus).toBe("verified");
  });
});

describe("display helpers", () => {
  it("labels request statuses", () => {
    expect(requestStatusLabel("DRAFT")).toBe("Draft");
    expect(requestStatusLabel("sent")).toBe("Sent");
    expect(requestStatusLabel("COMPLETED")).toBe("Completed");
    expect(requestStatusLabel("")).toBe("Draft");
  });

  it("reports signer progress", () => {
    expect(signerProgress(makeBackendRequest())).toBe("1 of 2 signed");
    expect(signerProgress(normalizeSignatureRequest({}))).toBe("0 of 0 signed");
  });
});

describe("currentUserCanSign", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("is true only for a pending signer", () => {
    localStorage.setItem(
      "currentUser",
      JSON.stringify({ id: 5, name: "Jane Doe", role: "PI" }),
    );
    const request = makeBackendRequest();
    expect(currentUserCanSign(request)).toBe(true);
  });

  it("is false once that user has already signed", () => {
    localStorage.setItem(
      "currentUser",
      JSON.stringify({ id: 6, name: "John Smith", role: "Sponsor" }),
    );
    const request = makeBackendRequest();
    expect(currentUserCanSign(request)).toBe(false);
  });

  it("is false for non-signers and anonymous sessions", () => {
    localStorage.setItem(
      "currentUser",
      JSON.stringify({ id: 999, name: "Nobody", role: "CRO" }),
    );
    expect(currentUserCanSign(makeBackendRequest())).toBe(false);

    localStorage.removeItem("currentUser");
    expect(currentUserCanSign(makeBackendRequest())).toBe(false);
  });
});

describe("API mode", () => {
  beforeEach(() => {
    localStorage.clear();
    (isApiEnabled as any).mockReturnValue(true);
  });

  it("lists requests from the backend", async () => {
    const transport = {
      get: vi.fn().mockResolvedValue([makeBackendRequest()]),
    };
    const rows = await getSignatureRequests(transport as any);
    expect(transport.get).toHaveBeenCalledWith("/api/signature-requests");
    expect(rows).toHaveLength(1);
    expect(rows[0].requestId).toBe(7);
  });

  it("creates a request with the exact backend contract", async () => {
    const transport = {
      post: vi.fn().mockResolvedValue(makeBackendRequest()),
    };
    const { request, error } = await createSignatureRequest(
      {
        documentId: 101,
        studyId: 202,
        title: "Approve ICF v2.0",
        status: SIGNATURE_REQUEST_STATUSES.SENT,
        signers: [
          { userId: 5, signerName: "Jane Doe", signerRole: "PI" },
          { userId: 6, signerName: "John Smith", signerRole: "Sponsor" },
        ],
      },
      transport as any,
    );
    expect(error).toBeUndefined();
    expect(transport.post).toHaveBeenCalledWith("/api/signature-requests", {
      documentId: 101,
      studyId: 202,
      title: "Approve ICF v2.0",
      status: "SENT",
      signers: [
        { userId: 5, signerName: "Jane Doe", signerRole: "PI" },
        { userId: 6, signerName: "John Smith", signerRole: "Sponsor" },
      ],
    });
    expect(request.requestId).toBe(7);
  });

  it("signs a request with the stamped signature payload", async () => {
    const transport = {
      post: vi.fn().mockResolvedValue(
        makeBackendRequest({
          status: "COMPLETED",
          signers: [
            {
              signerId: 11,
              requestId: 7,
              userId: 5,
              signerName: "Jane Doe",
              signerRole: "PI",
              status: "SIGNED",
              meaning: "approval",
              signedAt: "2026-09-03T08:00:00",
              verificationStatus: "verified",
            },
            {
              signerId: 12,
              requestId: 7,
              userId: 6,
              signerName: "John Smith",
              signerRole: "Sponsor",
              status: "SIGNED",
              meaning: "approval",
              signedAt: "2026-09-02T12:00:00",
              verificationStatus: "verified",
            },
          ],
        }),
      ),
    };
    const { request, error } = await signSignatureRequest(
      7,
      {
        printedName: "Jane Doe",
        signatureStamp: "abc123",
        signedAt: "2026-09-03T08:00:00",
        meaning: "approval",
      },
      transport as any,
    );
    expect(error).toBeUndefined();
    expect(transport.post).toHaveBeenCalledWith("/api/signature-requests/7/sign", {
      meaning: "approval",
      signature: {
        printedName: "Jane Doe",
        signatureStamp: "abc123",
        signedAt: "2026-09-03T08:00:00",
      },
    });
    expect(request.status).toBe("COMPLETED");
  });

  it("surfaces a backend rejection instead of writing a broken mirror", async () => {
    const transport = {
      post: vi.fn().mockRejectedValue({ message: "documentId is required." }),
    };
    const { request, error } = await createSignatureRequest(
      { signers: [{ userId: 1, signerName: "A" }] },
      transport as any,
    );
    expect(request).toBeNull();
    expect(error).toContain("documentId is required");
    expect(getSignatureRequests(transport as any)).resolves.toEqual([]);
  });
});

describe("offline mirror", () => {
  beforeEach(() => {
    localStorage.clear();
    (isApiEnabled as any).mockReturnValue(false);
  });

  it("creates and lists requests locally", async () => {
    const { request, error } = await createSignatureRequest({
      documentId: 101,
      title: "Offline draft",
      status: SIGNATURE_REQUEST_STATUSES.DRAFT,
      signers: [{ userId: 5, signerName: "Jane Doe" }],
    });
    expect(error).toBeUndefined();
    expect(String(request.requestId).startsWith("local-")).toBe(true);
    expect(request.status).toBe("DRAFT");

    const rows = await getSignatureRequests();
    expect(rows).toHaveLength(1);
    expect(rows[0].title).toBe("Offline draft");
  });

  it("signs the current user's row and completes the request when all signed", async () => {
    localStorage.setItem(
      "currentUser",
      JSON.stringify({ id: 5, name: "Jane Doe", role: "PI" }),
    );
    await createSignatureRequest({
      documentId: 101,
      title: "Offline sign-off",
      status: SIGNATURE_REQUEST_STATUSES.SENT,
      signers: [
        { userId: 5, signerName: "Jane Doe", signerRole: "PI" },
        { userId: 6, signerName: "John Smith", signerRole: "Sponsor" },
      ],
    });

    const [created] = await getSignatureRequests();
    expect(created.status).toBe("SENT");
    expect(currentUserCanSign(created)).toBe(true);

    const { request: signed, error } = await signSignatureRequest(
      created.requestId,
      { printedName: "Jane Doe", signatureStamp: "deadbeef", meaning: "approval" },
    );
    expect(error).toBeUndefined();
    // One of two signers has signed — the request stays SENT.
    expect(signed.status).toBe("SENT");
    expect(signed.signers.find((s: any) => s.userId === 5).status).toBe("SIGNED");
    expect(signed.signers.find((s: any) => s.userId === 5).verificationStatus).toBe("verified");
    expect(currentUserCanSign(signed)).toBe(false);

    // Second signer completes the request.
    localStorage.setItem(
      "currentUser",
      JSON.stringify({ id: 6, name: "John Smith", role: "Sponsor" }),
    );
    const { request: completed } = await signSignatureRequest(
      created.requestId,
      { printedName: "John Smith", meaning: "review" },
    );
    expect(completed.status).toBe("COMPLETED");
    expect(completed.completedAt).toBeDefined();
    expect(completed.signers.every((s: any) => s.status === "SIGNED")).toBe(true);
  });

  it("loads the directory from localStorage users when offline", async () => {
    (getUsers as any).mockReturnValue([
      { id: 1, name: "Ada", email: "ada@tria.test", role: "PI", approvalStatus: "Approved", accountStatus: "Active" },
      { id: 2, name: "Blocked", email: "b@tria.test", role: "CRO", approvalStatus: "Approved", accountStatus: "Inactive" },
    ]);
    const users = await fetchDirectoryUsers();
    expect(users).toHaveLength(1);
    expect(users[0].name).toBe("Ada");
    expect(users[0].role).toBe("PI");
  });
});