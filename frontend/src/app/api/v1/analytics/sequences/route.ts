import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    sequences: [
      { sequence_id: "seq-1", sequence_name: "Cold Outreach — SaaS", enrolled: 420, active: 185, completed: 210, open_rate: 0.62, reply_rate: 0.18, bounce_rate: 0.012 },
      { sequence_id: "seq-2", sequence_name: "Re-engagement", enrolled: 310, active: 95, completed: 180, open_rate: 0.55, reply_rate: 0.14, bounce_rate: 0.008 },
      { sequence_id: "seq-3", sequence_name: "Event Follow-Up", enrolled: 150, active: 60, completed: 85, open_rate: 0.71, reply_rate: 0.24, bounce_rate: 0.005 },
      { sequence_id: "seq-4", sequence_name: "Trial Nurture", enrolled: 280, active: 140, completed: 100, open_rate: 0.48, reply_rate: 0.11, bounce_rate: 0.018 },
      { sequence_id: "seq-5", sequence_name: "Enterprise ABM", enrolled: 95, active: 50, completed: 30, open_rate: 0.58, reply_rate: 0.22, bounce_rate: 0.009 },
    ],
  });
}
