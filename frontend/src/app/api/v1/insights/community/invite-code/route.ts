import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/community/invite-code");
  } catch {
    return NextResponse.json(
      { error: "Failed to generate invite code" },
      { status: 502 },
    );
  }
}
