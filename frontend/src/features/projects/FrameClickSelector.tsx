import React, { useEffect, useState } from "react";
import { frameUrl, getFrameDetections } from "../../services/projects";
import type { DetectionBox, PlayerClick } from "./guidedTypes";


type Props = {
  projectId: string;
  durationS: number;
  onPlayerClick: (click: { t: number; x_norm: number; y_norm: number }) => void;
  selectedTrackletId?: string | null;
  selectedClusterId?: string | null;
  focusTimestamp?: number | null;
  pendingPoint?: { x_norm: number; y_norm: number } | null;
  pendingClicks?: PlayerClick[];
};


function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}


export function FrameClickSelector({
  projectId,
  durationS,
  onPlayerClick,
  selectedTrackletId,
  selectedClusterId,
  focusTimestamp,
  pendingPoint,
  pendingClicks = [],
}: Props): JSX.Element {
  const [position, setPosition] = useState(0);
  const [displayedPosition, setDisplayedPosition] = useState(0);
  const [boxes, setBoxes] = useState<DetectionBox[]>([]);
  const [frameError, setFrameError] = useState("");
  const [frameAttempt, setFrameAttempt] = useState(0);

  useEffect(() => {
    if (focusTimestamp == null) return;
    setPosition(Math.max(0, Math.min(durationS, focusTimestamp)));
  }, [durationS, focusTimestamp]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setFrameError("");
      setDisplayedPosition(position);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [position]);

  useEffect(() => {
    if (!frameError) return;
    const timer = window.setTimeout(() => {
      setFrameError("");
      setFrameAttempt((value) => value + 1);
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [frameError]);

  useEffect(() => {
    let active = true;
    getFrameDetections(projectId, displayedPosition)
      .then((result) => {
        if (active) setBoxes(result.boxes);
      })
      .catch(() => {
        if (active) setBoxes([]);
      });
    return () => {
      active = false;
    };
  }, [displayedPosition, projectId]);

  function handleImageClick(event: React.MouseEvent<HTMLImageElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
    onPlayerClick({ t: displayedPosition, x_norm: x, y_norm: y });
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const delta = event.shiftKey ? 30 : 5;
    const direction = event.key === "ArrowRight" ? 1 : -1;
    setPosition((current) => Math.max(0, Math.min(durationS, current + direction * delta)));
  }

  return (
    <section style={{ display: "grid", gap: 10 }}>
      <p style={{ margin: 0, fontSize: 15 }}>Scrub to any moment where you can see your player clearly, then click them.</p>
      <div style={{ position: "relative", width: "100%", aspectRatio: "16 / 9", background: "#161a18", overflow: "hidden" }}>
        <img
          src={`${frameUrl(projectId, displayedPosition)}&attempt=${frameAttempt}`}
          alt="Match frame"
          onClick={handleImageClick}
          onError={() => setFrameError("We're still getting the video ready — try again in a moment.")}
          onLoad={() => setFrameError("")}
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block", cursor: "crosshair", visibility: frameError ? "hidden" : "visible" }}
        />
        {frameError ? (
          <div role="status" style={{ color: "#f4f5f2", display: "grid", position: "absolute", inset: 0, placeItems: "center", padding: 20 }}>{frameError}</div>
        ) : null}
        {boxes.map((box, index) => {
          const selected = box.is_target || Boolean(
            (selectedTrackletId && box.tracklet_id === selectedTrackletId)
            || (selectedClusterId && box.cluster_id === selectedClusterId),
          );
          return (
            <span
              key={`${box.tracklet_id ?? "box"}-${index}`}
              aria-label="Detected player"
              style={{
                position: "absolute",
                left: `${box.x * 100}%`,
                top: `${box.y * 100}%`,
                width: `${box.w * 100}%`,
                height: `${box.h * 100}%`,
                border: selected ? "3px solid #28a36a" : "1px solid rgba(255,255,255,0.52)",
                pointerEvents: "none",
                boxSizing: "border-box",
              }}
            />
          );
        })}
        {pendingPoint ? (
          <span aria-label="Pinned player click" style={{ position: "absolute", left: `${pendingPoint.x_norm * 100}%`, top: `${pendingPoint.y_norm * 100}%`, width: 14, height: 14, border: "3px solid #d59720", borderRadius: "50%", transform: "translate(-50%, -50%)", pointerEvents: "none" }} />
        ) : null}
        {pendingClicks
          .filter((click) => Math.abs(click.t - displayedPosition) <= 0.5)
          .map((click) => {
            const refining = click.status === "refining";
            const label = refining ? "Refining player click" : "Pinned player click";
            return (
              <span
                key={click.click_id}
                aria-label={label}
                title={label}
                style={{
                  position: "absolute",
                  left: `${click.x_norm * 100}%`,
                  top: `${click.y_norm * 100}%`,
                  width: 18,
                  height: 18,
                  border: "3px solid #d59720",
                  borderRadius: "50%",
                  transform: "translate(-50%, -50%)",
                  pointerEvents: "none",
                  boxSizing: "border-box",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    position: "absolute",
                    left: 11,
                    top: -12,
                    width: 18,
                    height: 18,
                    borderRadius: "50%",
                    background: "#d59720",
                    color: "#171914",
                    display: "grid",
                    placeItems: "center",
                    fontSize: 9,
                    fontWeight: 700,
                    lineHeight: 1,
                  }}
                >
                  {refining ? "..." : "P"}
                </span>
              </span>
            );
          })}
      </div>
      <label style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", alignItems: "center", gap: 10, fontSize: 13 }}>
        <span>{formatTime(position)}</span>
        <input
          aria-label="Match position"
          type="range"
          min={0}
          max={durationS}
          step={0.1}
          value={position}
          onChange={(event) => setPosition(Number(event.target.value))}
          onKeyDown={handleKeyDown}
        />
        <span>{formatTime(durationS)}</span>
      </label>
    </section>
  );
}
