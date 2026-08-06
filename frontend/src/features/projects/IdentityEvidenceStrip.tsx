import React, { useState } from "react";
import { apiUrl } from "../../services/apiClient";
import { adjustTarget, confirmTarget } from "../../services/projects";
import type { CandidateEvidence, CoverageSummary, IdentityCandidate } from "./guidedTypes";


type Props = {
  projectId: string;
  candidate: IdentityCandidate;
  clickedTrackletId?: string | null;
  jerseyHint: string | null;
  onRefresh: () => void | Promise<void>;
  onConfirmed: (coverage: CoverageSummary) => void;
};


function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}


function mediaUrl(uri: string): string {
  return /^https?:\/\//.test(uri) ? uri : apiUrl(uri);
}


export function IdentityEvidenceStrip({
  projectId,
  candidate,
  clickedTrackletId = null,
  jerseyHint,
  onRefresh,
  onConfirmed,
}: Props): JSX.Element {
  const [busyTracklet, setBusyTracklet] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [hoveredEvidence, setHoveredEvidence] = useState<CandidateEvidence | null>(null);
  const [expandedEvidence, setExpandedEvidence] = useState<CandidateEvidence | null>(null);
  const evidence = candidate.evidence
    .filter((item) => item.thumbnail_uri.startsWith(`/projects/${projectId}/evidence-media/`))
    .sort((left, right) => Number(right.tracklet_id === clickedTrackletId) - Number(left.tracklet_id === clickedTrackletId));
  const timestamps = evidence.slice(0, 4).map((item) => formatTime(item.ts));
  const clips = evidence.filter((item) => item.clip_uri?.startsWith(`/projects/${projectId}/evidence-media/`)).slice(0, 2);

  async function remove(trackletId: string) {
    setBusyTracklet(trackletId);
    setError("");
    try {
      await adjustTarget(projectId, { remove_tracklet_ids: [trackletId] });
      await onRefresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "We couldn't remove that appearance. Your match is safe — try again.");
    } finally {
      setBusyTracklet(null);
    }
  }

  async function confirm() {
    setConfirming(true);
    setError("");
    try {
      const response = await confirmTarget(projectId, candidate.cluster_id);
      onConfirmed(response.coverage);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "We couldn't confirm this player. Your match is safe — try again.");
    } finally {
      setConfirming(false);
    }
  }

  return (
    <section aria-label="Player evidence" style={{ display: "grid", gap: 14, borderTop: "1px solid #d6dbd5", paddingTop: 18 }}>
      <header>
        <h3 style={{ fontSize: 20, margin: "0 0 4px" }}>We think this is your player.</h3>
        <p style={{ margin: 0, color: "#4c5750" }}>
          {timestamps.length ? `Here they are at ${timestamps.join(", ")}${evidence.length > timestamps.length ? "…" : ""}` : "We're matching more appearances now."}
        </p>
      </header>

      {candidate.ambiguous ? (
        <p style={{ margin: 0, padding: 10, borderLeft: "3px solid #b7791f", background: "#fff7e6" }}>
          There may be two players who look alike. Check the crops carefully — if any aren't your player, tap 'Not them'.
        </p>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10 }}>
        {evidence.map((item) => (
          <article key={`${item.tracklet_id}-${item.ts}`} style={{ border: "1px solid #d5dad4", borderRadius: 6, overflow: "hidden", background: "#fff" }}>
            <button
              type="button"
              aria-label={`Enlarge player at ${formatTime(item.ts)}`}
              title="Enlarge player"
              onMouseEnter={() => setHoveredEvidence(item)}
              onMouseLeave={() => setHoveredEvidence(null)}
              onFocus={() => setHoveredEvidence(item)}
              onBlur={() => setHoveredEvidence(null)}
              onClick={() => setExpandedEvidence(item)}
              style={{ display: "block", width: "100%", padding: 0, border: 0, borderRadius: 0, cursor: "zoom-in", background: "#171a18" }}
            >
              <img
                src={mediaUrl(item.thumbnail_uri)}
                alt={`Player appearance at ${formatTime(item.ts)}`}
                style={{ display: "block", width: "100%", aspectRatio: "3 / 4", objectFit: "contain", background: "#171a18" }}
              />
            </button>
            <div style={{ display: "grid", gap: 6, padding: 8 }}>
              <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 6 }}>
                <time>{formatTime(item.ts)}</time>
                {item.tracklet_id === clickedTrackletId ? <small style={{ color: "#356447", fontWeight: 700 }}>Your click</small> : null}
              </div>
              <button
                type="button"
                aria-label={`Not them at ${formatTime(item.ts)}`}
                disabled={busyTracklet === item.tracklet_id}
                onClick={() => void remove(item.tracklet_id)}
                style={{ justifySelf: "start" }}
              >
                Not them
              </button>
            </div>
          </article>
        ))}
      </div>

      {hoveredEvidence && !expandedEvidence ? (
        <div
          data-testid="evidence-hover-preview"
          aria-hidden="true"
          style={{
            position: "fixed",
            zIndex: 40,
            top: "50%",
            left: "50%",
            width: "min(440px, calc(100vw - 32px))",
            maxHeight: "calc(100vh - 48px)",
            padding: 12,
            transform: "translate(-50%, -50%)",
            pointerEvents: "none",
            border: "1px solid #b9c1ba",
            borderRadius: 6,
            background: "#fff",
            boxShadow: "0 16px 44px rgba(22, 29, 24, 0.28)",
          }}
        >
          <img
            src={mediaUrl(hoveredEvidence.thumbnail_uri)}
            alt=""
            style={{ display: "block", width: "100%", maxHeight: "calc(100vh - 100px)", objectFit: "contain", background: "#171a18" }}
          />
        </div>
      ) : null}

      {expandedEvidence ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Player appearance at ${formatTime(expandedEvidence.ts)}`}
          onClick={() => setExpandedEvidence(null)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setExpandedEvidence(null);
          }}
          style={{ position: "fixed", zIndex: 50, inset: 0, display: "grid", placeItems: "center", padding: 16, background: "rgba(18, 22, 19, 0.72)" }}
        >
          <div
            onClick={(event) => event.stopPropagation()}
            style={{ display: "grid", gap: 10, width: "min(520px, 100%)", maxHeight: "calc(100vh - 32px)", padding: 12, borderRadius: 6, background: "#fff" }}
          >
            <button type="button" autoFocus onClick={() => setExpandedEvidence(null)} style={{ justifySelf: "end" }}>Close</button>
            <img
              src={mediaUrl(expandedEvidence.thumbnail_uri)}
              alt={`Enlarged player appearance at ${formatTime(expandedEvidence.ts)}`}
              style={{ display: "block", width: "100%", maxHeight: "calc(100vh - 120px)", objectFit: "contain", background: "#171a18" }}
            />
          </div>
        </div>
      ) : null}

      {clips.length ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
          {clips.map((item) => (
            <video
              key={item.clip_uri}
              src={mediaUrl(item.clip_uri!)}
              poster={mediaUrl(item.thumbnail_uri)}
              controls
              muted
              preload="metadata"
              style={{ width: "100%", borderRadius: 6, background: "#171a18" }}
            />
          ))}
        </div>
      ) : null}

      {jerseyHint && candidate.jersey_agreement.readings > 0 && candidate.jersey_agreement.agrees_with_hint ? (
        <p style={{ margin: 0 }}>We read #{candidate.jersey_number ?? jerseyHint} on them in {candidate.jersey_agreement.readings} different moments.</p>
      ) : null}
      {jerseyHint && candidate.jersey_agreement.readings > 0 && candidate.jersey_agreement.agrees_with_hint === false ? (
        <p style={{ margin: 0, color: "#8a4f08", padding: 10, borderLeft: "3px solid #b7791f", background: "#fff7e6" }}>
          Heads up: we read #{candidate.jersey_number} on this player. Double-check the crops.
        </p>
      ) : null}

      {error ? <p role="alert" style={{ margin: 0, color: "#9c2f2f" }}>{error}</p> : null}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
        <button type="button" disabled={confirming || evidence.length === 0} onClick={() => void confirm()}>
          {confirming ? "Confirming…" : "Yes, that's them"}
        </button>
        <span style={{ color: "#4c5750" }}>Not sure? Scrub somewhere else and click them again.</span>
      </div>
    </section>
  );
}
