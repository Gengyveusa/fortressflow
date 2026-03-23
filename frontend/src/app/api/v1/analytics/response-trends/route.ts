import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { week: "W1", rate: 0.12 },
    { week: "W2", rate: 0.14 },
    { week: "W3", rate: 0.15 },
    { week: "W4", rate: 0.18 },
    { week: "W5", rate: 0.17 },
    { week: "W6", rate: 0.19 },
  ]);
}
