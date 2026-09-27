interface Env {
  MEDIA_BUCKET?: any;
}

export const onRequestGet: PagesFunction<Env> = async ({ params, env }) => {
  const matchId = params.id as string;
  const endpoint = params.endpoint as string;

  if (!env.MEDIA_BUCKET || !matchId || !endpoint) {
    return new Response(JSON.stringify({ detail: "Not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }

  // Whitelist supported endpoints
  const allowed = ["events", "highlights", "radar", "analytics", "drawings", "team", "progress"];
  if (!allowed.includes(endpoint)) {
    return new Response(JSON.stringify({ detail: "Endpoint not supported" }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }

  if (endpoint === "progress") {
    return new Response(JSON.stringify({
      match_id: matchId,
      status: "ready",
      step: "Complete",
      progress: 100.0
    }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=60"
      }
    });
  }

  try {
    const object = await env.MEDIA_BUCKET.get(`matches/${matchId}/${endpoint}.json`);
    if (!object) {
      // Default empty responses based on endpoint type
      const emptyPayload = endpoint === "analytics" ? "null" : "[]";
      return new Response(emptyPayload, {
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "public, max-age=60",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }

    const data = await object.text();
    return new Response(data, {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=60, s-maxage=300",
        "Access-Control-Allow-Origin": "*"
      }
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
};
