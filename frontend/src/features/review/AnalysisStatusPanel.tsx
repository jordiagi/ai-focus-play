import React from "react";

export function AnalysisStatusPanel({ status, score }: { status: string; score: number }): JSX.Element {
  return (
    <section>
      <h2>Analysis status</h2>
      <p>Status: {status}</p>
      <p>Verification score: {score}</p>
    </section>
  );
}

