import React from "react";

export function ExportRequestPanel({
  outputProfile,
  overlayMode,
  identitySummary = "Exports require a confirmed real evidence-backed player identity.",
  onChange,
}: {
  outputProfile: string;
  overlayMode: string;
  identitySummary?: string;
  onChange: (field: string, value: string) => void;
}): JSX.Element {
  return (
    <section>
      <h2>Request exports</h2>
      <p>{identitySummary}</p>
      <label>
        Reel length
        <select value={outputProfile} onChange={(event) => onChange("outputProfile", event.target.value)}>
          <option value="short_highlight">Short highlight</option>
          <option value="medium_best_plays">Medium best plays</option>
        </select>
      </label>
      <label>
        Overlay mode
        <select value={overlayMode} onChange={(event) => onChange("overlayMode", event.target.value)}>
          <option value="none">No marker</option>
          <option value="target_marker">Show target marker</option>
        </select>
      </label>
    </section>
  );
}
