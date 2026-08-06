import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FrameClickSelector } from "./FrameClickSelector";

const getFrameDetections = vi.fn();
vi.mock("../../services/projects", async () => {
  const actual = await vi.importActual<typeof import("../../services/projects")>("../../services/projects");
  return { ...actual, getFrameDetections: (...args: unknown[]) => getFrameDetections(...args) };
});

describe("FrameClickSelector", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    getFrameDetections.mockResolvedValue({ analyzed: true, ts_actual: 0, boxes: [] });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("debounces scrubbing and requests the displayed timestamp", async () => {
    render(<FrameClickSelector projectId="p1" durationS={90} onPlayerClick={vi.fn()} />);
    const scrubber = screen.getByLabelText("Match position");

    fireEvent.change(scrubber, { target: { value: "12" } });
    fireEvent.change(scrubber, { target: { value: "18" } });
    await act(async () => vi.advanceTimersByTime(210));

    expect(getFrameDetections).toHaveBeenLastCalledWith("p1", 18);
    expect(screen.getByAltText("Match frame").getAttribute("src")).toContain("t=18");
  });

  it("posts normalized click coordinates and supports keyboard stepping", async () => {
    const onPlayerClick = vi.fn();
    render(<FrameClickSelector projectId="p1" durationS={90} onPlayerClick={onPlayerClick} />);
    const image = screen.getByAltText("Match frame");
    vi.spyOn(image, "getBoundingClientRect").mockReturnValue({
      x: 10,
      y: 20,
      left: 10,
      top: 20,
      right: 210,
      bottom: 120,
      width: 200,
      height: 100,
      toJSON: () => ({}),
    });

    fireEvent.click(image, { clientX: 110, clientY: 70 });
    fireEvent.keyDown(screen.getByLabelText("Match position"), { key: "ArrowRight", shiftKey: true });

    expect(onPlayerClick).toHaveBeenCalledWith({ t: 0, x_norm: 0.5, y_norm: 0.5 });
    expect((screen.getByLabelText("Match position") as HTMLInputElement).value).toBe("30");
  });

  it("retries the frame automatically after the proxy-pending image error", async () => {
    render(<FrameClickSelector projectId="p1" durationS={90} onPlayerClick={vi.fn()} />);
    const image = screen.getByAltText("Match frame");
    const firstUrl = image.getAttribute("src");

    fireEvent.error(image);
    expect(screen.getByText("We're still getting the video ready — try again in a moment.")).toBeTruthy();
    await act(async () => vi.advanceTimersByTime(2010));

    expect(image.getAttribute("src")).not.toBe(firstUrl);
    expect(screen.queryByText("We're still getting the video ready — try again in a moment.")).toBeNull();
  });

  it("keeps untracked boxes neutral and highlights only the selected player", async () => {
    getFrameDetections.mockResolvedValue({
      analyzed: true,
      ts_actual: 0,
      boxes: [
        { tracklet_id: null, x: 0.1, y: 0.1, w: 0.1, h: 0.2, is_target: false },
        { tracklet_id: "t2", cluster_id: "cluster-1", x: 0.3, y: 0.1, w: 0.1, h: 0.2, is_target: false },
      ],
    });

    render(
      <FrameClickSelector
        projectId="p1"
        durationS={90}
        selectedClusterId="cluster-1"
        onPlayerClick={vi.fn()}
      />,
    );

    await act(async () => Promise.resolve());
    const boxes = screen.getAllByLabelText("Detected player");
    expect(boxes[0].style.border).toContain("1px solid");
    expect(boxes[0].style.border).not.toContain("#28a36a");
    expect(boxes[1].style.border).toContain("3px solid");
  });

  it("returns to the selected click timestamp without manual scrubbing", async () => {
    render(
      <FrameClickSelector
        projectId="p1"
        durationS={90}
        focusTimestamp={42}
        onPlayerClick={vi.fn()}
      />,
    );

    await act(async () => vi.advanceTimersByTime(210));

    expect((screen.getByLabelText("Match position") as HTMLInputElement).value).toBe("42");
    expect(getFrameDetections).toHaveBeenLastCalledWith("p1", 42);
  });

  it("shows amber badges for pinned and refining clicks on the displayed frame", () => {
    render(
      <FrameClickSelector
        projectId="p1"
        durationS={90}
        pendingClicks={[
          { click_id: "c1", t: 0, x_norm: 0.25, y_norm: 0.4, label: "positive", status: "pinned" },
          { click_id: "c2", t: 0, x_norm: 0.65, y_norm: 0.6, label: "positive", status: "refining" },
        ]}
        onPlayerClick={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Pinned player click")).toBeTruthy();
    expect(screen.getByLabelText("Refining player click")).toBeTruthy();
  });
});
