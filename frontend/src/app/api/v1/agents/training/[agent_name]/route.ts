import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ agent_name: string }> }
) {
  const { agent_name } = await params;
  return proxyToBackend(req, `/api/v1/agents/training/${agent_name}`);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ agent_name: string }> }
) {
  const { agent_name } = await params;
  return proxyToBackend(req, `/api/v1/agents/training/${agent_name}`);
}
