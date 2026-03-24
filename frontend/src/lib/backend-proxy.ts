import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth-options";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

/**
 * Proxy a Next.js API route request to the FastAPI backend.
 *
 * @param req         - The incoming NextRequest
 * @param backendPath - The backend path (e.g. "/api/v1/leads")
 * @param opts        - Optional overrides
 */
export async function proxyToBackend(
  req: NextRequest,
  backendPath: string,
  opts?: {
    /** Override the HTTP method */
    method?: string;
    /** Pass raw body (e.g. for multipart/form-data) */
    rawBody?: BodyInit | null;
    /** Extra headers to merge */
    extraHeaders?: Record<string, string>;
    /** If true, stream the response (for SSE) */
    stream?: boolean;
  },
): Promise<NextResponse | Response> {
  const session = await getServerSession(authOptions);
  const accessToken = (session as any)?.accessToken;

  const url = new URL(`${BACKEND_URL}${backendPath}`);

  // Forward query params
  req.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.append(key, value);
  });

  const method = opts?.method ?? req.method;

  // Build headers
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  if (opts?.extraHeaders) {
    Object.assign(headers, opts.extraHeaders);
  }

  // Determine body
  let body: BodyInit | null | undefined = opts?.rawBody;
  if (body === undefined) {
    if (method !== "GET" && method !== "HEAD") {
      const contentType = req.headers.get("content-type") || "";
      if (contentType.includes("multipart/form-data")) {
        // Forward FormData as-is — let fetch set the boundary
        body = await req.formData() as any;
      } else {
        // Forward JSON or other text body
        headers["Content-Type"] = contentType || "application/json";
        body = await req.text();
      }
    } else {
      body = null;
    }
  }

  const backendRes = await fetch(url.toString(), {
    method,
    headers,
    body,
  });

  // Streaming response (SSE)
  if (opts?.stream && backendRes.body) {
    return new Response(backendRes.body, {
      status: backendRes.status,
      headers: {
        "Content-Type": backendRes.headers.get("content-type") || "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  // Standard JSON response
  const data = await backendRes.json().catch(() => null);
  return NextResponse.json(data ?? {}, { status: backendRes.status });
}
