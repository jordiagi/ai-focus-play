import React, { useEffect, useRef, useState } from "react";
import { listLocalSources } from "../../services/sources";
import type { SourceCatalogItem } from "./guidedTypes";


export type VideoSourceSelection = { file: File } | { file_path: string };

type Props = {
  onContinue: (payload: VideoSourceSelection) => Promise<void>;
  disabled?: boolean;
};


export function VideoSourceStep({ onContinue, disabled }: Props): JSX.Element {
  const [items, setItems] = useState<SourceCatalogItem[]>([]);
  const [selectedPath, setSelectedPath] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"upload" | "local">("upload");
  const [message, setMessage] = useState("Choose an MP4 from this Mac.");
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    listLocalSources()
      .then((catalog) => {
        if (!active) return;
        setItems(catalog.items);
        setSelectedPath(catalog.items[0]?.relative_path ?? "");
      })
      .catch(() => {
        if (active) setItems([]);
      });
    return () => {
      active = false;
    };
  }, []);

  async function submit() {
    const selection = mode === "upload" && file ? { file } : mode === "local" && selectedPath ? { file_path: selectedPath } : null;
    if (!selection) return;
    setSubmitting(true);
    try {
      await onContinue(selection);
      setMessage("Video accepted. Analysis is starting in the background.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "That file doesn't look like a playable video. Your file wasn't changed — try re-exporting it as MP4.");
    } finally {
      setSubmitting(false);
    }
  }

  const canContinue = mode === "upload" ? Boolean(file) : Boolean(selectedPath);
  return (
    <section style={{ display: "grid", gap: 16 }}>
      <header>
        <h2 style={{ fontSize: 24, margin: "0 0 6px" }}>Add video</h2>
        <p style={{ margin: 0, color: "#4a5847" }}>Choose the match recording from this Mac.</p>
      </header>
      <div role="tablist" aria-label="Video source" style={{ display: "flex", gap: 4 }}>
        <button type="button" role="tab" aria-selected={mode === "upload"} onClick={() => setMode("upload")}>Upload file</button>
        <button type="button" role="tab" aria-selected={mode === "local"} onClick={() => setMode("local")}>Video folder</button>
      </div>
      {mode === "upload" ? (
        <div
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            const next = event.dataTransfer.files[0];
            if (next) {
              setFile(next);
              setMessage(next.name);
            }
          }}
          style={{ border: "1px dashed #8d9990", padding: 24, textAlign: "center" }}
        >
          <input
            ref={inputRef}
            aria-label="Match video file"
            type="file"
            accept="video/mp4,video/quicktime,video/x-matroska"
            onChange={(event) => {
              const next = event.target.files?.[0] ?? null;
              setFile(next);
              if (next) setMessage(next.name);
            }}
          />
        </div>
      ) : (
        <label style={{ display: "grid", gap: 6 }}>
          Local videos
          <select value={selectedPath} onChange={(event) => setSelectedPath(event.target.value)}>
            {items.length === 0 ? <option value="">No local videos found</option> : null}
            {items.map((item) => <option key={item.catalog_id} value={item.relative_path}>{item.display_name}</option>)}
          </select>
        </label>
      )}
      <p style={{ margin: 0, color: "#586653", fontSize: 14 }}>{message}</p>
      <div style={{ display: "grid", gap: 8, justifyItems: "start" }}>
        <button type="button" disabled={disabled || submitting || !canContinue} onClick={() => void submit()}>
          {submitting ? "Adding video…" : "Continue"}
        </button>
        <small>We'll watch the whole match — this can take a while (it's fine to leave it overnight). You can start finding your player right away.</small>
      </div>
    </section>
  );
}
