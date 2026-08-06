import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import { ReelGenerationStep } from "./ReelGenerationStep";

describe("ReelGenerationStep", () => {
  test("stays locked until a confirmed evidence-backed identity exists", () => {
    const html = renderToStaticMarkup(<ReelGenerationStep projectId="p1" confirmed={false} />);

    expect(html).toContain("Confirm the player before generating reels.");
    expect(html).toContain("disabled");
  });

  test("offers coverage review and all three reel profiles once confirmed", () => {
    const html = renderToStaticMarkup(<ReelGenerationStep projectId="p1" confirmed />);

    expect(html).toContain("Build the reel");
    expect(html).toContain("Generate reel");
    expect(html).toContain("Reel length");
    expect(html).toContain("Short highlight");
    expect(html).toContain("Medium best plays");
    expect(html).toContain("Full appearances");
    expect(html).toContain("marker that follows the identified player");
  });
});
