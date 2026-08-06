import React from "react";

export function StatusBanner({ status, message }: { status: string; message: string }): JSX.Element {
  return (
    <div style={{ background: "#eef4ff", border: "1px solid #cbd8f4", padding: 16, borderRadius: 12, marginBottom: 20 }}>
      <strong>{status}</strong>
      <div>{message}</div>
    </div>
  );
}

