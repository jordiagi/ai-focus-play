interface Env {
  MEDIA_BUCKET?: any;
}

export const onRequestGet: PagesFunction<Env> = async () => {
  const capabilities = {
    read_only: true,
    allow_uploads: false,
    supported_analysis_modes: ["demo", "heuristic", "ml"],
    execution_targets: [
      {
        id: "cloudflare",
        name: "Cloudflare Global Edge",
        status: "online",
        badge: "Active",
        description: "Third-party match viewer served from Cloudflare Pages + R2"
      }
    ],
    default_target: "cloudflare"
  };

  return new Response(JSON.stringify(capabilities), {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=300",
      "Access-Control-Allow-Origin": "*"
    }
  });
};
