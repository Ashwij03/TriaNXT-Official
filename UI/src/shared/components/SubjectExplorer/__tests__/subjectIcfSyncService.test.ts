/**
 * Unit tests for subjectIcfSyncService (Task 3.2.4).
 *
 * Covers the pure derivation helpers: ICF-folder detection, owning-subject
 * resolution, and ICF version numbers derived from file names.
 */

import {
  ICF_FOLDER_NAME,
  isIcfFolder,
  subjectOfIcfFolder,
  versionFromFileName,
} from "../subjectIcfSyncService";

describe("ICF folder detection", () => {
  it("recognizes the canonical folder name", () => {
    expect(ICF_FOLDER_NAME).toBe("icf");
    expect(isIcfFolder("icf")).toBe(true);
    expect(isIcfFolder("SUB-004/icf")).toBe(true);
    expect(isIcfFolder("SUB-004/consent-forms")).toBe(false);
    expect(isIcfFolder(null)).toBe(false);
    expect(isIcfFolder("")).toBe(false);
  });
});

describe("subjectOfIcfFolder", () => {
  it("returns the owning subject for path-style ids", () => {
    expect(subjectOfIcfFolder("SUB-004/icf")).toBe("SUB-004");
    expect(subjectOfIcfFolder("SUB-004/icf/")).toBe("SUB-004");
    expect(subjectOfIcfFolder("S-1/consent/icf")).toBe("S-1/consent");
  });

  it("returns null for non-ICF folders and org-level icf", () => {
    expect(subjectOfIcfFolder("SUB-004/files")).toBeNull();
    expect(subjectOfIcfFolder("icf")).toBeNull();
    expect(subjectOfIcfFolder(null)).toBeNull();
  });
});

describe("versionFromFileName", () => {
  it("parses explicit version markers", () => {
    expect(versionFromFileName("icf_v2.pdf")).toBe("2.0");
    expect(versionFromFileName("ICF-V3.1_FINAL.pdf")).toBe("3.1");
    expect(versionFromFileName("v1 consent.pdf")).toBe("1.0");
  });

  it("falls back to 1.0 without a marker", () => {
    expect(versionFromFileName("informed-consent.pdf")).toBe("1.0");
    expect(versionFromFileName("")).toBe("1.0");
  });
});