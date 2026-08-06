export type ProjectState = {
  projectId?: string;
  status: string;
  step: number;
  verificationScore: number;
};

export const initialProjectState: ProjectState = {
  status: "draft",
  step: 1,
  verificationScore: 0,
};

const ACTIVE_PROJECT_KEY = "ai-focus-play.active-project-id";
const RECENT_PROJECT_RECOVERY_KEY = "ai-focus-play.recover-recent-project";

export function loadActiveProjectId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACTIVE_PROJECT_KEY);
  } catch {
    return null;
  }
}

export function saveActiveProjectId(projectId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ACTIVE_PROJECT_KEY, projectId);
    window.localStorage.removeItem(RECENT_PROJECT_RECOVERY_KEY);
  } catch {
    // The current session still works when browser storage is unavailable.
  }
}

export function clearActiveProjectId(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
  } catch {
    // Nothing else is required when browser storage is unavailable.
  }
}

export function startNewProjectSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
    window.localStorage.setItem(RECENT_PROJECT_RECOVERY_KEY, "disabled");
  } catch {
    // The in-memory reset still lets the current session start a new project.
  }
}

export function canRecoverRecentProject(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(RECENT_PROJECT_RECOVERY_KEY) !== "disabled";
  } catch {
    return false;
  }
}
