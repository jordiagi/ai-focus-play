import React from "react";
import { ProjectWizardPage } from "../features/projects/ProjectWizardPage";
import { ReviewPage } from "../features/review/ReviewPage";
import { ExportsPage } from "../features/exports/ExportsPage";

export type RouteKey = "setup" | "review" | "exports";

export function renderRoute(route: RouteKey): JSX.Element {
  if (route === "review") return <ReviewPage />;
  if (route === "exports") return <ExportsPage />;
  return <ProjectWizardPage />;
}

