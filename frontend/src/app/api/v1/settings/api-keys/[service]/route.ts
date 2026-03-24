import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ service: string }> },
) {
  const { service } = await params;
  return proxyToBackend(req, `/api/v1/settings/api-keys/${service}`);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ service: string }> },
) {
  const { service } = await params;
  return proxyToBackend(req, `/api/v1/settings/api-keys/${service}`);
}
