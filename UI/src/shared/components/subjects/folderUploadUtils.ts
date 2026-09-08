/**
 * Folder upload helpers (Task 3.2.3) — pure functions for bulk folder upload.
 *
 * A picked folder (via `<input webkitdirectory>` or the File System Access
 * API) is walked into { relativePath, file } entries, grouped by their
 * original subfolder, and validated with the SAME file-type/size rules the
 * Subject Explorer already uses (FileService.validateUploadCandidate) — no
 * second validator is introduced.
 */

export interface FolderUploadFile {
  /** Original folder-relative path, e.g. "Consent Forms/ICF v2/icf.pdf". */
  relativePath: string;
  /** Top-level folder name the file belongs to (first path segment). */
  folderName: string;
  file: File;
}

export interface FolderUploadBatch {
  folderName: string;
  files: File[];
}

export interface FolderUploadValidationResult {
  valid: boolean;
  /** Folder batches that passed validation. */
  batches: FolderUploadBatch[];
  /** Files that were rejected, with the reason. */
  rejected: Array<{ relativePath: string; error: string }>;
}

/** Normalize a file's relative path from a webkitdirectory FileList. */
export function relativePathOf(file: File): string {
  const raw = String((file as any).webkitRelativePath || "");
  // Strip any leading "./" and normalize separators.
  return raw.replace(/\\/g, "/").replace(/^\.\//, "");
}

/** Group picked files by their original top-level subfolder. */
export function groupFilesByFolder(files: Array<{ relativePath: string; file: File }>): Map<string, File[]> {
  const groups = new Map<string, File[]>();
  for (const entry of files) {
    const folderName = entry.relativePath.split("/")[0] || "(root)";
    const list = groups.get(folderName) || [];
    list.push(entry.file);
    groups.set(folderName, list);
  }
  return groups;
}

/** Walk a webkitdirectory FileList into { relativePath, folderName, file }. */
export function walkPickedFolder(files: FileList | File[]): FolderUploadFile[] {
  return Array.from(files || [])
    .map((file) => {
      const relativePath = relativePathOf(file);
      const folderName = relativePath.split("/")[0] || "(root)";
      return { relativePath, folderName, file };
    })
    .filter((entry) => entry.relativePath);
}

/**
 * Recursively walk a File System Access API directory entry into files,
 * preserving relative paths. Falls back to `file.webkitRelativePath` when
 * the entry API is unavailable.
 */
export async function walkDirectoryEntry(
  entry: any,
  basePath = "",
  files: FolderUploadFile[] = [],
): Promise<FolderUploadFile[]> {
  if (!entry) return files;
  if (entry.isFile) {
    const file: File = await new Promise((resolve, reject) => {
      entry.file(resolve, reject);
    });
    const relativePath = basePath ? `${basePath}/${file.name}` : file.name;
    files.push({
      relativePath,
      folderName: relativePath.split("/")[0] || "(root)",
      file,
    });
    return files;
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    const readAll = async (): Promise<any[]> => {
      const batch = await new Promise<any[]>((resolve, reject) => {
        reader.readEntries(resolve, reject);
      });
      if (batch.length === 0) return batch;
      return [...batch, ...(await readAll())];
    };
    const children = await readAll();
    for (const child of children) {
      await walkDirectoryEntry(child, basePath ? `${basePath}/${entry.name}` : entry.name, files);
    }
  }
  return files;
}

/**
 * Validate a picked folder and produce per-subfolder upload batches, reusing
 * the caller's validateUploadCandidate (FileService.validateUploadCandidate).
 */
export function validateFolderUpload(
  entries: FolderUploadFile[],
  validateCandidate: (file: File) => { valid: boolean; error?: string },
): FolderUploadValidationResult {
  const validFiles: Array<{ relativePath: string; file: File }> = [];
  const rejected: Array<{ relativePath: string; error: string }> = [];

  for (const entry of entries) {
    const result = validateCandidate(entry.file);
    if (result && result.valid) {
      validFiles.push({ relativePath: entry.relativePath, file: entry.file });
    } else {
      rejected.push({
        relativePath: entry.relativePath,
        error: (result && result.error) || "File rejected by upload rules.",
      });
    }
  }

  const groups = groupFilesByFolder(validFiles);
  const batches: FolderUploadBatch[] = Array.from(groups.entries()).map(
    ([folderName, files]) => ({ folderName, files }),
  );

  return {
    valid: validFiles.length > 0,
    batches,
    rejected,
  };
}

/**
 * Flatten nested paths into a folder-creation plan: for a batch rooted at
 * `<subjectId>/<folderName>`, the files' relative paths may contain deeper
 * subfolders; this returns the ordered list of folders to create under the
 * subject (relative to the batch root) so uploadFiles can land each file in
 * its correctly-named subfolder.
 */
export function collectSubfolders(batchFiles: Array<{ relativePath: string }>, rootFolderName: string): string[] {
  const folders = new Set<string>();
  const root = rootFolderName || "";
  for (const entry of batchFiles) {
    const parts = entry.relativePath.split("/");
    // parts[0] is the root folder; the LAST segment is the file name — only
    // directory prefixes in between are folders to create.
    for (let i = 1; i < parts.length - 1; i++) {
      const path = root ? `${root}/${parts.slice(1, i + 1).join("/")}` : parts.slice(0, i + 1).join("/");
      folders.add(path);
    }
  }
  return Array.from(folders).sort((a, b) => {
    const depth = a.split("/").length - b.split("/").length;
    return depth !== 0 ? depth : a.localeCompare(b);
  });
}