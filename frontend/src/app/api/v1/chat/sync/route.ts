import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({
    response: "I've analyzed your outreach data. Your sequences are performing above industry average. Would you like me to suggest optimizations?",
    sources: ["analytics_engine"],
    session_id: "demo-session",
  });
}
