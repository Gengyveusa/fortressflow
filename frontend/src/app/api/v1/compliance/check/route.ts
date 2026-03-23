import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({ can_send: true, reason: "Valid consent on file" });
}
