import React, { useState } from "react";
import type { CoverageSegment, TimelineResponse } from "./guidedTypes";

export type CoverageTimelineProps = {
  projectId: string;
  timeline: TimelineResponse | null;
  durationS: number;
  onToggleInclude: (segmentId: string, included: boolean) => void;
  onNotThem: (segment: CoverageSegment) => void;
  onStartOver: () => void;
};

function fmt(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function fmtDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return minutes > 0 ? `${minutes}m ${secs}s` : `${secs}s`;
}

function segmentColor(segment: CoverageSegment): string {
  if (!segment.included) return "#9aa79a";
  const span = Math.max(0.001, segment.end_ts - segment.start_ts);
  const density = segment.score / span;
  if (segment.score < 3 || density < 0.5) return "#e0a53d";
  return "#3f7d3a";
}

export function CoverageTimeline(props: CoverageTimelineProps): JSX.Element {
  const { timeline, durationS } = props;
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);

  if (!timeline || timeline.segments.length === 0) {
    return (
      <p style={{ color: "#4a5847" }}>
        No appearances yet — confirm your player to see their coverage.
      </p>
    );
  }

  const segments = timeline.segments;
  const span = Math.max(1, durationS);
  const excludedCount = segments.filter((segment) => !segment.included).length;
  const showEscapeHatch = segments.length > 0 && excludedCount / segments.length > 0.4;
  const selected = segments.find((segment) => segment.segment_id === selectedSegmentId) ?? null;

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <div
        style={{
          position: "relative",
          height: 28,
          width: "100%",
          background: "#dfe6d8",
          borderRadius: 6,
          overflow: "hidden",
        }}
      >
        {segments.map((segment) => (
          <div
            key={segment.segment_id}
            title={`${fmt(segment.start_ts)}–${fmt(segment.end_ts)}`}
            onClick={() =>
              setSelectedSegmentId((current) =>
                current === segment.segment_id ? null : segment.segment_id,
              )
            }
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: `${(segment.start_ts / span) * 100}%`,
              width: `${((segment.end_ts - segment.start_ts) / span) * 100}%`,
              background: segmentColor(segment),
              cursor: "pointer",
              borderRight: "1px solid #ffffff66",
            }}
          />
        ))}
      </div>

      <p style={{ margin: 0, color: "#4a5847" }}>
        {segments.length} stretches · {fmtDuration(timeline.summary.total_s)} total ·{" "}
        {timeline.summary.included_count} in the reel.
      </p>

      {selected ? (
        <div
          style={{
            padding: 14,
            borderRadius: 16,
            background: "#eef2e8",
            color: "#31402f",
            display: "grid",
            gap: 8,
            justifyItems: "start",
          }}
        >
          <img src={selected.thumbnail_uri} alt="" style={{ maxWidth: 200, borderRadius: 8 }} />
          <span>
            {fmt(selected.start_ts)}–{fmt(selected.end_ts)}
          </span>
          <video src={selected.preview_clip_uri} controls style={{ maxWidth: 320 }} />
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              onClick={() => props.onToggleInclude(selected.segment_id, !selected.included)}
            >
              {selected.included ? "Leave out of reel" : "Put back in the reel"}
            </button>
            <button type="button" onClick={() => props.onNotThem(selected)}>
              Not them
            </button>
          </div>
        </div>
      ) : null}

      {showEscapeHatch ? (
        <div
          style={{
            padding: 12,
            borderRadius: 14,
            background: "#f6e9cf",
            color: "#5a4520",
            display: "grid",
            gap: 8,
            justifyItems: "start",
          }}
        >
          <span>
            A lot of these weren't your player. Want to start the match-up over from a fresh click?
          </span>
          <button type="button" onClick={() => props.onStartOver()}>
            Start over
          </button>
        </div>
      ) : null}
    </section>
  );
}
