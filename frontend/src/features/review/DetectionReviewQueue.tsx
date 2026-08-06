import React from "react";

export type Detection = {
  detection_id: string;
  identity_confidence: number;
  review_state: string;
  visual_cues_used: string[];
};

export function DetectionReviewQueue({
  detections,
  onSelect,
}: {
  detections: Detection[];
  onSelect: (detectionId: string, decision: "approve" | "reject") => void;
}): JSX.Element {
  return (
    <section>
      <h2>Review detections</h2>
      {detections.map((detection) => (
        <div key={detection.detection_id} style={{ border: "1px solid #d7dfeb", padding: 12, marginBottom: 12 }}>
          <p>Confidence: {detection.identity_confidence}</p>
          <p>Cues: {detection.visual_cues_used.join(", ")}</p>
          <button onClick={() => onSelect(detection.detection_id, "approve")}>Approve</button>
          <button onClick={() => onSelect(detection.detection_id, "reject")}>Reject</button>
        </div>
      ))}
    </section>
  );
}

