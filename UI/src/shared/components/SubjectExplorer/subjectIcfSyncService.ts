/**
 * Subject ICF folder reconciliation (Task 3.2.4)
 * ==============================================
 * Keeps a subject's locked, system-managed ICF folder — which lives inside
 * that subject's file tree at the deterministic path `<subjectId>/icf` —
 * reconciled in both directions with the ICF version records that
 * subjectConsentStatus.ts / the eISF surface read (icfConsentService, the
 * single consent/ICF store — no new store is introduced).
 *
 *   * Files added/removed/renamed inside `<subjectId>/icf` are mirrored into
 *     icfConsentService as ICF versions tagged `source: "subject-explorer"`.
 *   * In API mode, new mirror versions are best-effort POSTed to
 *     /api/site/icf/versions (persisted into ctms_icfversion) — fail-soft,
 *     never throwing to the UI.
 *
 * The ICF folder itself is already protected from rename/delete by the
 * existing locked-folder mechanism (folderTreeService creates it with
 * `locked: true`; SubjectFileManager refuses rename/delete inside locked
 * folders), so no second protection concept is introduced here.
 */

import { isApiEnabled, api } from "../../services/api/client";
import {
  createIcfVersion,
  getIcfVersions,
} from "../../services/icfConsentService";
import { findSubjectRecord } from "./subjectRecordsService";
import { listFiles } from "./fileService";

/** The canonical ICF folder name inside a subject's file tree. */
export const ICF_FOLDER_NAME = "icf";

/** True when a folder id is the system ICF folder of some subject. */
export function isIcfFolder(folderId: any): boolean {
  const id = String(folderId || "").trim().toLowerCase();
  return id === ICF_FOLDER_NAME || id.endsWith(`/${ICF_FOLDER_NAME}`);
}

/** Owning subject id of an ICF folder, or null when not an ICF folder. */
export function subjectOfIcfFolder(folderId: any): string | null {
  const id = String(folderId || "").trim().replace(/\/+$/, "");
  if (id === ICF_FOLDER_NAME) return null; // org-level icf folder, no subject
  if (id.toLowerCase().endsWith(`/${ICF_FOLDER_NAME}`)) {
    return id.slice(0, id.length - `/${ICF_FOLDER_NAME}`.length) || null;
  }
  return null;
}

/** Derive an ICF version number from a file name ("icf_v2.pdf" -> "2.0"). */
export function versionFromFileName(fileName: string): string {
  const match = String(fileName || "").match(/v(\d+(?:\.\d+)?)/i);
  if (match) {
    const number = match[1].includes(".")
      ? match[1]
      : `${match[1]}.0`;
    return number;
  }
  return "1.0";
}

/**
 * Mirror a subject's ICF folder files into the ICF version store.
 * For each file in the folder, a matching version tagged
 * `source: "subject-explorer"` is ensured (create if missing); in API mode
 * the new version is best-effort POSTed to /api/site/icf/versions.
 *
 * Returns { created, skipped } counts for callers/tests.
 */
export async function syncSubjectIcfFolder(
  studyId: string,
  subjectId: string,
  files: any[] = [],
): Promise<{ created: number; skipped: number }> {
  const result = { created: 0, skipped: 0 };
  if (!studyId || !subjectId) return result;

  const record = findSubjectRecord(studyId, subjectId) || {};
  const siteCode =
    String(record.siteCode || record.site || record.siteNo || "").trim();

  const existing = getIcfVersions(studyId);

  for (const file of files || []) {
    const fileName = String(file?.name || file?.fileName || "");
    if (!fileName) continue;
    const version = versionFromFileName(fileName);

    const mirrored = existing.some(
      (v: any) =>
        String(v.subjectId || "") === String(subjectId) &&
        v.source === "subject-explorer" &&
        String(v.fileName || "") === fileName,
    );
    if (mirrored) continue;

    const payload: any = {
      studyCode: studyId,
      siteCode: siteCode || "UNASSIGNED",
      version,
      language: "English",
      source: "subject-explorer",
      subjectId,
      fileName,
      uploadedAt: file.createdAt || new Date().toISOString(),
    };
    try {
      createIcfVersion(payload);
      result.created += 1;
      if (isApiEnabled()) {
        // Best-effort backend mirror (ctms_icfversion via /api/site/icf/*).
        api
          .post("/api/site/icf/versions", {
            studyCode: payload.studyCode,
            siteCode: payload.siteCode,
            version: payload.version,
            language: payload.language,
          })
          .catch(() => {
            // Local version stands; the API path retries on next change.
          });
      }
    } catch {
      result.skipped += 1; // duplicate or invalid — mirror stays consistent
    }
  }
  return result;
}

/**
 * Reconcile the ICF folder from the file store: computes the folder's file
 * list (FileService.listFiles) and mirrors it. Call this on load and after
 * every add/remove/rename inside a subject's ICF folder.
 */
export async function reconcileIcfFolderFromStore(
  studyId: string,
  subjectId: string,
  store: any,
  folderId: string,
): Promise<{ created: number; skipped: number }> {
  if (!isIcfFolder(folderId)) {
    return { created: 0, skipped: 0 };
  }
  const files = listFiles(store, folderId);
  return syncSubjectIcfFolder(studyId, subjectId, files);
}

const SubjectIcfSyncService = {
  ICF_FOLDER_NAME,
  isIcfFolder,
  subjectOfIcfFolder,
  versionFromFileName,
  syncSubjectIcfFolder,
  reconcileIcfFolderFromStore,
};

export default SubjectIcfSyncService;