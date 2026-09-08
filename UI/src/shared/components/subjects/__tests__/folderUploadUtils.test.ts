/**
 * Unit tests for folderUploadUtils (Task 3.2.3).
 *
 * Covers: relative-path normalisation, grouping by original subfolder,
 * validation reusing the caller's candidate validator (with per-file
 * rejection reasons), and nested-subfolder planning.
 */

import {
  collectSubfolders,
  groupFilesByFolder,
  relativePathOf,
  validateFolderUpload,
  walkPickedFolder,
} from "../folderUploadUtils";

function fakeFile(name: string, relPath: string) {
  const file = new File(["x"], name, { type: "text/plain" });
  Object.defineProperty(file, "webkitRelativePath", { value: relPath });
  return file;
}

describe("relativePathOf", () => {
  it("normalizes webkitRelativePath separators", () => {
    const file = fakeFile("a.pdf", "Consent/ICF v1\\a.pdf");
    expect(relativePathOf(file)).toBe("Consent/ICF v1/a.pdf");
  });
});

describe("walkPickedFolder", () => {
  it("maps files to { relativePath, folderName, file }", () => {
    const file = fakeFile("icf.pdf", "ICF Forms/icf.pdf");
    const entries = walkPickedFolder([file]);
    expect(entries).toHaveLength(1);
    expect(entries[0].relativePath).toBe("ICF Forms/icf.pdf");
    expect(entries[0].folderName).toBe("ICF Forms");
  });

  it("skips entries without a relative path", () => {
    const bare = new File(["x"], "bare.pdf");
    expect(walkPickedFolder([bare])).toHaveLength(0);
  });
});

describe("groupFilesByFolder", () => {
  it("groups by the top-level folder", () => {
    const groups = groupFilesByFolder([
      { relativePath: "A/x.pdf", file: fakeFile("x.pdf", "A/x.pdf") },
      { relativePath: "A/y.pdf", file: fakeFile("y.pdf", "A/y.pdf") },
      { relativePath: "B/z.pdf", file: fakeFile("z.pdf", "B/z.pdf") },
    ]);
    expect(groups.get("A")?.length).toBe(2);
    expect(groups.get("B")?.length).toBe(1);
  });
});

describe("validateFolderUpload", () => {
  it("reuses the caller's validator and reports rejections", () => {
    const validator = (file: File) =>
      file.name === "bad.exe"
        ? { valid: false, error: "EXE files are not allowed." }
        : { valid: true };

    const entries = walkPickedFolder([
      fakeFile("good.pdf", "Docs/good.pdf"),
      fakeFile("bad.exe", "Docs/bad.exe"),
    ]);
    const result = validateFolderUpload(entries, validator);

    expect(result.valid).toBe(true);
    expect(result.batches).toHaveLength(1);
    expect(result.batches[0].folderName).toBe("Docs");
    expect(result.batches[0].files.map((f) => f.name)).toEqual(["good.pdf"]);
    expect(result.rejected).toHaveLength(1);
    expect(result.rejected[0].error).toBe("EXE files are not allowed.");
  });

  it("reports invalid when everything is rejected", () => {
    const result = validateFolderUpload(
      walkPickedFolder([fakeFile("bad.exe", "Docs/bad.exe")]),
      () => ({ valid: false, error: "nope" }),
    );
    expect(result.valid).toBe(false);
    expect(result.batches).toHaveLength(0);
    expect(result.rejected).toHaveLength(1);
  });
});

describe("collectSubfolders", () => {
  it("plans nested folders under the batch root, shallow first", () => {
    const folders = collectSubfolders(
      [
        { relativePath: "Root/sub/inner/a.pdf" },
        { relativePath: "Root/other/b.pdf" },
        { relativePath: "Root/c.pdf" },
      ],
      "Root",
    );
    expect(folders).toEqual(["Root/other", "Root/sub", "Root/sub/inner"]);
  });
});