/**
 * Signature Requests workspace — list / create / send / sign multi-signer
 * signature requests backed by the FastAPI /api/signature-requests surface
 * (ctms_signature_requests + ctms_signature_request_signers), with a
 * localStorage mirror when the backend is unreachable.
 *
 * Signing flows through the app-wide ESignatureModal (openSignature): the
 * captured SHA-256-stamped SignaturePayload is posted to
 * /api/signature-requests/{id}/sign, which marks the user's signer row
 * complete and appends one ctms_electronic_signature ledger row. The modal
 * is invoked WITHOUT an actionKey so it does not double-record to
 * /api/audit/signatures — the sign endpoint is the ledger writer here.
 */

import { useEffect, useMemo, useState } from "react";
import DashboardLayout from "../../components/dashboard/shared/DashboardLayout";
import DataTable from "../../components/dashboard/shared/DataTable";
import KPICard from "../../components/dashboard/shared/KPICard";
import {
  SIGNATURE_MEANINGS,
  formatSignatureStamp,
  formatSignatureTime,
  openSignature,
} from "../../services/actionSignatureService";
import {
  SIGNATURE_REQUEST_STATUSES,
  SIGNATURE_REQUESTS_EVENT,
  createSignatureRequest,
  currentUserCanSign,
  fetchDirectoryUsers,
  getCurrentUserEntry,
  getSignatureRequests,
  requestStatusLabel,
  signSignatureRequest,
  signerProgress,
} from "../../services/signatureRequestService";
import { getStudies } from "../../services/studyService";
import { getAllDocuments } from "../EISF/services/eisfService";
import "../../styles/AdminPage.css";
import "./SignatureRequests.css";

const STATUS_TABS = [
  { key: "ALL", label: "All" },
  { key: SIGNATURE_REQUEST_STATUSES.DRAFT, label: "Draft" },
  { key: SIGNATURE_REQUEST_STATUSES.SENT, label: "Sent" },
  { key: SIGNATURE_REQUEST_STATUSES.COMPLETED, label: "Completed" },
];

function resolveDocumentName(documentId) {
  if (documentId === null || documentId === undefined) return "—";
  const document = getAllDocuments().find(
    (entry) => String(entry.id) === String(documentId)
  );
  return document?.documentName || document?.name || `Document #${documentId}`;
}

function resolveStudyName(studyId) {
  if (studyId === null || studyId === undefined) return "—";
  const study = getStudies().find(
    (entry) =>
      String(entry.id) === String(studyId) ||
      String(entry.code) === String(studyId) ||
      String(entry.studyId) === String(studyId)
  );
  return study?.name || study?.code || `Study #${studyId}`;
}

function SignerChips({ signers }) {
  const entries = Array.isArray(signers) ? signers : [];
  return (
    <span className="sigreq-signer-chips">
      {entries.length === 0 && <span className="sigreq-muted">No signers</span>}
      {entries.map((signer) => {
        const signed =
          String(signer.status).toUpperCase() === "SIGNED";
        return (
          <span
            key={`${signer.signerId ?? signer.userId ?? signer.signerName}-${signer.signerName}`}
            className={`sigreq-signer-chip ${signed ? "signed" : "pending"}`}
            title={`${signer.signerName} — ${signed ? "Signed" : "Pending"}${
              signer.signedAt ? ` on ${formatSignatureTime(signer.signedAt)}` : ""
            }`}
          >
            {signed ? "✓ " : "○ "}
            {signer.signerName}
          </span>
        );
      })}
    </span>
  );
}

function StatusPill({ status }) {
  const normalized = String(status || "").toUpperCase();
  return (
    <span className={`sigreq-status-pill ${normalized.toLowerCase()}`}>
      {requestStatusLabel(status)}
    </span>
  );
}

