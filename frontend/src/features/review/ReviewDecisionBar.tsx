import React from "react";

export function ReviewDecisionBar({ summary }: { summary: string }): JSX.Element {
  return <div style={{ marginTop: 12, color: "#445066" }}>{summary}</div>;
}

