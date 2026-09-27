interface Env {
  MEDIA_BUCKET?: any;
}

function getContentType(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".mp4")) return "video/mp4";
  if (lower.endsWith(".webm")) return "video/webm";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".json")) return "application/json";
  return "application/octet-stream";
}

function parseRangeHeader(rangeHeader: string, totalSize: number): { offset: number; length: number; start: number; end: number } | null {
  if (!rangeHeader || !rangeHeader.startsWith("bytes=")) return null;
  const parts = rangeHeader.replace("bytes=", "").split("-");
  const startStr = parts[0].trim();
  const endStr = parts[1].trim();

  let start = 0;
  let end = totalSize - 1;

  if (startStr === "" && endStr !== "") {
    const suffix = parseInt(endStr, 10);
    if (isNaN(suffix) || suffix <= 0) return null;
    start = Math.max(0, totalSize - suffix);
  } else {
    start = parseInt(startStr, 10);
    if (isNaN(start) || start < 0 || start >= totalSize) return null;
    if (endStr !== "") {
      const parsedEnd = parseInt(endStr, 10);
      if (!isNaN(parsedEnd) && parsedEnd >= start) {
        end = Math.min(parsedEnd, totalSize - 1);
      }
    }
  }

  const length = end - start + 1;
  return { offset: start, length, start, end };
}

export const onRequestGet: PagesFunction<Env> = async ({ request, params, env }) => {
  if (!env.MEDIA_BUCKET) {
    return new Response("Storage not configured", { status: 503 });
  }

  // Reconstruct path: /media/videos/abc.mp4 -> key = media/videos/abc.mp4
  const pathSegments = Array.isArray(params.path) ? params.path : [params.path].filter(Boolean);
  const rawKey = pathSegments.join("/");
  const key = rawKey.startsWith("media/") ? rawKey : `media/${rawKey}`;
  const filename = pathSegments[pathSegments.length - 1] || "media.bin";
  const contentType = getContentType(filename);

  try {
    // Check object existence and size first
    const head = await env.MEDIA_BUCKET.head(key);
    if (!head) {
      return new Response("Media asset not found", { status: 404 });
    }

    const totalSize = head.size;
    const rangeHeader = request.headers.get("range");

    if (rangeHeader) {
      const parsed = parseRangeHeader(rangeHeader, totalSize);
      if (!parsed) {
        return new Response("Requested range not satisfiable", {
          status: 416,
          headers: {
            "Content-Range": `bytes */${totalSize}`,
          },
        });
      }

      const object = await env.MEDIA_BUCKET.get(key, {
        range: { offset: parsed.offset, length: parsed.length },
      });

      if (!object || !object.body) {
        return new Response("Error retrieving media slice", { status: 500 });
      }

      return new Response(object.body, {
        status: 206,
        headers: {
          "Content-Type": contentType,
          "Content-Length": String(parsed.length),
          "Content-Range": `bytes ${parsed.start}-${parsed.end}/${totalSize}`,
          "Accept-Ranges": "bytes",
          "Cache-Control": "public, max-age=86400, s-maxage=604800",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }

    // Full object request
    const object = await env.MEDIA_BUCKET.get(key);
    if (!object || !object.body) {
      return new Response("Media not found", { status: 404 });
    }

    return new Response(object.body, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Length": String(totalSize),
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=86400, s-maxage=604800",
        "Access-Control-Allow-Origin": "*",
      },
    });
  } catch (err) {
    return new Response(`Error serving media: ${String(err)}`, { status: 500 });
  }
};
