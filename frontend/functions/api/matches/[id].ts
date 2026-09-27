interface Env {
  MEDIA_BUCKET?: any;
}

export const onRequestGet: PagesFunction<Env> = async ({ params, env }) => {
  const matchId = params.id as string;
  if (!env.MEDIA_BUCKET || !matchId) {
    return new Response(JSON.stringify({ detail: "Match not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }

  try {
    const object = await env.MEDIA_BUCKET.get(`matches/${matchId}/match.json`);
    if (!object) {
      return new Response(JSON.stringify({ detail: `Match '${matchId}' not found` }), {
        status: 404,
        headers: { "Content-Type": "application/json" }
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
