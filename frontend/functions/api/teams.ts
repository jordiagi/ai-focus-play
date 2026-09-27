interface Env {
  MEDIA_BUCKET?: any;
}

export const onRequestGet: PagesFunction<Env> = async ({ env }) => {
  if (!env.MEDIA_BUCKET) {
    return new Response(JSON.stringify([]), {
      headers: { "Content-Type": "application/json" }
    });
  }

  try {
    const object = await env.MEDIA_BUCKET.get("teams/index.json");
    if (!object) {
      return new Response(JSON.stringify([]), {
        headers: { "Content-Type": "application/json" }
      });
    }

    const data = await object.text();
    return new Response(data, {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=300",
        "Access-Control-Allow-Origin": "*"
      }
    });
  } catch (err) {
    return new Response(JSON.stringify([]), {
      headers: { "Content-Type": "application/json" }
    });
  }
};
