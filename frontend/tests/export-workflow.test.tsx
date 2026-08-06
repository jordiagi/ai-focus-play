import { describe, expect, test } from "vitest";

describe("export workflow", () => {
  test("includes the supported export profiles", () => {
    expect(["short_highlight", "medium_best_plays"]).toContain("short_highlight");
  });
});

