import React, { useState } from "react";
import { StepLayout } from "../../components/StepLayout";
import { listDetections, reviewDetection, startAnalysis } from "../../services/reviews";
import { AnalysisStatusPanel } from "./AnalysisStatusPanel";
import { DetectionReviewQueue, type Detection } from "./DetectionReviewQueue";
import { ReviewDecisionBar } from "./ReviewDecisionBar";

export function ReviewPage(): JSX.Element {
  const [projectId, setProjectId] = useState("");
  const [status, setStatus] = useState("Waiting for project");
  const [score, setScore] = useState(0);
  const [summary, setSummary] = useState("Verification status will update as you review detections.");
  const [detections, setDetections] = useState<Detection[]>([]);

  async function handleStartAnalysis() {
    if (!projectId) return;
    const project = (await startAnalysis(projectId, "local")) as { status: string; verification_score: number };
    setStatus(project.status);
    setScore(project.verification_score);
    const payload = (await listDetections(projectId)) as { items: Detection[] };
    setDetections(payload.items);
  }

  async function handleDecision(detectionId: string, decision: "approve" | "reject") {
    if (!projectId) return;
    const project = (await reviewDetection(projectId, detectionId, { decision, reviewer_note: "" })) as {
      status: string;
      verification_score: number;
    };
    setStatus(project.status);
    setScore(project.verification_score);
    setSummary(`Latest decision: ${decision}. Verification score is now ${project.verification_score}.`);
    const payload = (await listDetections(projectId)) as { items: Detection[] };
    setDetections(payload.items);
  }

  return (
    <StepLayout title="Review player tracking" subtitle="Approve or reject low-confidence detections before export.">
      <label>
        Project ID
        <input value={projectId} onChange={(event) => setProjectId(event.target.value)} />
      </label>
      <button onClick={() => void handleStartAnalysis()} style={{ margin: "16px 0" }}>
        Start local analysis
      </button>
      <AnalysisStatusPanel status={status} score={score} />
      <DetectionReviewQueue detections={detections} onSelect={(detectionId, decision) => void handleDecision(detectionId, decision)} />
      <ReviewDecisionBar summary={summary} />
    </StepLayout>
  );
}
