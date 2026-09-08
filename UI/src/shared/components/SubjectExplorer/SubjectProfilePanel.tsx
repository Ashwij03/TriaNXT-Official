import { useEffect, useState } from "react";
import { MdClose, MdEvent, MdFlag, MdMedicalServices, MdPlace, MdTag } from "react-icons/md";

import ConsentStatusBadge from "./ConsentStatusBadge";
import { getSubjectTimeline } from "./subjectTimeline";
import { findSubjectRecord, getSubjectDetailFields } from "./subjectRecordsService";
import SubjectComments from "../../pages/subjects/SubjectComments";
import "./SubjectProfile.css";

/**
 * SubjectProfilePanel — collapsible side panel showing a subject's profile.
 *
 * Opened from the Subjects workspace ("View Profile" next to a selected
 * subject). Renders:
 *   - identity fields (ID / site / indication / enrollment date / status)
 *     sourced from subjectRecordsService (the same store the workspace and
 *     StudySubjects.js read — no second fetch path);
 *   - the ConsentStatusBadge (sourced from subjectConsentStatus.ts);
 *   - a chronological timeline of status changes / completed visits /
 *     consent events via subjectTimeline.getSubjectTimeline() (API-first
 *     with the local derivation as fallback);
 *   - an inline comments/notes section reusing SubjectComments.
 *
 * Props
 *   studyId, subjectId  the subject to profile
 *   subject             optional pre-resolved subject record/node
 *   onClose             closes the panel
 */
function SubjectProfilePanel({ studyId = "", subjectId = "", subject = null, onClose }: any) {
  const [timeline, setTimeline] = useState<any[]>([]);
  const [timelineSource, setTimelineSource] = useState<"api" | "local" | "">("");

  const record = subject || (studyId && subjectId ? findSubjectRecord(studyId, subjectId) : null) || {};

  useEffect(() => {
    let cancelled = false;
    const subjectLike = record && (record.subjectId || record.id)
      ? record
      : { subjectId, studyId };
    getSubjectTimeline(subjectLike)
      .then((result) => {
        if (cancelled) return;
        setTimeline(result.timeline || []);
        setTimelineSource(result.source || "");
      })
      .catch(() => {
        if (!cancelled) {
          setTimeline([]);
          setTimelineSource("");
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId, subjectId]);

  if (!subjectId) return null;

  const fields = getSubjectDetailFields(studyId, subjectId);
  const byKey = new Map(fields.map((field: any) => [field.key, field]));
  const fieldValue = (key: string) => byKey.get(key)?.value ?? "—";

  const FIELD_ICONS: Record<string, any> = {
    initials: MdBadgeIcon,
    status: MdFlag,
    pi: MdMedicalServices,
    studyId: MdTag,
    site: MdPlace,
    screeningDate: MdEvent,
    enrollmentDate: MdEvent,
    currentVisit: MdEvent,
  };

  return (
    <aside className="subject-profile-panel" aria-label={`Profile for subject ${subjectId}`}>
      <header className="subject-profile-header">
        <div>
          <h3 className="subject-profile-title">Subject Profile</h3>
          <span className="subject-profile-id">{subjectId || "—"}</span>
        </div>
        <button
          type="button"
          className="subject-profile-close"
          onClick={onClose}
          aria-label="Close profile panel"
        >
          <MdClose size={18} aria-hidden="true" />
        </button>
      </header>

      <div className="subject-profile-body">
        <div className="subject-profile-consent">
          <ConsentStatusBadge studyId={studyId} subjectId={subjectId} subject={record} />
        </div>

        <dl className="subject-profile-fields">
          {[
            ["initials", "Initials"],
            ["status", "Status"],
            ["pi", "Principal Investigator"],
            ["studyId", "Study"],
            ["site", "Site"],
            ["enrollmentDate", "Enrollment Date"],
          ].map(([key, label]) => {
            const Icon = FIELD_ICONS[key] || MdBadgeIcon;
            return (
              <div className="subject-profile-field" key={key}>
                <dt className="subject-profile-field-label">
                  <Icon size={13} aria-hidden="true" />
                  {label}
                </dt>
                <dd className="subject-profile-field-value">{fieldValue(key)}</dd>
              </div>
            );
          })}
        </dl>

        <section className="subject-profile-section">
          <h4 className="subject-profile-section-title">
            Timeline
            {timelineSource === "api" && (
              <span className="subject-profile-source">server</span>
            )}
          </h4>
          {timeline.length === 0 ? (
            <p className="subject-profile-empty">No events recorded yet.</p>
          ) : (
            <ol className="subject-profile-timeline">
              {timeline.map((entry, index) => (
                <li className="subject-profile-timeline-entry" key={`${entry.type}-${index}`}>
                  <span className={`subject-profile-timeline-dot subject-profile-timeline-dot--${entry.type}`} aria-hidden="true" />
                  <div className="subject-profile-timeline-body">
                    <div className="subject-profile-timeline-label">{entry.label}</div>
                    <div className="subject-profile-timeline-at">
                      {formatTimelineAt(entry.at)}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="subject-profile-section">
          <h4 className="subject-profile-section-title">Comments &amp; Notes</h4>
          <SubjectComments subjectId={subjectId} studyId={studyId} />
        </section>
      </div>
    </aside>
  );
}

function MdBadgeIcon(props: any) {
  return <MdTag size={13} aria-hidden="true" {...props} />;
}

function formatTimelineAt(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

export default SubjectProfilePanel;