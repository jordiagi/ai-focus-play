import React, { useEffect, useState } from "react";
import { GuidedWorkflowShell } from "../../components/GuidedWorkflowShell";
import { StatusBanner } from "../../components/StatusBanner";
import { attachSource, createProject, getProject, listProjects } from "../../services/projects";
import { FindPlayerStep } from "./FindPlayerStep";
import { ReelGenerationStep } from "./ReelGenerationStep";
import { VideoSourceStep, type VideoSourceSelection } from "./VideoSourceStep";
import type { GuidedProject } from "./guidedTypes";
import { canRecoverRecentProject, loadActiveProjectId, saveActiveProjectId, startNewProjectSession } from "./projectStore";


function stepIndex(project: GuidedProject | null): number {
  if (!project?.source) return 0;
  return project.target_cluster_id || project.status === "target_confirmed" || project.status === "ready_to_export" ? 2 : 1;
}


export function ProjectWizardPage(): JSX.Element {
  const [project, setProject] = useState<GuidedProject | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [status, setStatus] = useState("Reopening your project");
  const [message, setMessage] = useState("Restoring your match and analysis progress.");

  useEffect(() => {
    let active = true;
    const restore = async () => {
      let projectId = loadActiveProjectId();
      if (!projectId && canRecoverRecentProject()) {
        const projects = await listProjects();
        projectId = projects.find((candidate) => candidate.source_id)?.project_id ?? null;
        if (projectId) saveActiveProjectId(projectId);
      }
      if (!projectId) {
        if (active) {
          setStatus("Add video");
          setMessage("Choose a match recording to begin.");
        }
        return null;
      }
      return getProject(projectId);
    };
    restore()
      .then((restored) => {
        if (!active || !restored) return;
        setProject(restored);
        if (restored.source) {
          setStatus("Find your player");
          setMessage("Choose a clear moment in the match, then click your player. Analysis status appears below.");
        } else {
          setStatus("Add video");
          setMessage("Choose a match recording to begin.");
        }
      })
      .catch(() => {
        if (!active) return;
        setStatus("We couldn't reopen this project");
        setMessage("Your data is safe — refresh to try reconnecting.");
      })
      .finally(() => {
        if (active) setRestoring(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function ensureProject(): Promise<GuidedProject> {
    if (project) return project;
    const created = await createProject("My player reel");
    saveActiveProjectId(created.project_id);
    setProject(created);
    return created;
  }

  async function handleSource(selection: VideoSourceSelection) {
    const active = await ensureProject();
    if ("file" in selection) {
      const form = new FormData();
      form.append("file", selection.file);
      await attachSource(active.project_id, form);
    } else {
      await attachSource(active.project_id, selection);
    }
    const updated = await getProject(active.project_id);
    saveActiveProjectId(updated.project_id);
    setProject(updated);
    setStatus("Find your player");
    setMessage("Choose a clear moment in the match, then click your player. Analysis status appears below.");
  }

  function handleNewProject() {
    startNewProjectSession();
    setProject(null);
    setRestoring(false);
    setStatus("Add video");
    setMessage("Choose a match recording to begin.");
  }

  async function handlePlayerConfirmed() {
    if (!project) return;
    const updated = await getProject(project.project_id);
    setProject(updated);
    setStatus("Build the reel");
    setMessage("Your player is confirmed. Review the coverage and build the reel.");
  }

  const activeStep = stepIndex(project);
  return (
    <GuidedWorkflowShell activeStep={activeStep} title="AI Focus Play" subtitle="Turn one match recording into a player-focused reel.">
      <StatusBanner status={status} message={message} />
      {project?.source ? (
        <button type="button" onClick={handleNewProject} style={{ marginBottom: 16 }}>
          Start new project
        </button>
      ) : null}
      {!restoring && activeStep === 0 ? <VideoSourceStep onContinue={handleSource} /> : null}
      {activeStep === 1 && project ? <FindPlayerStep project={project} onContinue={() => void handlePlayerConfirmed()} /> : null}
      {activeStep === 2 && project ? (
        <ReelGenerationStep
          projectId={project.project_id}
          confirmed
          durationS={project.source ? Number((project.source as { duration_s?: number }).duration_s) || undefined : undefined}
          onStartOver={() => void handleNewProject()}
        />
      ) : null}
    </GuidedWorkflowShell>
  );
}
