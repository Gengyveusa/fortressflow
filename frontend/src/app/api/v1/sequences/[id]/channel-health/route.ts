import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { channel: "email", sent_today: 45, limit: 200, utilization: 0.225, bounce_rate: 0.012, reply_rate: 0.18, last_failure: null },
    { channel: "linkedin", sent_today: 12, limit: 50, utilization: 0.24, bounce_rate: 0, reply_rate: 0.22, last_failure: null },
    { channel: "sms", sent_today: 8, limit: 100, utilization: 0.08, bounce_rate: 0.005, reply_rate: 0.14, last_failure: null },
  ]);
}
