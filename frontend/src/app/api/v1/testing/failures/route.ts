import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/testing/failures");
  } catch {
    return NextResponse.json(
      { by_category: {}, top_failing_actions: [], all_failures: [], error: "Backend unavailable" },
      { status: 502 },
    );
  }
}
