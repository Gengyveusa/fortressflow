import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { sequence_id: "seq-1", total_sends: 1250, opens: 775, replies: 225, bounces: 15 },
    { sequence_id: "seq-2", total_sends: 890, opens: 490, replies: 125, bounces: 7 },
    { sequence_id: "seq-3", total_sends: 450, opens: 320, replies: 108, bounces: 2 },
  ]);
}
