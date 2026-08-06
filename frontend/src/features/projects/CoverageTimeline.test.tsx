import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import { CoverageTimeline } from "./CoverageTimeline";
import type { TimelineResponse } from "./guidedTypes";

const noop = () => {};

function fixture(): TimelineResponse {
  return {
    summary: { segment_count: 2, total_s: 21, included_count: 1 },
    segments: [
      {
        segment_id: "seg-a",
        start_ts: 3.5,
        end_ts: 11.5,
        score: 8,
        included: true,
        thumbnail_uri: "/projects/p1/evidence-media/segment-seg-a.jpg",
        preview_clip_uri: "/projects/p1/evidence-media/segment-seg-a.mp4",
      },
      {
        segment_id: "seg-b",
        start_ts: 38.5,
        end_ts: 51.5,
        score: 13,
        included: false,
        thumbnail_uri: "/projects/p1/evidence-media/segment-seg-b.jpg",
        preview_clip_uri: "/projects/p1/evidence-media/segment-seg-b.mp4",
      },
    ],
  };
}

describe("CoverageTimeline", () => {
  test("renders the empty state when there is no timeline", () => {
    const html = renderToStaticMarkup(
      <CoverageTimeline
        projectId="p1"
        timeline={null}
        durationS={120}
        onToggleInclude={noop}
        onNotThem={noop}
        onStartOver={noop}
      />,
    );
    expect(html).toContain("No appearances yet");
  });

  test("summarises coverage and positions each segment", () => {
    const html = renderToStaticMarkup(
      <CoverageTimeline
        projectId="p1"
        timeline={fixture()}
        durationS={120}
        onToggleInclude={noop}
        onNotThem={noop}
        onStartOver={noop}
      />,
    );
    expect(html).toContain("in the reel");
    expect(html).toContain("2 stretches");
    expect(html).toContain("1 in the reel");
    // Both segments rendered as positioned bars.
    expect(html).toContain("2.916");
    expect(html).toContain("32.083");
  });
});
