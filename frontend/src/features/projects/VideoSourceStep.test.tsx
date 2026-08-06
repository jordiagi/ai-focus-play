import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { VideoSourceStep } from "./VideoSourceStep";


vi.mock("../../services/sources", () => ({ listLocalSources: vi.fn().mockResolvedValue({ items: [] }) }));

describe("VideoSourceStep", () => {
  it("offers file and local video selection with long-analysis copy", () => {
    const html = renderToStaticMarkup(<VideoSourceStep onContinue={vi.fn()} />);
    expect(html).toContain("Add video");
    expect(html).toContain("Upload file");
    expect(html).toContain("Video folder");
    expect(html).toContain("fine to leave it overnight");
  });
});
