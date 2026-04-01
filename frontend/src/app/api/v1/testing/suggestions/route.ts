import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/testing/suggestions");
  } catch {
    return NextResponse.json([], { status: 502 });
  }
}