export default function SignatureRequests() {
  const [requests, setRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [showCreate, setShowCreate] = useState(false);
  const [detailRequest, setDetailRequest] = useState<any | null>(null);
  const [notice, setNotice] = useState("");

  const refresh = async () => {
    const rows = await getSignatureRequests();
    setRequests(rows);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
    const unsubscribe = () => {};
    const onEvent = () => refresh();
    if (typeof window !== "undefined") {
      window.addEventListener(SIGNATURE_REQUESTS_EVENT, onEvent);
    }
    return () => {
      unsubscribe();
      if (typeof window !== "undefined") {
        window.removeEventListener(SIGNATURE_REQUESTS_EVENT, onEvent);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleRequests = useMemo(
    () =>
      statusFilter === "ALL"
        ? requests
        : requests.filter(
            (request) => String(request.status).toUpperCase() === statusFilter
          ),
    [requests, statusFilter]
  );

  const counts = useMemo(() => {
    const count = (status) =>
      requests.filter((r) => String(r.status).toUpperCase() === status).length;
    return {
      total: requests.length,
      draft: count(SIGNATURE_REQUEST_STATUSES.DRAFT),
      sent: count(SIGNATURE_REQUEST_STATUSES.SENT),
      completed: count(SIGNATURE_REQUEST_STATUSES.COMPLETED),
    };
  }, [requests]);

  const pendingForMe = useMemo(
    () => requests.filter((request) => currentUserCanSign(request)).length,
    [requests]
  );

  const handleSign = (request) => {
    openSignature({
      title: `Sign: ${request.title}`,
      description: `You are asked to sign "${request.title}" (${
        resolveDocumentName(request.documentId)
      }). Your signature is recorded with a tamper-evident SHA-256 stamp and appended to the electronic-signature ledger.`,
      meanings: [...SIGNATURE_MEANINGS],
      onSigned: async (signature) => {
        const { request: updated, error } = await signSignatureRequest(
          request.requestId,
          signature
        );
        if (error) {
          setNotice(error);
        } else if (updated) {
          setRequests((rows) =>
            rows.map((row) =>
              String(row.requestId) === String(updated.requestId)
                ? updated
                : row
            )
          );
          if (detailRequest && String(detailRequest.requestId) === String(updated.requestId)) {
            setDetailRequest(updated);
          }
          setNotice(
            `Signature recorded for "${updated.title}".`
          );
        }
      },
      onCancel: () => setNotice(""),
    });
  };

  const tableData = useMemo(
    () =>
      visibleRequests.map((request) => ({
        id: String(request.requestId),
        title: request.title,
        document: resolveDocumentName(request.documentId),
        study: resolveStudyName(request.studyId),
        status: requestStatusLabel(request.status),
        statusKey: String(request.status).toUpperCase(),
        signers: request.signers,
        progress: signerProgress(request),
        created: request.createdAt
          ? formatSignatureTime(request.createdAt)
          : "—",
        request,
      })),
    [visibleRequests]
  );

  return (
    <DashboardLayout>
      <div className="admin-page signature-requests-page tnxt-compact">
        <div className="admin-page-title page-section-highlight">
          <h1>Signature Requests</h1>
          <p>
            Create, send and sign multi-signer signature requests. Every
            completed signature is stamped (SHA-256) and appended to the
            electronic-signature ledger.
          </p>
        </div>

        {notice && (
          <div className="sigreq-notice">
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice("")} aria-label="Dismiss">
              ×
            </button>
          </div>
        )}

        <div className="admin-kpi-grid">
          <KPICard
            title="Total Requests"
            value={counts.total}
            subtitle="All Signature Requests"
            icon="📝"
          />
          <KPICard
            title="Awaiting My Signature"
            value={pendingForMe}
            subtitle="Pending for You"
            icon="✍️"
          />
          <KPICard
            title="Completed"
            value={counts.completed}
            subtitle="Fully Signed"
            icon="✅"
          />
        </div>

        <div className="sigreq-toolbar">
          <div className="sigreq-tabs" role="tablist" aria-label="Filter by status">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={statusFilter === tab.key}
                className={`sigreq-tab ${statusFilter === tab.key ? "active" : ""}`}
                onClick={() => setStatusFilter(tab.key)}
              >
                {tab.label}
                <span className="sigreq-tab-count">
                  {tab.key === "ALL"
                    ? counts.total
                    : tab.key === SIGNATURE_REQUEST_STATUSES.DRAFT
                      ? counts.draft
                      : tab.key === SIGNATURE_REQUEST_STATUSES.SENT
                        ? counts.sent
                        : counts.completed}
                </span>
              </button>
            ))}
          </div>
          <button
            type="button"
            className="sigreq-new-btn"
            onClick={() => setShowCreate(true)}
          >
            + New Request
          </button>
        </div>

        <div className="admin-table-section">
          <DataTable
            className="ctms-standard-table"
            title="Requests"
            columns={[
              { key: "title", label: "Title" },
              { key: "document", label: "Document" },
              { key: "study", label: "Study" },
              {
                key: "status",
                label: "Status",
                width: "120px",
                render: (value) => (
                  <StatusPill status={value} />
                ),
              },
              {
                key: "signers",
                label: "Signers",
                render: (value) => <SignerChips signers={value} />,
              },
              { key: "progress", label: "Progress", width: "120px" },
              { key: "created", label: "Created" },
              {
                key: "request",
                label: "Actions",
                width: "200px",
                render: (request) => (
                  <span className="sigreq-row-actions">
                    <button
                      type="button"
                      className="sigreq-action-btn"
                      onClick={() => setDetailRequest(request)}
                    >
                      Details
                    </button>
                    {currentUserCanSign(request) && (
                      <button
                        type="button"
                        className="sigreq-action-btn primary"
                        onClick={() => handleSign(request)}
                      >
                        Sign
                      </button>
                    )}
                  </span>
                ),
              },
            ]}
            data={tableData}
            searchable
            searchPlaceholder="Search signature requests..."
            searchFields={["title", "document", "study", "status", "progress"]}
            filters={[
              {
                key: "status",
                label: "Status",
                options: [
                  { value: "Draft", label: "Draft" },
                  { value: "Sent", label: "Sent" },
                  { value: "Completed", label: "Completed" },
                ],
              },
            ]}
            pagination
            initialPageSize={10}
            emptyMessage={
              loading
                ? "Loading signature requests..."
                : "No signature requests yet. Create one to start the sign-off workflow."
            }
          />
        </div>
      </div>

      {showCreate && (
        <CreateRequestModal
          onClose={() => setShowCreate(false)}
          onCreated={(request) => {
            setShowCreate(false);
            setRequests((rows) => [request, ...rows]);
            setNotice(`Signature request "${request.title}" created.`);
          }}
        />
      )}

      {detailRequest && (
        <RequestDetailModal
          request={detailRequest}
          onClose={() => setDetailRequest(null)}
          onSign={() => {
            const request = detailRequest;
            setDetailRequest(null);
            handleSign(request);
          }}
        />
      )}
    </DashboardLayout>
  );
}

