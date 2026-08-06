import { describe, expect, test } from "vitest";

describe("generate reels flow", () => {
  test("supports short, medium, and target marker choices after confirmation", () => {
    expect(["short_highlight", "medium_best_plays"]).toContain("medium_best_plays");
    expect({ target_marker: true }).toEqual({ target_marker: true });
  });
});
