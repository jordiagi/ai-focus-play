import React, { useState } from "react";
import { StepLayout } from "../../components/StepLayout";
import { createExport, exportDownloadUrl, listExports } from "../../services/exports";
import type { OverlayMode, ReelProfile } from "../projects/guidedTypes";
import { ExportRequestPanel } from "./ExportRequestPanel";
import { OutputList } from "./OutputList";

export function ExportsPage(): JSX.Element {
  const [projectId, setProjectId] = useState("");
  const [form, setForm] = useState({ outputProfile: "short_highlight", overlayMode: "none" });
  const [outputs, setOutputs] = useState<Array<{ outputId: string; exportStatus: string; downloadUri?: string }>>([]);

  async function refreshOutputs() {
    if (!projectId) return;
    const { outputs: items } = await listExports(projectId);
    setOutputs(
      items.map((item) => ({
        outputId: item.output_id,
        exportStatus: item.status,
        downloadUri: item.status === "ready" ? exportDownloadUrl(projectId, item.output_id) : undefined,
      })),
    );
  }

  async function handleCreateExport() {
    if (!projectId) return;
    await createExport(projectId, {
      profile: form.outputProfile as ReelProfile,
      overlay_mode: form.overlayMode as OverlayMode,
    });
    await refreshOutputs();
  }

  return (
    <StepLayout title="Generate exports" subtitle="Choose the reel profile and whether to mark the target player on screen.">
      <label>
        Project ID
        <input value={projectId} onChange={(event) => setProjectId(event.target.value)} />
      </label>
      <ExportRequestPanel
        outputProfile={form.outputProfile}
        overlayMode={form.overlayMode}
        onChange={(field, value) => setForm((current) => ({ ...current, [field]: value }))}
      />
      <button onClick={() => void handleCreateExport()} style={{ margin: "16px 0" }}>
        Create export
      </button>
      <OutputList outputs={outputs} />
    </StepLayout>
  );
}
