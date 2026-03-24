import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ agent_name: string }> }
) {
  const { agent_name } = await params;
  return proxyToBackend(req, `/api/v1/agents/${agent_name}/execute`);
}
