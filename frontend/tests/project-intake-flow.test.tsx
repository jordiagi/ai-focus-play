import { describe, expect, test } from "vitest";
import { guidedStepLabels } from "../src/features/projects/guidedTypes";

describe("project intake flow", () => {
  test("tracks the simplified three guided steps", () => {
    expect(guidedStepLabels).toEqual(["Add video", "Find your player", "Build the reel"]);
  });
});
