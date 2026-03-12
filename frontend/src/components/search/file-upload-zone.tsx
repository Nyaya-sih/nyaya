"use client";

import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { FileText, UploadCloud, X } from "lucide-react";
import { useSearchStore } from "@/lib/stores/search-store";

const ACCEPTED_FORMATS = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
};
const MAX_FILE_SIZE = 50 * 1024 * 1024;

export function FileUploadZone() {
  const uploadedFile = useSearchStore((state) => state.uploadedFile);
  const setUploadedFile = useSearchStore((state) => state.setUploadedFile);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      if (fileRejections.length) {
        setError(fileRejections[0].errors[0]?.message ?? "Invalid file");
        return;
      }
      setError(null);
      setUploadedFile(acceptedFiles[0] ?? null);
    },
    [setUploadedFile]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FORMATS,
    maxSize: MAX_FILE_SIZE,
    multiple: false,
  });

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <div
        {...getRootProps()}
        className={`flex min-h-[220px] cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
          isDragActive
            ? "border-[var(--accent-400)] bg-[var(--accent-50)]"
            : "border-[var(--border)]"
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--surface-alt)]">
          {uploadedFile ? <FileText className="h-6 w-6" /> : <UploadCloud className="h-6 w-6" />}
        </div>
        <div>
          <p className="text-sm font-semibold text-[var(--primary-900)]">
            {uploadedFile ? uploadedFile.name : "Drop PDF or DOCX here"}
          </p>
          <p className="text-xs text-[var(--neutral-500)]">Max 50MB • PDF, DOCX</p>
        </div>
      </div>

      {uploadedFile && (
        <div className="mt-4 flex items-center justify-between rounded-xl border border-[var(--border)] px-4 py-3 text-xs text-[var(--neutral-600)]">
          <span>{uploadedFile.name}</span>
          <button type="button" onClick={() => setUploadedFile(null)}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {error && <p className="mt-3 text-xs text-[var(--danger)]">{error}</p>}
    </div>
  );
}
