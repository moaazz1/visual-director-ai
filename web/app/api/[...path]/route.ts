import { NextRequest } from "next/server";

export const runtime = "nodejs";

const routes = {
  GET: /^(config|assets\/[0-9a-f-]{36}\/(image|audit))$/,
  POST: /^(assets|audits|audits\/[0-9a-f-]{36}\/prompts)$/,
};
const maxSize = 16 * 1024 * 1024;

async function relay(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const path = (await context.params).path.join("/");
  const method = request.method as keyof typeof routes;
  if (!routes[method]?.test(path)) return Response.json({detail: "Route not found."}, {status: 404});
  if (method === "POST" && request.headers.get("sec-fetch-site") === "cross-site") {
    return Response.json({detail: "Cross-site requests are disabled."}, {status: 403});
  }
  const headers = new Headers();
  for (const key of ["content-type", "cookie"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const reader = request.body?.getReader();
  const chunks: Uint8Array<ArrayBuffer>[] = [];
  let size = 0;
  if (reader) {
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxSize) {
        await reader.cancel();
        return Response.json({detail: "Upload exceeds the request limit."}, {status: 413});
      }
      chunks.push(new Uint8Array(value));
    }
  }
  try {
    const base = (process.env.DIRECTOR_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    const result = await fetch(`${base}/${path}`, {
      method, headers, body: reader ? new Blob(chunks) : undefined,
      cache: "no-store", signal: AbortSignal.timeout(125_000),
    });
    const outgoing = new Headers({"Cache-Control": "private, no-store"});
    for (const key of ["content-type", "set-cookie", "x-content-type-options"]) {
      const value = result.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    return new Response(result.body, {status: result.status, headers: outgoing});
  } catch {
    return Response.json({detail: "The creative API is unavailable. Check that FastAPI is running, then retry."}, {status: 503});
  }
}

export const GET = relay;
export const POST = relay;
