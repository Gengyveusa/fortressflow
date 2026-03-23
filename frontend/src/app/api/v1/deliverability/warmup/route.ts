import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { inbox_id: "inbox-1", date: "2026-03-22", emails_sent: 45, emails_target: 50, bounce_rate: 0.01, spam_rate: 0.0, open_rate: 0.72, status: "active" },
    { inbox_id: "inbox-2", date: "2026-03-22", emails_sent: 30, emails_target: 40, bounce_rate: 0.02, spam_rate: 0.001, open_rate: 0.65, status: "active" },
  ]);
}
