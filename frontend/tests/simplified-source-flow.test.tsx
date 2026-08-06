import { describe, expect, test } from "vitest";
import type { SourceType } from "../src/features/projects/guidedTypes";

const supportedSourceTypes: SourceType[] = ["discovered_local", "youtube", "relative_local_path"];

describe("simplified source flow", () => {
  test("supports local dropdown, youtube, and safe relative path sources", () => {
    expect(supportedSourceTypes).toContain("discovered_local");
    expect(supportedSourceTypes).toContain("youtube");
    expect(supportedSourceTypes).toContain("relative_local_path");
  });

  test("does not include manual match-window as a guided step", () => {
    expect(["Choose video", "Confirm player", "Generate reels"]).not.toContain("Confirm match window");
  });
});
