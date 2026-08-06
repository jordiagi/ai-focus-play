import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FindPlayerStep } from "./FindPlayerStep";
import type { GuidedProject, IdentityCandidate } from "./guidedTypes";


const serviceMocks = vi.hoisted(() => ({
  getJobs: vi.fn(),
  getClicks: vi.fn(),
  postClick: vi.fn(),
  getCandidates: vi.fn(),
  runPipeline: vi.fn(),
  putJerseyHint: vi.fn(),
}));

vi.mock("../../services/projects", async () => {
  const actual = await vi.importActual<typeof import("../../services/projects")>("../../services/projects");
  return { ...actual, ...serviceMocks };
});

vi.mock("./FrameClickSelector", () => ({
  FrameClickSelector: ({ onPlayerClick, selectedClusterId, focusTimestamp, pendingClicks }: {
    onPlayerClick: (click: { t: number; x_norm: number; y_norm: number }) => void;
    selectedClusterId?: string | null;
    focusTimestamp?: number | null;
    pendingClicks?: Array<{ status: string }>;
  }) => (
    <div
      data-testid="frame-selector"
      data-cluster={selectedClusterId ?? ""}
      data-focus={focusTimestamp ?? ""}
      data-pending={pendingClicks?.map((click) => click.status).join(",") ?? ""}
    >
      <button type="button" onClick={() => onPlayerClick({ t: 12, x_norm: 0.5, y_norm: 0.5 })}>Click frame</button>
    </div>
  ),
}));

const project: GuidedProject = {
  project_id: "p1",
  status: "analyzing",
  target_cluster_id: null,
  jersey_hint: null,
  source: { duration_s: 90 },
  analysis: { overall_status: "running", stages: [], no_readable_jersey_numbers: false },
};

const candidate: IdentityCandidate = {
  cluster_id: "cluster-1",
  jersey_number: null,
  jersey_agreement: { readings: 0, agrees_with_hint: null },
  kit_color_name: "blue",
  screen_time_s: 12,
  tracklet_count: 1,
  rep_crop_uri: "/projects/p1/evidence-media/rep.jpg",
  evidence: [],
  timeline_spans: [],
};


describe("FindPlayerStep", () => {
  beforeEach(() => {
    serviceMocks.getJobs.mockReset().mockResolvedValue({ jobs: [] });
    serviceMocks.getClicks.mockReset().mockResolvedValue({ clicks: [] });
    serviceMocks.getCandidates.mockReset().mockResolvedValue({ candidates: [candidate] });
    serviceMocks.runPipeline.mockReset().mockResolvedValue({ jobs_queued: [] });
    serviceMocks.putJerseyHint.mockReset().mockResolvedValue({ jersey_hint: "8" });
    serviceMocks.postClick.mockReset();
  });

  afterEach(cleanup);

  it.each([
    [
      { click_id: "c1", resolution: "pinned", message: "Got them — we'll match this player across the match as we finish watching." },
      "Got them — we'll match this player across the match as we finish watching.",
    ],
    [
      { click_id: "c1", resolution: "sam2_queued", job_id: "j1" },
      "Taking a closer look at that moment…",
    ],
    [
      { click_id: "c1", resolution: "no_player_here", message: "We don't see a player there — try clicking directly on their body." },
      "We don't see a player there — try clicking directly on their body.",
    ],
  ])("renders click feedback for %s", async (response, expected) => {
    serviceMocks.postClick.mockResolvedValue(response);
    render(<FindPlayerStep project={project} onContinue={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Click frame" }));

    await waitFor(() => expect(screen.getByText(expected)).toBeTruthy());
  });

  it("loads matched evidence and saves the optional jersey hint", async () => {
    serviceMocks.postClick.mockResolvedValue({
      click_id: "c1",
      resolution: "tracklet",
      tracklet_id: "t1",
      cluster_id: "cluster-1",
      box: { x: 0.4, y: 0.3, w: 0.2, h: 0.4 },
    });
    render(<FindPlayerStep project={project} onContinue={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Click frame" }));
    await waitFor(() => expect(screen.getByText("We think this is your player.")).toBeTruthy());
    expect(serviceMocks.getCandidates).toHaveBeenCalledWith("p1", "cluster-1", "t1", 12);

    fireEvent.change(screen.getByLabelText("Jersey number (optional) — helps us double-check."), { target: { value: "8" } });
    await waitFor(() => expect(serviceMocks.putJerseyHint).toHaveBeenCalledWith("p1", "8"));
  });

  it("shows the neutral no-readable-numbers message", () => {
    render(
      <FindPlayerStep
        project={{ ...project, analysis: { ...project.analysis!, no_readable_jersey_numbers: true } }}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.getByText("We couldn't read jersey numbers in this footage — no problem, your click is what matters.")).toBeTruthy();
  });

  it("restores the viewer to the latest resolved selection", async () => {
    serviceMocks.getClicks.mockResolvedValue({
      clicks: [
        {
          click_id: "c1",
          t: 42,
          x_norm: 0.5,
          y_norm: 0.5,
          label: "positive",
          status: "resolved",
          resolved_tracklet_id: "t1",
          cluster_id: "cluster-1",
        },
      ],
    });

    render(<FindPlayerStep project={project} onContinue={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("frame-selector").getAttribute("data-cluster")).toBe("cluster-1");
      expect(screen.getByTestId("frame-selector").getAttribute("data-focus")).toBe("42");
    });
  });

  it("restores an in-progress refinement and its pinned timestamp", async () => {
    serviceMocks.getClicks.mockResolvedValue({
      clicks: [
        {
          click_id: "c1",
          t: 36,
          x_norm: 0.25,
          y_norm: 0.4,
          label: "positive",
          status: "refining",
        },
      ],
    });

    render(<FindPlayerStep project={project} onContinue={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("frame-selector").getAttribute("data-pending")).toBe("refining");
      expect(screen.getByTestId("frame-selector").getAttribute("data-focus")).toBe("36");
    });
  });

  it("shows the no-player toast when refinement finishes without a player", async () => {
    serviceMocks.getClicks.mockResolvedValue({
      clicks: [
        {
          click_id: "c1",
          t: 36,
          x_norm: 0.25,
          y_norm: 0.4,
          label: "positive",
          status: "no_player",
        },
      ],
    });

    render(<FindPlayerStep project={project} onContinue={vi.fn()} />);

    expect((await screen.findByRole("alert")).textContent).toBe(
      "We don't see a player there — try clicking directly on their body.",
    );
    expect(screen.getByTestId("frame-selector").getAttribute("data-pending")).toBe("");
  });
});
