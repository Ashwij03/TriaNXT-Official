/**
 * Subject consent status (Task 3)
 * ================================
 * Pure derivation of a subject's current consent state from the same source
 * data the backend `GET /api/site/subjects/{code}/consent` endpoint reads
 * (consent events + ICF versions + open re-consent campaigns). The rules
 * here mirror `derive_subject_consent` in tria_engine/apps/ctms/
 * router_subjects.py so the badge shows the same status online and offline.
 *
 * Statuses:
 *   reconsent_required -> an open re-consent campaign is pending, or the
 *                          consent was recorded on a superseded/expired ICF
 *   not_consented      -> no consent event recorded at all
 *   expiring_soon      -> latest consent is older than the validity window
 *   consented          -> all good
 */

import { isApiEnabled, api } from "../../services/api/client";
import {
  getConsentEvents,
  getIcfVersions,
  getReConsentCampaigns,
} from "../../services/icfConsentService";

/** Mirror of backend CONSENT_VALIDITY_DAYS (router_subjects.py). */
export const CONSENT_VALIDITY_DAYS = 730;

export const SUBJECT_CONSENT_STATUSES = [
  "consented",
  "expiring_soon",
  "not_consented",
  "reconsent_required",
] as const;

export type SubjectConsentState = (typeof SUBJECT_CONSENT_STATUSES)[number];

export interface SubjectConsentStatus {
  status: SubjectConsentState;
  label: string;
  needsAttention: boolean;
  reason: string;
  campaignId?: string;
  icfVersionId?: string;
}

function norm(value: any): string {
  return String(value ?? "").trim().toLowerCase();
}

function subjectIdOf(subject: any = {}): string {
  return String(subject.subjectId || subject.id || "").trim();
}

function studyOf(subject: any = {}): string {
  return String(subject.studyId || subject.study || "").trim();
}

/**
 * Local (offline) derivation — same order of checks as the backend:
 *  1. open re-consent campaign pending for this subject
 *  2. no consent event at all
 *  3. consented on a superseded/expired/archived ICF version
 *  4. consent older than the validity window -> expiring soon
 *  5. otherwise consented
 */
export function getSubjectConsentStatus(
  subject: any = {},
  consentEvents: any[] = [],
  icfVersions: any[] = [],
  reconsentCampaigns: any[] = [],
  options: { now?: Date } = {},
): SubjectConsentStatus {
  const subjectId = subjectIdOf(subject);
  const studyCode = studyOf(subject);
  const today = (options.now || new Date()).toISOString().slice(0, 10);

  const openCampaign = (reconsentCampaigns || []).find(
    (campaign) =>
      norm(campaign.status) === "open" &&
      (!studyCode || norm(campaign.studyCode) === norm(studyCode)) &&
      (campaign.subjects || []).some(
        (entry: any) =>
          norm(entry.subjectId) === norm(subjectId) && !entry.completedAt,
      ),
  );

  if (openCampaign) {
    return {
      status: "reconsent_required",
      label: "Re-consent Required",
      needsAttention: true,
      reason: `Subject ${subjectId} must re-consent on ICF v${
        openCampaign.icfVersion || "?"
      } (campaign ${openCampaign.id}).`,
      campaignId: openCampaign.id,
    };
  }

  const subjectEvents = (consentEvents || []).filter(
    (event) =>
      norm(event.subjectId) === norm(subjectId) &&
      (!studyCode || norm(event.studyCode) === norm(studyCode)),
  );

  if (subjectEvents.length === 0) {
    return {
      status: "not_consented",
      label: "Not Consented",
      needsAttention: true,
      reason: `No consent event has been recorded for subject ${subjectId}.`,
    };
  }

  const latest = subjectEvents.reduce((newest, event) => {
    const at = String(event.date || event.createdAt || "");
    const newestAt = String(newest.date || newest.createdAt || "");
    return at > newestAt ? event : newest;
  }, subjectEvents[0]);

  const icfVersionId = String(latest.icfVersionId || "").trim();
  const icfVersion = (icfVersions || []).find(
    (version) => String(version.id || "").trim() === icfVersionId,
  );

  if (icfVersion) {
    const versionStatus = norm(icfVersion.status);
    if (["superseded", "expired", "archived"].includes(versionStatus)) {
      return {
        status: "reconsent_required",
        label: "Re-consent Required",
        needsAttention: true,
        reason: `Consent was recorded on ICF v${icfVersion.version} which is now ${icfVersion.status}.`,
        icfVersionId,
      };
    }
  }

  const consentDate = String(latest.date || latest.createdAt || "").slice(0, 10);
  if (consentDate) {
    const signedOn = new Date(`${consentDate}T00:00:00Z`);
    if (!Number.isNaN(signedOn.getTime())) {
      const todayDate = new Date(`${today}T00:00:00Z`);
      const ageDays = Math.round(
        (todayDate.getTime() - signedOn.getTime()) / 86_400_000,
      );
      if (ageDays > CONSENT_VALIDITY_DAYS) {
        return {
          status: "expiring_soon",
          label: "Expiring Soon",
          needsAttention: true,
          reason: `Consent on ICF v${
            icfVersion ? icfVersion.version : "?"
          } signed ${consentDate} is older than the ${CONSENT_VALIDITY_DAYS}-day validity window.`,
          icfVersionId,
        };
      }
    }
  }

  return {
    status: "consented",
    label: "Consented",
    needsAttention: false,
    reason: `Consent confirmed on ICF v${
      icfVersion ? icfVersion.version : "?"
    } on ${consentDate || "recorded"}.`,
    icfVersionId,
  };
}

/**
 * API-first wrapper: in API mode prefer the server-computed consent status
 * (GET /api/site/subjects/{code}/consent) and fall back to the local
 * derivation from the same ICF/eConsent stores when the backend is
 * unreachable or not configured (standard fail-soft pattern).
 */
export async function fetchSubjectConsentStatus(
  subject: any = {},
): Promise<SubjectConsentStatus> {
  const code = String(subject.subjectId || subject.id || "").trim();

  if (isApiEnabled() && code) {
    try {
      const response = await api.get(
        `/api/site/subjects/${encodeURIComponent(code)}/consent`,
      );
      const payload = (response as any)?.data ?? response;
      if (payload && payload.status) {
        return {
          status: payload.status,
          label: payload.label || payload.status,
          needsAttention: Boolean(payload.needsAttention),
          reason: payload.reason || "",
          ...(payload.campaignId ? { campaignId: payload.campaignId } : {}),
          ...(payload.icfVersionId
            ? { icfVersionId: payload.icfVersionId }
            : {}),
        };
      }
    } catch {
      // Backend unreachable — fall through to the local derivation.
    }
  }

  const studyCode = studyOf(subject);
  return getSubjectConsentStatus(
    subject,
    getConsentEvents(studyCode, subjectIdOf(subject)),
    getIcfVersions(studyCode),
    getReConsentCampaigns(studyCode),
  );
}

const SubjectConsentStatusService = {
  CONSENT_VALIDITY_DAYS,
  SUBJECT_CONSENT_STATUSES,
  getSubjectConsentStatus,
  fetchSubjectConsentStatus,
};

export default SubjectConsentStatusService;
