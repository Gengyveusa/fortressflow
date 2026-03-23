import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { day: "Mon", email: 245, sms: 38, linkedin: 62 },
    { day: "Tue", email: 312, sms: 45, linkedin: 78 },
    { day: "Wed", email: 287, sms: 52, linkedin: 71 },
    { day: "Thu", email: 356, sms: 48, linkedin: 85 },
    { day: "Fri", email: 298, sms: 41, linkedin: 68 },
    { day: "Sat", email: 120, sms: 15, linkedin: 22 },
    { day: "Sun", email: 85, sms: 10, linkedin: 18 },
  ]);
}
