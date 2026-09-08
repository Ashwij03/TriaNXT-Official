/**
 * eisfApi — eISF regulatory document repository (backend /api/eisf/*).
 *
 * Thin fetch wrapper matching the pattern of safetyApi / monitoringApi: every
 * function is gated by the caller (documentService.ts) on isApiEnabled() so
 * the module keeps its localStorage path when no backend is configured.
 *
 * The backend is a JSON-mirror CRUD surface: records are the exact JSON the
 * eISF pages render, keyed by a stable `id` (row code); writes require a
 * captured SignaturePayload (Part 11 gate) on the payload's `signature` key.
 */
import api from "./client";

/** List documents (study/site/folder/status filters). */
export function listDocuments(params = {}) {
  return api.get("/api/eisf/documents", { query: params });
}

/** One document + version history. */
export function getDocument(code) {
  return api.get(`/api/eisf/documents/${encodeURIComponent(code)}`);
}

/** Create/upload a document (payload must carry a `signature` object). */
export function createDocument(payload) {
  return api.post("/api/eisf/documents", payload);
}

/** Update/replace a document (new version; payload must carry a signature). */
export function updateDocument(code, payload) {
  return api.put(`/api/eisf/documents/${encodeURIComponent(code)}`, payload);
}

/** Delete a document (signature required, Admin only). */
export function deleteDocument(code, signature = null) {
  return api.delete(`/api/eisf/documents/${encodeURIComponent(code)}`, {
    body: signature ? { signature } : {},
  });
}

/** Canonical binder taxonomy (EISF_STRUCTURE on the backend). */
export function getStructure() {
  return api.get("/api/eisf/structure");
}

/** Sign a document (records a Part 11 signature row server-side). */
export function signDocument(code, body) {
  return api.post(
    `/api/eisf/documents/${encodeURIComponent(code)}/sign`,
    body,
  );
}

/** Verify a document's content hash against the hash recorded at signing. */
export function verifyDocumentIntegrity(code) {
  return api.get(`/api/eisf/documents/${encodeURIComponent(code)}/verify-integrity`);
}

/** Issue a short-lived signed download token. */
export function getDownloadToken(code) {
  return api.get(`/api/eisf/documents/${encodeURIComponent(code)}/download-token`);
}

const eisfApi = {
  listDocuments,
  getDocument,
  createDocument,
  updateDocument,
  deleteDocument,
  getStructure,
  signDocument,
  verifyDocumentIntegrity,
  getDownloadToken,
};

export default eisfApi;