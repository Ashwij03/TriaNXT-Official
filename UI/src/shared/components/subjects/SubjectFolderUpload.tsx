import { useRef, useState } from "react";
import { MdFolderOpen } from "react-icons/md";

import {
  FolderUploadBatch,
  validateFolderUpload,
  walkDirectoryEntry,
  walkPickedFolder,
} from "./folderUploadUtils";
import "./SubjectFolderUpload.css";

/**
 * SubjectFolderUpload — bulk FOLDER upload control.
 *
 * Distinct from the single/multi-FILE drag-drop (DragDropUpload.tsx): lets
 * the user pick or drag an entire local folder, preserving the folder's
 * relative path structure. Uses the browser's `webkitdirectory` input (the
 * same hidden-input approach as FileUploadButton.tsx) and validates every
 * file with the caller-supplied validateUploadCandidate (the SAME rules
 * fileService.ts uses — no second validator).
 *
 * The component stays presentational: it produces validated per-subfolder
 * batches and hands them to `onSubmit`. The caller owns folder creation +
 * upload persistence (SubjectFileManager wires it: create each subfolder,
 * then FileService.uploadFiles per batch under one signature).
 *
 * Props
 *   onSubmit        (batches: FolderUploadBatch[]) => void | Promise<void>
 *   validateFile    (file) => { valid, error? }   — FileService.validateUploadCandidate
 *   disabled        blocks the picker
 *   busy            shows the in-flight label
 */
function SubjectFolderUpload({
  onSubmit,
  validateFile,
  disabled = false,
  busy = false,
  label = "Upload Folder",
}: any) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [feedback, setFeedback] = useState<{ tone: string; message: string } | null>(null);

  const handleChange = async (event) => {
    const { files } = event.target;
    setFeedback(null);
    if (!files || files.length === 0) return;

    try {
      const picked = walkPickedFolder(files);
      const result = validateFolderUpload(picked, validateFile || (() => ({ valid: true })));
      if (!result.valid && result.rejected.length === picked.length) {
        setFeedback({
          tone: "error",
          message: `No valid files found — ${result.rejected[0].error}`,
        });
        return;
      }
      const batches: FolderUploadBatch[] = result.batches;
      if (batches.length === 0) {
        setFeedback({ tone: "error", message: "No valid files to upload." });
        return;
      }
      await onSubmit?.(batches, result.rejected);
      if (result.rejected.length > 0) {
        setFeedback({
          tone: "warning",
          message: `${batches.length} ${batches.length === 1 ? "folder" : "folders"} ready; ${result.rejected.length} file(s) skipped.`,
        });
      }
    } catch (err) {
      setFeedback({
        tone: "error",
        message: (err && (err as any).message) || "The folder could not be read.",
      });
    } finally {
      // Allow re-selecting the same folder (browsers skip unchanged values).
      event.target.value = "";
    }
  };

  return (
    <span className="sfu-root">
      <input
        ref={inputRef}
        type="file"
        multiple
        style={{ display: "none" }}
        onChange={handleChange}
        aria-label="Upload a folder of subject documents"
        // webkitdirectory is the browser folder-picker attribute (not in
        // React's InputHTMLAttributes types) — spread via a cast.
        {...({ webkitdirectory: "", directory: "" } as any)}
      />
      <button
        type="button"
        className="sf-btn sfu-button"
        disabled={disabled || busy}
        onClick={() => inputRef.current?.click()}
        title="Upload an entire folder, preserving its subfolder structure"
      >
        <MdFolderOpen size={15} aria-hidden="true" />
        {busy ? "Uploading…" : label}
      </button>
      {feedback && (
        <span className={`sfu-feedback sfu-feedback--${feedback.tone}`} role="status">
          {feedback.message}
        </span>
      )}
    </span>
  );
}

export default SubjectFolderUpload;