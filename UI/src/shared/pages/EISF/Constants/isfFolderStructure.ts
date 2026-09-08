/**
 * eISF folder / zone structure (canonical).
 * =========================================
 * The eISF binder's top-level zones and their standard subfolders, used to
 * seed a new study's eISF binder and to drive the EISF dashboard/module
 * workspace navigation.
 *
 * This file is the single named home for the structure the eISF module
 * renders. It is built FROM the existing `EISFMenuConfig` (the menu that
 * EISFDashboard / EISFModuleWorkspace already render) rather than
 * duplicating a second list, so the two can never drift apart: change the
 * menu and the structure follows.
 */

import EISFMenuConfig from "./EISFMenuConfig";

/** Canonical binder config — the raw section tree (id/title/path/children). */
export const EISF_BINDER_CONFIG = EISFMenuConfig;

/** Top-level eISF zones (the "1.0 / 2.0 / 3.0 …" sections). */
export const EISF_ZONES = EISFMenuConfig.map((section) => ({
  id: section.id,
  title: section.title,
  path: section.path,
}));

/** Zone + standard-subfolder pairs, e.g. [{ zone: "1.0", folders: [...] }]. */
export const EISF_ZONE_FOLDERS = EISFMenuConfig.map((section) => ({
  zoneId: section.id,
  zoneTitle: section.title,
  folders: (section.children || []).map((child) => ({
    id: child.id,
    title: child.title,
    path: child.path,
  })),
}));

/** Flat list of every standard folder across all zones. */
export const EISF_FOLDERS = EISFMenuConfig.flatMap((section) =>
  (section.children || []).map((child) => ({
    zoneId: section.id,
    zoneTitle: section.title,
    id: child.id,
    title: child.title,
    path: child.path,
  })),
);

/** Seeding helper: the folder names (titles) to create under a study binder. */
export function defaultEisfFolderNames(): string[] {
  return EISFMenuConfig.flatMap((section) =>
    (section.children || []).map((child) => child.title),
  );
}

export default EISFMenuConfig;