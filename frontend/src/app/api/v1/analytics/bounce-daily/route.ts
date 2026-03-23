import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { date: "2026-03-16", bounced: 5, sent: 312 },
    { date: "2026-03-17", bounced: 3, sent: 345 },
    { date: "2026-03-18", bounced: 7, sent: 298 },
    { date: "2026-03-19", bounced: 2, sent: 356 },
    { date: "2026-03-20", bounced: 4, sent: 287 },
    { date: "2026-03-21", bounced: 1, sent: 120 },
    { date: "2026-03-22", bounced: 2, sent: 85 },
  ]);
}
