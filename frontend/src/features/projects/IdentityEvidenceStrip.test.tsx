import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IdentityEvidenceStrip } from "./IdentityEvidenceStrip";
import type { IdentityCandidate } from "./guidedTypes";


const serviceMocks = vi.hoisted(() => ({
  adjustTarget: vi.fn(),
  confirmTarget: vi.fn(),
}));

vi.mock("../../services/projects", async () => {
  const actual = await vi.importActual<typeof import("../../services/projects")>("../../services/projects");
  return { ...actual, ...serviceMocks };
});

const candidate: IdentityCandidate = {
  cluster_id: "cluster-1",
  jersey_number: "8",
  jersey_agreement: { readings: 4, agrees_with_hint: true },
  kit_color_name: "blue",
  screen_time_s: 20,
  tracklet_count: 2,
  rep_crop_uri: "/projects/p1/evidence-media/rep.jpg",
  evidence: [
    {
      ts: 12,
      thumbnail_uri: "/projects/p1/evidence-media/crop.jpg",
      clip_uri: "/projects/p1/evidence-media/clip.mp4",
      tracklet_id: "t1",
    },
  ],
  timeline_spans: [{ start_ts: 10, end_ts: 14 }],
};


describe("IdentityEvidenceStrip", () => {
  beforeEach(() => {
    serviceMocks.adjustTarget.mockReset().mockResolvedValue({ coverage: { segment_count: 0, total_s: 0, gaps: [] } });
    serviceMocks.confirmTarget.mockReset().mockResolvedValue({
      target_cluster_id: "cluster-1",
      coverage: { segment_count: 2, total_s: 20, gaps: [] },
    });
  });

  afterEach(cleanup);

  it("renders only real evidence media and the jersey agreement source", () => {
    render(
      <IdentityEvidenceStrip
        projectId="p1"
        candidate={candidate}
        jerseyHint="8"
        onRefresh={vi.fn()}
        onConfirmed={vi.fn()}
      />,
    );

    expect(screen.getByText("We think this is your player.")).toBeTruthy();
    expect(screen.getByText("We read #8 on them in 4 different moments.")).toBeTruthy();
    expect(screen.getByAltText("Player appearance at 0:12").getAttribute("src")).toContain("/projects/p1/evidence-media/crop.jpg");
    expect(document.querySelector("video")?.getAttribute("src")).toContain("/projects/p1/evidence-media/clip.mp4");
    expect(document.body.innerHTML).not.toContain("placeholder");
    expect(document.body.innerHTML).not.toContain("linear-gradient");
  });

  it("leads with the clicked appearance and enlarges the full crop on hover", () => {
    const clickedEvidence = {
      ts: 48,
      thumbnail_uri: "/projects/p1/evidence-media/clicked.jpg",
      tracklet_id: "t2",
    };
    render(
      <IdentityEvidenceStrip
        projectId="p1"
        candidate={{ ...candidate, evidence: [candidate.evidence[0], clickedEvidence] }}
        clickedTrackletId="t2"
        jerseyHint={null}
        onRefresh={vi.fn()}
        onConfirmed={vi.fn()}
      />,
    );

    const thumbnails = screen.getAllByRole("button", { name: /Enlarge player at/ });
    expect(thumbnails[0].getAttribute("aria-label")).toBe("Enlarge player at 0:48");

    fireEvent.mouseEnter(thumbnails[0]);
    const preview = screen.getByTestId("evidence-hover-preview");
    expect(preview.querySelector("img")?.getAttribute("src")).toContain("clicked.jpg");

    fireEvent.mouseLeave(thumbnails[0]);
    expect(screen.queryByTestId("evidence-hover-preview")).toBeNull();
  });

  it("shows an amber mismatch and supports Not them plus confirmation", async () => {
    const onRefresh = vi.fn();
    const onConfirmed = vi.fn();
    render(
      <IdentityEvidenceStrip
        projectId="p1"
        candidate={{ ...candidate, jersey_number: "11", jersey_agreement: { readings: 3, agrees_with_hint: false } }}
        jerseyHint="8"
        onRefresh={onRefresh}
        onConfirmed={onConfirmed}
      />,
    );

    expect(screen.getByText("Heads up: we read #11 on this player. Double-check the crops.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Not them at 0:12" }));
    await waitFor(() => expect(serviceMocks.adjustTarget).toHaveBeenCalledWith("p1", { remove_tracklet_ids: ["t1"] }));
    expect(onRefresh).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Yes, that's them" }));
    await waitFor(() => expect(serviceMocks.confirmTarget).toHaveBeenCalledWith("p1", "cluster-1"));
    expect(onConfirmed).toHaveBeenCalledWith({ segment_count: 2, total_s: 20, gaps: [] });
  });
});
