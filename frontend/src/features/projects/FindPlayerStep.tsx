import React, { useEffect, useState } from "react";
import {
  getCandidates,
  getClicks,
  getJobs,
  postClick,
  putJerseyHint,
  runPipeline,
} from "../../services/projects";
import { AnalysisProgressCard } from "./AnalysisProgressCard";
import { FrameClickSelector } from "./FrameClickSelector";
import { IdentityEvidenceStrip } from "./IdentityEvidenceStrip";
import type {
  CoverageSummary,
  GuidedProject,
  IdentityCandidate,
  PipelineJob,
  PlayerClick,
} from "./guidedTypes";


type Props = {
  project: GuidedProject;
  onContinue: () => void;
};


const NO_PLAYER_MESSAGE = "We don't see a player there — try clicking directly on their body.";


export function latestJobsByStage(jobs: PipelineJob[]): PipelineJob[] {
  const latest = new Map<PipelineJob["stage"], PipelineJob>();
  for (const job of jobs) latest.set(job.stage, job);
  return [...latest.values()];
}


function formatDuration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(whole / 60);
  const remainder = whole % 60;
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
}


export function FindPlayerStep({ project, onContinue }: Props): JSX.Element {
  const projectId = project.project_id;
  const durationS = Number(project.source?.duration_s ?? 0);
  const [jobs, setJobs] = useState<PipelineJob[]>(project.analysis?.stages ?? []);
  const [candidate, setCandidate] = useState<IdentityCandidate | null>(null);
  const [selectedTrackletId, setSelectedTrackletId] = useState<string | null>(null);
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);
  const [focusTimestamp, setFocusTimestamp] = useState<number | null>(null);
  const [pendingPoint, setPendingPoint] = useState<{ x_norm: number; y_norm: number } | null>(null);
  const [clicks, setClicks] = useState<PlayerClick[]>([]);
  const [message, setMessage] = useState("");
  const [toast, setToast] = useState("");
  const [jerseyHint, setJerseyHint] = useState(project.jersey_hint ?? "");
  const [coverage, setCoverage] = useState<CoverageSummary | null>(null);
  const [pollGeneration, setPollGeneration] = useState(0);

  async function loadCandidate(
    clusterId: string,
    anchorTrackletId: string | null = selectedTrackletId,
    anchorTimestamp: number | null = focusTimestamp,
  ) {
    const response = await getCandidates(
      projectId,
      clusterId,
      anchorTrackletId,
      anchorTimestamp,
    );
    setCandidate(response.candidates[0] ?? null);
  }

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const [jobResponse, clickResponse] = await Promise.all([
          getJobs(projectId),
          getClicks(projectId),
        ]);
        if (!active) return;
        const currentJobs = latestJobsByStage(jobResponse.jobs);
        setJobs(currentJobs);
        setClicks(clickResponse.clicks);
        const latestPositive = [...clickResponse.clicks].reverse().find(
          (click) => click.label === "positive",
        );
        if (latestPositive?.status === "resolved" && latestPositive.cluster_id) {
          setSelectedTrackletId(latestPositive.resolved_tracklet_id ?? null);
          setSelectedClusterId(latestPositive.cluster_id);
          setFocusTimestamp(latestPositive.t);
          setPendingPoint(null);
          setToast("");
          await loadCandidate(
            latestPositive.cluster_id,
            latestPositive.resolved_tracklet_id ?? null,
            latestPositive.t,
          );
        } else if (latestPositive?.status === "pinned" || latestPositive?.status === "refining") {
          setFocusTimestamp(latestPositive.t);
          setPendingPoint(null);
          setToast("");
        } else if (latestPositive?.status === "no_player") {
          setPendingPoint(null);
          setToast(NO_PLAYER_MESSAGE);
        }
        if (currentJobs.some((job) => job.status === "queued" || job.status === "running")) {
          timer = window.setTimeout(poll, 2000);
        }
      } catch {
        if (active) timer = window.setTimeout(poll, 2000);
      }
    };
    void poll();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [projectId, pollGeneration]);

  async function handlePlayerClick(click: { t: number; x_norm: number; y_norm: number }) {
    setMessage("");
    setToast("");
    const result = await postClick(projectId, { ...click, label: "positive" });
    if (result.resolution === "tracklet") {
      setSelectedTrackletId(result.tracklet_id);
      setSelectedClusterId(result.cluster_id);
      setFocusTimestamp(click.t);
      setPendingPoint(null);
      setMessage("Locked on. Matching them across the rest of the match…");
      if (result.cluster_id) {
        await loadCandidate(result.cluster_id, result.tracklet_id, click.t);
      }
    } else if (result.resolution === "pinned") {
      setPendingPoint({ x_norm: click.x_norm, y_norm: click.y_norm });
      setMessage(result.message);
    } else if (result.resolution === "sam2_queued") {
      setPendingPoint({ x_norm: click.x_norm, y_norm: click.y_norm });
      setMessage("Taking a closer look at that moment…");
      setPollGeneration((value) => value + 1);
    } else {
      setToast(result.message);
    }
  }

  async function saveJerseyHint(value: string) {
    const digits = value.replace(/\D/g, "").slice(0, 3);
    setJerseyHint(digits);
    await putJerseyHint(projectId, digits || null);
    if (candidate) await loadCandidate(candidate.cluster_id);
  }

  async function retry() {
    await runPipeline(projectId);
    setPollGeneration((value) => value + 1);
  }

  return (
    <section style={{ display: "grid", gap: 18 }}>
      <AnalysisProgressCard jobs={jobs} durationS={durationS} onRetry={() => void retry()} />
      <FrameClickSelector
        projectId={projectId}
        durationS={durationS}
        onPlayerClick={(click) => void handlePlayerClick(click)}
        selectedTrackletId={selectedTrackletId}
        selectedClusterId={selectedClusterId}
        focusTimestamp={focusTimestamp}
        pendingPoint={pendingPoint}
        pendingClicks={clicks.filter(
          (click) => click.label === "positive" && (click.status === "pinned" || click.status === "refining"),
        )}
      />
      {message ? <p role="status" style={{ margin: 0 }}>{message}</p> : null}
      {toast ? <p role="alert" style={{ margin: 0, color: "#7d261f" }}>{toast}</p> : null}

      <label style={{ display: "grid", gap: 6, maxWidth: 320 }}>
        <span>Jersey number (optional) — helps us double-check.</span>
        <input
          aria-label="Jersey number (optional) — helps us double-check."
          inputMode="numeric"
          value={jerseyHint}
          onChange={(event) => void saveJerseyHint(event.target.value)}
          style={{ minHeight: 40, padding: "6px 10px" }}
        />
      </label>
      {project.analysis?.no_readable_jersey_numbers ? (
        <p style={{ margin: 0, color: "#4c5750" }}>
          We couldn't read jersey numbers in this footage — no problem, your click is what matters.
        </p>
      ) : null}

      {candidate ? (
        <IdentityEvidenceStrip
          projectId={projectId}
          candidate={candidate}
          clickedTrackletId={selectedTrackletId}
          jerseyHint={jerseyHint || null}
          onRefresh={() => loadCandidate(candidate.cluster_id)}
          onConfirmed={setCoverage}
        />
      ) : null}

      {coverage ? (
        <section aria-label="Player coverage" style={{ display: "grid", gap: 8, borderTop: "1px solid #d6dbd5", paddingTop: 16 }}>
          <strong>Found them in {coverage.segment_count} stretches — {formatDuration(coverage.total_s)} of the match.</strong>
          {coverage.total_s < 180 ? (
            <p style={{ margin: 0 }}>We only found them clearly for {formatDuration(coverage.total_s)}. The reel will be short. You can scrub and click them in more moments to help us.</p>
          ) : null}
          <button type="button" onClick={onContinue} style={{ justifySelf: "start" }}>Continue to build the reel</button>
        </section>
      ) : null}
    </section>
  );
}
