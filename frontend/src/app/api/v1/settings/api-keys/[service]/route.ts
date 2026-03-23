import { NextResponse } from "next/server";

export async function PUT() {
  return NextResponse.json({
    service_name: "openai",
    masked_key: "sk-...updated",
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-22T08:00:00Z",
  });
}

export async function DELETE() {
  return NextResponse.json({ success: true });
}
