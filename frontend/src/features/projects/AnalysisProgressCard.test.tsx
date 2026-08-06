import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach } from "vitest";
import { describe, expect, it, vi } from "vitest";
import { AnalysisProgressCard } from "./AnalysisProgressCard";
import type { PipelineJob } from "./guidedTypes";

afterEach(cleanup);


const job = (overrides: Partial<PipelineJob>): PipelineJob => ({
  job_id: "j1",
  stage: "detect_track",
  status: "running",
  progress_pct: 50,
  progress_message: "Watching the match — 46 of 92 minutes",
  error: null,
  created_at: "now",
  ...overrides,
});


describe("AnalysisProgressCard", () => {
  it("maps internal stages to plain-language progress", () => {
    render(<AnalysisProgressCard jobs={[job({})]} durationS={92 * 60} onRetry={vi.fn()} />);

    expect(screen.getByText("Watching the match")).toBeTruthy();
    expect(screen.getByText("46 of 92 minutes")).toBeTruthy();
    expect(screen.getByText("You don't have to wait — click your player now and we'll match them as we go.")).toBeTruthy();
    expect(screen.getByText("It's safe to close this window — analysis keeps running as long as the app is running.")).toBeTruthy();
    expect(screen.queryByText("detect_track")).toBeNull();
  });

  it("shows the normative safe failure copy and one Retry action", () => {
    const onRetry = vi.fn();
    render(<AnalysisProgressCard jobs={[job({ status: "failed", error: "raw" })]} durationS={100} onRetry={onRetry} />);

    expect(screen.getByText("Something went wrong while watching the match. Your video is fine — tap Retry to pick up where we left off.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("ignores a failed attempt superseded by a successful retry", () => {
    render(
      <AnalysisProgressCard
        jobs={[
          job({ status: "failed", error: "old failure" }),
          job({ job_id: "j2", status: "succeeded", progress_pct: 100, error: null }),
        ]}
        durationS={100}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("Ready — every moment is searchable")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });
});
