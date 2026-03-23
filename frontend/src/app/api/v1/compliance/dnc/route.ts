import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    items: [
      { id: "dnc-1", identifier: "spam@badactor.com", channel: "email", reason: "Spam complaint", source: "automated", blocked_at: "2026-03-15T10:00:00Z", created_at: "2026-03-15T10:00:00Z" },
      { id: "dnc-2", identifier: "+1-555-0199", channel: "sms", reason: "Unsubscribe request", source: "manual", blocked_at: "2026-03-18T14:00:00Z", created_at: "2026-03-18T14:00:00Z" },
      { id: "dnc-3", identifier: "noreply@oldcompany.com", channel: "email", reason: "Hard bounce", source: "automated", blocked_at: "2026-03-20T09:00:00Z", created_at: "2026-03-20T09:00:00Z" },
    ],
    total: 3,
    page: 1,
    page_size: 50,
  });
}

export async function POST() {
  return NextResponse.json({
    id: "dnc-new", identifier: "test@example.com", channel: "email",
    reason: "Manual add", source: "manual",
    blocked_at: "2026-03-22T08:00:00Z", created_at: "2026-03-22T08:00:00Z",
  }, { status: 201 });
}
