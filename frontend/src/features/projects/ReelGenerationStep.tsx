import React, { useEffect, useState } from "react";
import { createExport, exportDownloadUrl, listExports } from "../../services/exports";
import { adjustTarget, getTimeline, patchTimelineSegment, resetTarget } from "../../services/projects";
import { CoverageTimeline } from "./CoverageTimeline";
import type {
  CoverageSegment,
  OverlayMode,
  ReelExportItem,
  ReelProfile,
  TimelineResponse,
} from "./guidedTypes";

type Props = {
  projectId: string;
  confirmed: boolean;
  durationS?: number;
  onStartOver?: () => void;
};

const PROFILE_LABELS: Record<ReelProfile, string> = {
  short_highlight: "Short highlight",
  medium_best_plays: "Medium best plays",
  full_appearances: "Full appearances",
};

export function ReelGenerationStep({ projectId, confirmed, durationS, onStartOver }: Props): JSX.Element {
  const [profile, setProfile] = useState<ReelProfile>("short_highlight");
  const [targetMarker, setTargetMarker] = useState(false);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [exports, setExports] = useState<ReelExportItem[]>([]);
  const [message, setMessage] = useState(
    confirmed ? "Choose the reel output." : "Confirm the player before generating reels.",
  );

  async function refreshTimeline(): Promise<void> {
    try {
      setTimeline(await getTimeline(projectId));
    } catch {
      /* timeline not ready yet — leave as null */
    }
  }

  async function refreshExports(): Promise<void> {
    try {
      setExports((await listExports(projectId)).outputs);
    } catch {
      /* no exports yet */
    }
  }

  useEffect(() => {
    if (!confirmed) return;
    void refreshTimeline();
    void refreshExports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmed, projectId]);

  const effectiveDuration =
    durationS && durationS > 0
      ? durationS
      : Math.max(1, ...(timeline?.segments ?? []).map((segment) => segment.end_ts), 1);

  async function handleToggleInclude(segmentId: string, included: boolean): Promise<void> {
    await patchTimelineSegment(projectId, segmentId, { included });
    await refreshTimeline();
  }

  async function handleNotThem(segment: CoverageSegment): Promise<void> {
    const trackletIds = segment.tracklet_ids ?? [];
    if (trackletIds.length > 0) {
      await adjustTarget(projectId, { remove_tracklet_ids: trackletIds });
    } else {
      await patchTimelineSegment(projectId, segment.segment_id, { included: false });
    }
    await refreshTimeline();
  }

  async function handleStartOver(): Promise<void> {
    await resetTarget(projectId);
    onStartOver?.();
  }

  async function generate(): Promise<void> {
    if (!confirmed) {
      setMessage("Player confirmation is required before generating reels.");
      return;
    }
    const overlay_mode: OverlayMode = targetMarker ? "target_marker" : "none";
    try {
      setMessage("Cutting your clips and stitching them together…");
      const { output_id } = await createExport(projectId, { profile, overlay_mode });
      // Poll the exports list until this reel is ready.
      for (let attempt = 0; attempt < 600; attempt += 1) {
        const outputs = (await listExports(projectId)).outputs;
        setExports(outputs);
        const mine = outputs.find((item) => item.output_id === output_id);
        if (mine?.status === "ready") {
          setMessage("Your reel is ready to download below.");
          return;
        }
        if (mine?.status === "failed") {
          setMessage("Something went wrong rendering this reel. Your video is fine — try again.");
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      setMessage("Your reel is still rendering — check the list below in a moment.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not generate this reel.");
    }
  }

  return (
    <section style={{ display: "grid", gap: 18 }}>
      <div>
        <p style={{ margin: 0, color: "#66745e", textTransform: "uppercase", letterSpacing: 1.4 }}>Step 3</p>
        <h2 style={{ fontSize: 34, margin: "6px 0" }}>Build the reel</h2>
        <p style={{ margin: 0, color: "#4a5847" }}>
          Review where we found your player, leave out anything that isn't them, then generate the reel.
        </p>
      </div>

      {confirmed ? (
        <CoverageTimeline
          projectId={projectId}
          timeline={timeline}
          durationS={effectiveDuration}
          onToggleInclude={(segmentId, included) => void handleToggleInclude(segmentId, included)}
          onNotThem={(segment) => void handleNotThem(segment)}
          onStartOver={() => void handleStartOver()}
        />
      ) : null}

      <label>
        Reel length
        <select
          value={profile}
          onChange={(event) => setProfile(event.target.value as ReelProfile)}
          style={{ display: "block", padding: 12, borderRadius: 14, border: "1px solid #bac8b4" }}
        >
          {(Object.keys(PROFILE_LABELS) as ReelProfile[]).map((key) => (
            <option key={key} value={key}>
              {PROFILE_LABELS[key]}
            </option>
          ))}
        </select>
      </label>

      <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input type="checkbox" checked={targetMarker} onChange={(event) => setTargetMarker(event.target.checked)} />
        Show a marker that follows the identified player
      </label>

      <button
        type="button"
        disabled={!confirmed}
        onClick={() => void generate()}
        style={{
          justifySelf: "start",
          padding: "12px 18px",
          borderRadius: 999,
          border: 0,
          background: confirmed ? "#172517" : "#7d8778",
          color: "#f8f1df",
          fontWeight: 700,
        }}
      >
        Generate reel
      </button>

      <p style={{ color: "#586653" }}>{message}</p>

      {exports.length > 0 ? (
        <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 8 }}>
          {exports.map((item) => (
            <li key={item.output_id} style={{ padding: 12, borderRadius: 14, background: "#eef2e8", color: "#31402f" }}>
              <strong>{PROFILE_LABELS[item.profile as ReelProfile] ?? item.profile}</strong> — {item.status}
              {item.status === "ready" ? (
                <>
                  {" · "}
                  <a href={exportDownloadUrl(projectId, item.output_id)}>Download</a>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
