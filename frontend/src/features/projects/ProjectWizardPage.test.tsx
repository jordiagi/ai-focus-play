import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectWizardPage } from "./ProjectWizardPage";
import { saveActiveProjectId } from "./projectStore";


const projectMocks = vi.hoisted(() => ({
  getProject: vi.fn(),
  listProjects: vi.fn(),
  createProject: vi.fn(),
  attachSource: vi.fn(),
}));

vi.mock("../../services/projects", async () => {
  const actual = await vi.importActual<typeof import("../../services/projects")>("../../services/projects");
  return { ...actual, ...projectMocks };
});

vi.mock("./FindPlayerStep", () => ({
  FindPlayerStep: ({ project }: { project: { project_id: string } }) => <div>Restored {project.project_id}</div>,
}));


describe("ProjectWizardPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    projectMocks.getProject.mockReset();
    projectMocks.listProjects.mockReset();
    projectMocks.listProjects.mockResolvedValue([]);
  });

  afterEach(cleanup);

  it("restores the active project and returns to player finding", async () => {
    saveActiveProjectId("project-1");
    projectMocks.getProject.mockResolvedValue({
      project_id: "project-1",
      status: "analyzing",
      source: { duration_s: 90, proxy_status: "pending" },
      target_cluster_id: null,
    });

    render(<ProjectWizardPage />);

    expect(screen.getByText("Reopening your project")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Restored project-1")).toBeTruthy());
    expect(projectMocks.getProject).toHaveBeenCalledWith("project-1");
    expect(screen.getByText("Choose a clear moment in the match, then click your player. Analysis status appears below.")).toBeTruthy();
  });

  it("renders the three normative step labels", async () => {
    render(<ProjectWizardPage />);

    await waitFor(() => expect(screen.getByText("Add video", { selector: "strong" })).toBeTruthy());
    expect(screen.getByText("Find your player", { selector: "strong" })).toBeTruthy();
    expect(screen.getByText("Build the reel", { selector: "strong" })).toBeTruthy();
  });

  it("recovers the newest attached project when storage predates persistence", async () => {
    projectMocks.listProjects.mockResolvedValue([
      { project_id: "draft", status: "draft", source_id: null },
      { project_id: "active", status: "analyzing", source_id: "source-1" },
    ]);
    projectMocks.getProject.mockResolvedValue({
      project_id: "active",
      status: "analyzing",
      source_id: "source-1",
      source: { duration_s: 90, proxy_status: "ready" },
      target_cluster_id: null,
    });

    render(<ProjectWizardPage />);

    await waitFor(() => expect(screen.getByText("Restored active")).toBeTruthy());
    expect(window.localStorage.getItem("ai-focus-play.active-project-id")).toBe("active");
  });

  it("returns to video selection without deleting the processed project", async () => {
    saveActiveProjectId("project-1");
    projectMocks.getProject.mockResolvedValue({
      project_id: "project-1",
      status: "analyzing",
      source: { duration_s: 90, proxy_status: "ready" },
      target_cluster_id: null,
    });

    render(<ProjectWizardPage />);
    await waitFor(() => expect(screen.getByText("Restored project-1")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Start new project" }));

    expect(screen.getByLabelText("Match video file")).toBeTruthy();
    expect(window.localStorage.getItem("ai-focus-play.active-project-id")).toBeNull();
  });
});
