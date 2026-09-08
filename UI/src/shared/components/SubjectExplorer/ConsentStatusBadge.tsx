import { useEffect, useState } from "react";
import {
  getSubjectConsentStatus,
  SubjectConsentStatus,
} from "./subjectConsentStatus";
import {
  getConsentEvents,
  getIcfVersions,
  getReConsentCampaigns,
  subscribeConsentIcf,
} from "../../services/icfConsentService";
import { findSubjectRecord } from "./subjectRecordsService";

/**
 * useSubjectConsentStatus(studyId, subjectId, subject?)
 * ======================================================
 * React binding over getSubjectConsentStatus() (the single source of truth
 * for consent state — see subjectConsentStatus.ts). Recomputes when the
 * subject/study changes and subscribes to the ICF/eConsent store so the
 * badge stays live when a consent event / ICF version / re-consent campaign
 * changes elsewhere in the app.
 */
export function useSubjectConsentStatus(
  studyId: string,
  subjectId: string,
  subject: any = null,
): SubjectConsentStatus | null {
  const [status, setStatus] = useState<SubjectConsentStatus | null>(null);

  useEffect(() => {
    const compute = () => {
      const record =
        subject ||
        (studyId && subjectId
          ? findSubjectRecord(studyId, subjectId)
          : null) ||
        null;
      const subjectLike = record || { subjectId, studyId };
      setStatus(
        getSubjectConsentStatus(
          subjectLike,
          getConsentEvents(studyId, subjectId),
          getIcfVersions(studyId),
          getReConsentCampaigns(studyId),
        ),
      );
    };

    compute();
    const unsubscribe = subscribeConsentIcf(compute);
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId, subjectId]);

  return status;
}

/**
 * ConsentStatusBadge — a small status pill rendering a subject's consent
 * state (Consented / Not Consented / Re-consent Required / Expiring Soon).
 *
 * Styling follows the shared status-pill language used across the app
 * (`.sf-status-pill`-style rounded pills); the specific colors live in
 * SubjectProfile.css (`.subject-consent-badge`).
 *
 * Props
 *   studyId, subjectId  identify the subject (used by the hook)
 *   subject             optional pre-resolved subject record (avoids the
 *                       store lookup when the caller already has it)
 *   status              optional precomputed status (skips the hook entirely)
 *   showTooltip         when true, the reason text is shown as a title
 */
function ConsentStatusBadge({
  studyId = "",
  subjectId = "",
  subject = null,
  status = null,
  showTooltip = true,
}: any) {
  const hookStatus = useSubjectConsentStatus(studyId, subjectId, subject);
  const resolved = status || hookStatus;

  if (!resolved) return null;

  const toneClass = `subject-consent-badge--${resolved.status}`;
  return (
    <span
      className={`subject-consent-badge ${toneClass}`}
      title={showTooltip ? resolved.reason || resolved.label : undefined}
    >
      <span className="subject-consent-badge-dot" aria-hidden="true" />
      {resolved.label}
      {resolved.needsAttention && (
        <span className="subject-consent-badge-attn" aria-label="Needs attention">
          !
        </span>
      )}
    </span>
  );
}

export default ConsentStatusBadge;