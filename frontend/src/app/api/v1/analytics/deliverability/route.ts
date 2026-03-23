import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    total_sent: 14562,
    total_bounced: 218,
    bounce_rate: 0.015,
    spam_complaints: 3,
    spam_rate: 0.0002,
    warmup_active: 2,
    warmup_completed: 5,
  });
}
