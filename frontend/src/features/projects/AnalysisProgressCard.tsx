import React from "react";
import type { AnalysisStage, PipelineJob } from "./guidedTypes";


const labels: Record<AnalysisStage, string> = {
  proxy: "Getting the video ready",
  detect_track: "Watching the match",
  embed_cluster: "Learning what each player looks like",
  jersey_ocr: "Reading jersey numbers",
  assemble_candidates: "Lining up who we found",
  sam2_refine: "Taking a closer look",
  export: "Building the reel",
  sleep_demo: "Preparing background work",
};


type Props = {
  jobs: PipelineJob[];
  durationS: number;
  onRetry: () => void;
};


export function AnalysisProgressCard({ jobs, durationS, onRetry }: Props): JSX.Element {
  const latestByStage = new Map<AnalysisStage, PipelineJob>();
  jobs.forEach((job) => latestByStage.set(job.stage, job));
  const currentJobs = [...latestByStage.values()];
  const failed = currentJobs.some((job) => job.status === "failed");
  const active = currentJobs.find((job) => job.status === "running") ?? currentJobs.find((job) => job.status === "queued");
  const complete = currentJobs.length > 0 && currentJobs.every((job) => job.status === "succeeded");

  if (failed) {
    return (
      <section aria-label="Analysis progress" style={{ border: "1px solid #d9b66d", padding: 14, borderRadius: 6, display: "grid", gap: 10 }}>
        <p style={{ margin: 0 }}>Something went wrong while watching the match. Your video is fine — tap Retry to pick up where we left off.</p>
        <button type="button" onClick={onRetry} style={{ justifySelf: "start" }}>Retry</button>
      </section>
    );
  }

  const detail = active?.stage === "detect_track"
    ? `${Math.round((durationS * active.progress_pct) / 6000)} of ${Math.round(durationS / 60)} minutes`
    : active?.progress_message;

  return (
    <section aria-label="Analysis progress" style={{ border: "1px solid #d8ddd8", padding: 14, borderRadius: 6, display: "grid", gap: 6 }}>
      <strong>{complete ? "Ready — every moment is searchable" : active ? labels[active.stage] : "Getting ready to watch the match"}</strong>
      {detail ? <span>{detail}</span> : null}
      {!complete ? <p style={{ margin: 0, color: "#4a554e" }}>You don't have to wait — click your player now and we'll match them as we go.</p> : null}
      {!complete ? <p style={{ margin: 0, color: "#4a554e" }}>It's safe to close this window — analysis keeps running as long as the app is running.</p> : null}
    </section>
  );
}
