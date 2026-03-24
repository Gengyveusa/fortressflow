import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  return proxyToBackend(req, "/api/v1/chat/sync");
}
