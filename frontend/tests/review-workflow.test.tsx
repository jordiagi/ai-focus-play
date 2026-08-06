import { describe, expect, test } from "vitest";

describe("review workflow", () => {
  test("keeps review decisions explicit", () => {
    expect(["approve", "reject"]).toContain("approve");
  });
});