/* ----------------------------------------------------------------------
   Create modal
---------------------------------------------------------------------- */

function CreateRequestModal({ onClose, onCreated }: any) {
  const [documents, setDocuments] = useState<any[]>([]);
  const [studies, setStudies] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);

  const [documentId, setDocumentId] = useState("");
  const [studyId, setStudyId] = useState("");
  const [title, setTitle] = useState("");
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // The backend stores documentId / studyId as real ctms_documents /
  // ctms_studies foreign keys, so the pickers offer numeric candidate ids
  // (from any documents/studies the frontend already knows) and let the
  // user type a raw numeric id when none match.
  const documentCandidates = useMemo(
    () =>
      documents
        .map((document) => ({
          id: Number(document.id),
          label: `${document.documentName || document.name || "Document"} (${document.id})`,
        }))
        .filter((entry) => Number.isInteger(entry.id) && entry.id > 0),
    [documents]
  );

  const studyCandidates = useMemo(
    () =>
      studies
        .map((study) => ({
          id: Number(study.id ?? study.studyId),
          label: `${study.name || study.code || "Study"} (${study.id ?? study.studyId})`,
        }))
        .filter((entry) => Number.isInteger(entry.id) && entry.id > 0),
    [studies]
  );

  useEffect(() => {
    setDocuments(getAllDocuments());
    setStudies(getStudies());
    fetchDirectoryUsers().then((directory) => {
      setUsers(directory);
      setLoadingUsers(false);
    });
  }, []);

  const toggleSigner = (userId) => {
    const key = String(userId);
    setSelectedUserIds((ids) =>
      ids.includes(key) ? ids.filter((id) => id !== key) : [...ids, key]
    );
  };

  const selectedSigners = users.filter((user) =>
    selectedUserIds.includes(String(user.id))
  );

  const submit = async (status: string) => {
    setError("");
    const numericDocumentId = Number(documentId);
    if (!documentId || !Number.isInteger(numericDocumentId) || numericDocumentId <= 0) {
      setError("Enter a valid numeric document id.");
      return;
    }
    if (selectedSigners.length === 0) {
      setError("Add at least one signer.");
      return;
    }
    if (!title.trim()) {
      setError("Give the request a title.");
      return;
    }

    const numericStudyId = studyId ? Number(studyId) : null;
    if (studyId && (!Number.isInteger(numericStudyId) || numericStudyId <= 0)) {
      setError("Enter a valid numeric study id, or leave study blank.");
      return;
    }

    setSubmitting(true);
    const { request, error: createError } = await createSignatureRequest({
      documentId: numericDocumentId,
      studyId: numericStudyId,
      title: title.trim(),
      status,
      signers: selectedSigners.map((user) => ({
        userId: user.id,
        signerName: user.name,
        signerRole: user.role || "",
      })),
    });
    setSubmitting(false);

    if (createError) {
      setError(createError);
      return;
    }
    onCreated(request);
  };

  return (
    <div
      className="sigreq-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="New signature request"
    >
      <div className="sigreq-modal">
        <div className="sigreq-modal-header">
          <h2>New Signature Request</h2>
          <button type="button" className="sigreq-modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="sigreq-modal-body">
          <div className="sigreq-form-group">
            <label htmlFor="sigreq-title">
              <span className="required">*</span> Title
            </label>
            <input
              id="sigreq-title"
              type="text"
              className="sigreq-input"
              placeholder="e.g. Approve ICF v2.0"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={submitting}
            />
          </div>

          <div className="sigreq-form-group">
            <label htmlFor="sigreq-document">
              <span className="required">*</span> Document ID
            </label>
            <input
              id="sigreq-document"
              type="number"
              min="1"
              className="sigreq-input"
              placeholder="e.g. 101 — the document's id in the trial master file"
              value={documentId}
              list="sigreq-document-candidates"
              onChange={(e) => setDocumentId(e.target.value)}
              disabled={submitting}
            />
            {documentCandidates.length > 0 && (
              <datalist id="sigreq-document-candidates">
                {documentCandidates.map((candidate) => (
                  <option key={candidate.id} value={String(candidate.id)}>
                    {candidate.label}
                  </option>
                ))}
              </datalist>
            )}
            {documentCandidates.length === 0 && (
              <p className="sigreq-muted">
                No numeric document ids available from the frontend store —
                enter the id of an existing trial master file document.
              </p>
            )}
          </div>

          <div className="sigreq-form-group">
            <label htmlFor="sigreq-study">
              Study ID <span className="sigreq-muted">(optional)</span>
            </label>
            <input
              id="sigreq-study"
              type="number"
              min="1"
              className="sigreq-input"
              placeholder="e.g. 202, or leave blank for organization-wide"
              value={studyId}
              list="sigreq-study-candidates"
              onChange={(e) => setStudyId(e.target.value)}
              disabled={submitting}
            />
            {studyCandidates.length > 0 && (
              <datalist id="sigreq-study-candidates">
                {studyCandidates.map((candidate) => (
                  <option key={candidate.id} value={String(candidate.id)}>
                    {candidate.label}
                  </option>
                ))}
              </datalist>
            )}
          </div>

          <div className="sigreq-form-group">
            <span className="sigreq-field-label">
              <span className="required">*</span> Signers
              <span className="sigreq-muted">
                {" "}
                — {selectedSigners.length} selected
              </span>
            </span>
            {loadingUsers ? (
              <p className="sigreq-muted">Loading directory…</p>
            ) : (
              <div className="sigreq-signer-list">
                {users.length === 0 && (
                  <p className="sigreq-muted">
                    No users in the directory yet. Signers must be registered
                    users.
                  </p>
                )}
                {users.map((user) => (
                  <label
                    key={String(user.id)}
                    className={`sigreq-signer-option ${
                      selectedUserIds.includes(String(user.id)) ? "selected" : ""
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedUserIds.includes(String(user.id))}
                      onChange={() => toggleSigner(user.id)}
                      disabled={submitting}
                    />
                    <span className="sigreq-signer-name">{user.name}</span>
                    <span className="sigreq-signer-role">
                      {user.role || "—"}
                    </span>
                    <span className="sigreq-signer-email">{user.email}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {error && <span className="sigreq-error-message">{error}</span>}
        </div>

        <div className="sigreq-modal-footer">
          <button
            type="button"
            className="sigreq-cancel-btn"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="sigreq-save-btn"
            onClick={() => submit(SIGNATURE_REQUEST_STATUSES.DRAFT)}
            disabled={submitting || loadingUsers}
          >
            {submitting ? "Saving…" : "Save Draft"}
          </button>
          <button
            type="button"
            className="sigreq-send-btn"
            onClick={() => submit(SIGNATURE_REQUEST_STATUSES.SENT)}
            disabled={submitting || loadingUsers}
          >
            {submitting ? "Sending…" : "Create & Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------
   Detail modal
---------------------------------------------------------------------- */

function RequestDetailModal({ request, onClose, onSign }: any) {
  const me = getCurrentUserEntry();
  const canSign = currentUserCanSign(request);

  return (
    <div
      className="sigreq-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Signature request: ${request.title}`}
    >
      <div className="sigreq-modal">
        <div className="sigreq-modal-header">
          <h2>{request.title}</h2>
          <button type="button" className="sigreq-modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="sigreq-modal-body">
          <div className="sigreq-detail-grid">
            <div>
              <span className="sigreq-detail-label">Document</span>
              <span className="sigreq-detail-value">
                {resolveDocumentName(request.documentId)}
              </span>
            </div>
            <div>
              <span className="sigreq-detail-label">Study</span>
              <span className="sigreq-detail-value">
                {resolveStudyName(request.studyId)}
              </span>
            </div>
            <div>
              <span className="sigreq-detail-label">Status</span>
              <span className="sigreq-detail-value">
                <StatusPill status={request.status} />
              </span>
            </div>
            <div>
              <span className="sigreq-detail-label">Created</span>
              <span className="sigreq-detail-value">
                {formatSignatureTime(request.createdAt)}
              </span>
            </div>
          </div>

          <div className="sigreq-detail-section">
            <h3>Signers</h3>
            <table className="ctms-table sigreq-signer-table">
              <thead>
                <tr>
                  <th>Signer</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Meaning</th>
                  <th>Signed At</th>
                  <th>Stamp</th>
                </tr>
              </thead>
              <tbody>
                {(request.signers || []).map((signer) => {
                  const signed =
                    String(signer.status).toUpperCase() === "SIGNED";
                  return (
                    <tr key={`${signer.signerId ?? signer.userId}-${signer.signerName}`}>
                      <td>
                        {signer.signerName}
                        {String(signer.userId) === String(me.id) && (
                          <span className="sigreq-you-tag"> you</span>
                        )}
                      </td>
                      <td>{signer.signerRole || "—"}</td>
                      <td>
                        <span
                          className={`sigreq-signer-chip ${
                            signed ? "signed" : "pending"
                          }`}
                        >
                          {signed ? "✓ Signed" : "○ Pending"}
                        </span>
                      </td>
                      <td>{signer.meaning ? String(signer.meaning).toUpperCase() : "—"}</td>
                      <td>{formatSignatureTime(signer.signedAt)}</td>
                      <td>
                        <span title={signer.signatureStamp || ""}>
                          {formatSignatureStamp(signer.signatureStamp)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="sigreq-detail-note">
              Verification status:{" "}
              {(request.signers || [])
                .map((signer) => signer.verificationStatus || "—")
                .join(", ") || "—"}
            </p>
          </div>
        </div>

        <div className="sigreq-modal-footer">
          <button type="button" className="sigreq-cancel-btn" onClick={onClose}>
            Close
          </button>
          {canSign && (
            <button type="button" className="sigreq-sign-btn" onClick={onSign}>
              ✍️ Sign Now
            </button>
          )}
        </div>
      </div>
    </div>
  );
}