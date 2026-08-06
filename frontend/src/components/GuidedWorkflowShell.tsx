import React from "react";
import { guidedStepLabels } from "../features/projects/guidedTypes";

type Props = {
  activeStep: number;
  title: string;
  subtitle: string;
  children: React.ReactNode;
};

export function GuidedWorkflowShell({ activeStep, title, subtitle, children }: Props): JSX.Element {
  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#f3f5f2",
        color: "#19201b",
        fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
        padding: "24px 16px",
      }}
    >
      <section style={{ maxWidth: 1120, margin: "0 auto" }}>
        <header style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 28, lineHeight: 1.2, margin: "0 0 6px", maxWidth: 850 }}>
            {title}
          </h1>
          <p style={{ fontSize: 15, maxWidth: 700, color: "#526058", margin: 0 }}>{subtitle}</p>
        </header>
        <ol style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8, padding: 0, margin: "0 0 20px" }}>
          {guidedStepLabels.map((label, index) => (
            <li
              key={label}
              aria-current={index === activeStep ? "step" : undefined}
              aria-disabled={index > activeStep}
              style={{
                listStyle: "none",
                padding: "10px 12px",
                borderRadius: 6,
                border: index === activeStep ? "1px solid #245d3d" : "1px solid #d4dad5",
                background: index === activeStep ? "#e8f2eb" : "#fff",
                color: "#1d2d22",
              }}
            >
              <small style={{ display: "block", opacity: 0.72 }}>Step {index + 1}</small>
              <strong>{label}</strong>
            </li>
          ))}
        </ol>
        <section style={{ borderTop: "1px solid #d4dad5", paddingTop: 20 }}>
          {children}
        </section>
      </section>
    </main>
  );
}
