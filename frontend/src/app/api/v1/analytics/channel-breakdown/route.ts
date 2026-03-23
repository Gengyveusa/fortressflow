import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { name: "Email", value: 68 },
    { name: "LinkedIn", value: 22 },
    { name: "SMS", value: 10 },
  ]);
}
