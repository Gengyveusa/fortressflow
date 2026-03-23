import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    lead_id: id,
    consents: [
      { id: 1, channel: "email", method: "explicit_opt_in", proof: "Web form submission", granted_at: "2026-03-15T10:00:00Z" },
    ],
    touch_logs: [
      { id: 1, channel: "email", sent_at: "2026-03-16T14:00:00Z", step_position: 1 },
    ],
    dnc_records: [],
  });
}
