import { beforeEach, describe, expect, it } from "vitest";
import {
  clearActiveProjectId,
  canRecoverRecentProject,
  loadActiveProjectId,
  saveActiveProjectId,
  startNewProjectSession,
} from "./projectStore";


describe("projectStore", () => {
  beforeEach(() => window.localStorage.clear());

  it("persists and clears the active project id", () => {
    expect(loadActiveProjectId()).toBeNull();

    saveActiveProjectId("project-1");
    expect(loadActiveProjectId()).toBe("project-1");

    clearActiveProjectId();
    expect(loadActiveProjectId()).toBeNull();
  });

  it("keeps an explicit new-project choice across reloads", () => {
    saveActiveProjectId("project-1");
    startNewProjectSession();

    expect(loadActiveProjectId()).toBeNull();
    expect(canRecoverRecentProject()).toBe(false);

    saveActiveProjectId("project-2");
    expect(canRecoverRecentProject()).toBe(true);
  });
});
