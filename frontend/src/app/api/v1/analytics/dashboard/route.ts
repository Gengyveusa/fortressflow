import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    total_leads: 2847,
    active_consents: 1923,
    touches_sent: 14562,
    response_rate: 0.187,
  });
}
