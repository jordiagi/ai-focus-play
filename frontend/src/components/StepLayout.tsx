import React from "react";

type StepLayoutProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
};

export function StepLayout({ title, subtitle, children }: StepLayoutProps): JSX.Element {
  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: 32, fontFamily: "ui-sans-serif, system-ui" }}>
      <header style={{ marginBottom: 24 }}>
        <p style={{ textTransform: "uppercase", letterSpacing: 1.2, color: "#5d6b82" }}>AI Focus Play</p>
        <h1 style={{ margin: "8px 0", fontSize: 36 }}>{title}</h1>
        <p style={{ color: "#445066" }}>{subtitle}</p>
      </header>
      {children}
    </main>
  );
}

