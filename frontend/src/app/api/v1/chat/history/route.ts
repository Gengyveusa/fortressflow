import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    items: [],
    total: 0,
    session_id: "demo-session",
  });
}
