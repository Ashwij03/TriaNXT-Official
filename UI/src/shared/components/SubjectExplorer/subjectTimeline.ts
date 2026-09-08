/**
 * Subject timeline (Task 3)
 * =========================
 * Builds the single, chronologically-merged timeline shown on the Subject
 * Profile: status transitions + completed visits + consent events, each
 * entry tagged with its source type so the UI can render a distinct
 * icon/label per entry type.
 *
 * Mirrors `_build_subject_timeline` in tria_engine/apps/ctms/
 * router_subjects.py. In API mode the merged timeline comes from
 * `GET /api/site/subjects/{code}/history`; the local derivation below is
 * the offline fallback and consumes the same local stores the backend
 * mirrors (subjectService status-history trail, visit schedules, ICF
 * consent events).
 */

import { isApiEnabled, api } from "../../services/api/client";
import { getSubjectStatusHistory } from "../../services/subjectService";
import { getConsentEvents } from "../../services/icfConsentService";
// The visit-schedule store getter lives in adminService (visitScheduleService
// does not export a top-level getSchedules) — same store the calendar reads.
import { getSchedules } from "../../services/adminService";

export const TIMELINE_ENTRY_TYPES = ["status_change", "visit", "consent"] as const;

export type TimelineEntryType = (typeof TIMELINE_ENTRY_TYPES)[number];

export interface TimelineEntry {
  type: TimelineEntryType;
  at: string;
  label: string;
  detail: Record<string, any>;
}

function ts(value: any): string {
  return String(value || "").trim() || new Date().toISOString();
}

/**
 * Pure merge + sort + tag. Input rows are the raw source records:
 *   - statusHistory: append-only transition rows
 *     ({ status, reason, changedBy, changedAt })
 *   - visits: completed visit records ({ visit, date, status, completedAt })
 *   - consentEvents: consent records ({ icfVersion, icfVersionId, date })
 */
export function buildSubjectTimeline({
  statusHistory = [],
  visits = [],
  consentEvents = [],
}: {
  statusHistory?: any[];
  visits?: any[];
  consentEvents?: any[];
}): TimelineEntry[] {
  const entries: TimelineEntry[] = [];

  (statusHistory || []).forEach((row) => {
    entries.push({
      type: "status_change",
      at: ts(row.changedAt || row.createdAt),
      label: `Status changed to ${row.status || "Unknown"}`,
      detail: {
        status: row.status,
        reason: row.reason || "",
        changedBy: row.changedBy || "",
      },
    });
  });

  (visits || []).forEach((visit) => {
    entries.push({
      type: "visit",
      at: ts(
        visit.completedAt || visit.actualDate || visit.date || visit.createdAt,
      ),
      label: `Visit ${visit.visit || visit.visitName || "?"} completed`,
      detail: {
        visit: visit.visit || visit.visitName,
        date: visit.date,
        status: visit.status,
      },
    });
  });

  (consentEvents || []).forEach((event) => {
    entries.push({
      type: "consent",
      at: ts(event.date || event.createdAt),
      label: `Consent recorded on ICF v${event.icfVersion || "?"}`,
      detail: {
        icfVersion: event.icfVersion,
        icfVersionId: event.icfVersionId,
        witness: event.witness || "",
      },
    });
  });

  entries.sort((a, b) => a.at.localeCompare(b.at));
  return entries;
}

/** Completed visits for one subject from the local visit-schedule store. */
function localCompletedVisits(studyId: string, subjectId: string): any[] {
  try {
    return (getSchedules() || []).filter(
      (schedule: any) =>
        String(schedule.subjectId || "").trim() ===
          String(subjectId || "").trim() &&
        (!studyId ||
          String(schedule.study || schedule.studyCode || "").trim() ===
            String(studyId || "").trim()) &&
        String(schedule.status || "").trim().toLowerCase() === "completed",
    );
  } catch {
    return [];
  }
}

/**
 * API-first: fetch the merged timeline from the backend; on failure (or
 * without a configured backend) derive it locally from the same stores.
 */
export async function getSubjectTimeline(subject: any = {}): Promise<{
  subjectId: string;
  studyId: string;
  timeline: TimelineEntry[];
  source: "api" | "local";
}> {
  const subjectId = String(subject.subjectId || subject.id || "").trim();
  const studyId = String(subject.studyId || subject.study || "").trim();
  const code = subjectId || subject.code;

  if (isApiEnabled() && code) {
    try {
      const response = await api.get(
        `/api/site/subjects/${encodeURIComponent(code)}/history`,
      );
      const payload = (response as any)?.timeline
        ? response
        : (response as any)?.data;
      if (payload && Array.isArray(payload.timeline)) {
        return {
          subjectId: payload.subjectId || subjectId,
          studyId: payload.studyId || studyId,
          timeline: payload.timeline,
          source: "api",
        };
      }
    } catch {
      // Backend unreachable — fall through to the local derivation.
    }
  }

  return {
    subjectId,
    studyId,
    timeline: buildSubjectTimeline({
      statusHistory: studyId
        ? getSubjectStatusHistory(studyId, subjectId)
        : [],
      visits: localCompletedVisits(studyId, subjectId),
      consentEvents: getConsentEvents(studyId, subjectId),
    }),
    source: "local",
  };
}

const SubjectTimelineService = {
  TIMELINE_ENTRY_TYPES,
  buildSubjectTimeline,
  getSubjectTimeline,
};

export default SubjectTimelineService;
