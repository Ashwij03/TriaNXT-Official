import { useEffect, useMemo, useState } from "react";
import {
  SIGNATURE_MEANINGS,
  closeSignature,
  confirmLabelForAction,
  createActionSignature,
  defaultMeaningForAction,
  getDefaultSigningName,
  getSignatureRequest,
  signEntity,
  signatureMeaningLabel,
  subscribeSignatureRequest,
} from "../services/actionSignatureService";
import "./ESignatureModal.css";

/**
 * ESignatureModal — 21 CFR Part 11 signature capture (Task 1).
 *
 * A single instance is mounted in App.tsx; components request a signature
 * imperatively via `openSignature({ ... })` from actionSignatureService. The
 * modal renders the request (title/description of what is being authorized),
 * captures the printed name (defaulted from the signed-in user), shows the
 * signature stamp in a script treatment, and — for destructive actions —
 * requires the user to type the exact confirmation word before Sign enables.
 * `onSigned` fires once with the captured SignaturePayload; the caller's
 * mutation only runs then.
 */
export default function ESignatureModal() {
  const request = useSignatureRequest();
  const [printedName, setPrintedName] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [meaning, setMeaning] = useState("approval");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Reset the form whenever a new signature request opens.
  useEffect(() => {
    if (request) {
      setPrintedName(getDefaultSigningName() || "");
      setConfirmation("");
      setError("");
      setSubmitting(false);
      setMeaning(request.meaning || defaultMeaningForAction(request.actionKey));
    }
  }, [request]);

  const typedConfirmation = request?.requireTypedConfirmation || "";
  const nameValid = printedName.trim().length > 0;
  const confirmationValid =
    typedConfirmation.length === 0 ||
    confirmation.trim() === typedConfirmation;
  const canSign = nameValid && confirmationValid && !submitting;

  const meanings = request?.meanings || SIGNATURE_MEANINGS;
  const signedAt = useMemo(() => new Date().toISOString(), [request]);

  if (!request) return null;

  const handleCancel = () => {
    const onCancel = request.onCancel;
    closeSignature();
    onCancel?.();
  };

  const handleSign = async () => {
    if (!canSign) return;

    setSubmitting(true);
    setError("");

    try {
      // Real tamper-evident stamp: SHA-256 of the canonical signing payload
      // (action + entity + meaning + signer identity + timestamp). The raw
      // typed name is no longer used as the stamp.
      const signature = await createActionSignature({
        actionKey: request.actionKey || "sign",
        entityType: request.entityType || "",
        entityName: request.entityName || "",
        meaning,
        meta: request.meta,
        printedName: printedName.trim(),
      });

      // Record the audit trail first (append-only, fail-soft).
      if (request.actionKey) {
        await signEntity(
          request.actionKey,
          request.entityType || "",
          request.entityName || "",
          signature,
          request.meta,
        );
      }

      await request.onSigned(signature);
      closeSignature();
    } catch (err) {
      setError(
        (err && (err as any).message) ||
          "The action could not be completed. Please try again.",
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="esign-overlay" role="dialog" aria-modal="true" aria-label="Electronic signature">
      <div className="esign-modal">
        <div className="esign-header">
          <h2>{request.title || "Electronic Signature"}</h2>
          <button
            type="button"
            className="esign-close"
            onClick={handleCancel}
            aria-label="Cancel signature"
            disabled={submitting}
          >
            ×
          </button>
        </div>

        <div className="esign-body">
          <p className="esign-description">{request.description}</p>

          {typedConfirmation && (
            <div className="esign-warning">
              <strong>Warning:</strong> this action cannot be undone.
            </div>
          )}

          <div className="esign-form-group">
            <label htmlFor="esign-printed-name">
              <span className="required">*</span> Printed Full Name
            </label>
            <input
              id="esign-printed-name"
              type="text"
              className={`esign-input ${error ? "error" : ""}`}
              placeholder="Enter your full legal name"
              value={printedName}
              onChange={(e) => setPrintedName(e.target.value)}
              disabled={submitting}
              autoFocus
            />
          </div>

          <div className="esign-form-group esign-meaning-group">
            <fieldset className="esign-meaning-fieldset">
              <legend>
                <span className="required">*</span> Purpose of Signature
              </legend>
              {meanings.map((option) => (
                <label
                  key={option.value}
                  className={`esign-meaning-option ${
                    meaning === option.value ? "selected" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="esign-meaning"
                    value={option.value}
                    checked={meaning === option.value}
                    onChange={() => setMeaning(option.value)}
                    disabled={submitting}
                  />
                  <span className="esign-meaning-label">{option.label}</span>
                  {option.description && (
                    <span className="esign-meaning-description">
                      {option.description}
                    </span>
                  )}
                </label>
              ))}
            </fieldset>
          </div>

          <div className="esign-stamp-block">
            <div className="esign-stamp">
              <span className="esign-stamp-script">
                {printedName.trim() || "Signature"}
              </span>
              <span className="esign-stamp-meta">
                {signatureMeaningLabel(meaning)} · Signed at {signedAt} (UTC)
              </span>
            </div>
            <p className="esign-stamp-hint">
              On signing, a tamper-evident SHA-256 stamp is computed over this
              action, its purpose ({signatureMeaningLabel(meaning)}), your
              identity and the timestamp — replacing the typed name as the
              stored signature stamp.
            </p>
          </div>

          {typedConfirmation && (
            <div className="esign-form-group">
              <label htmlFor="esign-confirmation">
                <span className="required">*</span> Type{" "}
                <strong className="esign-confirm-word">{typedConfirmation}</strong>{" "}
                to confirm
              </label>
              <input
                id="esign-confirmation"
                type="text"
                className={`esign-input ${error ? "error" : ""}`}
                placeholder={`Type ${typedConfirmation}`}
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                disabled={submitting}
              />
            </div>
          )}

          {error && <span className="esign-error-message">{error}</span>}
        </div>

        <div className="esign-footer">
          <button
            type="button"
            className="esign-cancel-btn"
            onClick={handleCancel}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="esign-sign-btn"
            onClick={handleSign}
            disabled={!canSign}
          >
            {submitting
              ? "Signing…"
              : confirmLabelForAction(request.actionKey)}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Subscribe to the imperative signature request store. */
function useSignatureRequest() {
  const [request, setRequest] = useState(getSignatureRequest());

  useEffect(
    () =>
      subscribeSignatureRequest(() => {
        setRequest(getSignatureRequest());
      }),
    [],
  );

  return request;
}