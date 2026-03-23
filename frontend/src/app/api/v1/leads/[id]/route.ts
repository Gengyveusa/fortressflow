import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    id,
    email: "sarah.chen@acmetech.io",
    phone: "+1-555-0101",
    first_name: "Sarah",
    last_name: "Chen",
    company: "AcmeTech",
    title: "VP of Sales",
    source: "HubSpot Import",
    meeting_verified: true,
    proof_data: null,
    created_at: "2026-03-15T10:30:00Z",
    updated_at: "2026-03-20T14:22:00Z",
  });
}
