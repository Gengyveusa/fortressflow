import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    sequence_id: id,
    sequence_name: "Cold Outreach — SaaS",
    status: "active",
    total_enrolled: 420,
    active: 185,
    completed: 210,
    replied: 75,
    failed: 5,
    enrollments: [
      {
        id: "enr-1", lead_id: "lead-001", lead_name: "Sarah Chen", lead_email: "sarah.chen@acmetech.io", lead_company: "AcmeTech",
        current_step: 3, total_steps: 3, status: "completed", enrolled_at: "2026-03-10T09:00:00Z",
        last_touch_at: "2026-03-18T14:00:00Z", last_state_change_at: "2026-03-18T14:00:00Z",
        hole_filler_triggered: false, escalation_channel: null, touch_history: [], reply_snippets: [],
      },
    ],
    channel_breakdown: { email: 700, linkedin: 350, sms: 0 },
    daily_send_count: { "2026-03-20": 45, "2026-03-21": 38, "2026-03-22": 22 },
  });
}
