import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { service_name: "openai", masked_key: "sk-...abc123", created_at: "2026-03-01T00:00:00Z", updated_at: "2026-03-15T00:00:00Z" },
    { service_name: "anthropic", masked_key: "sk-ant-...xyz789", created_at: "2026-03-05T00:00:00Z", updated_at: "2026-03-18T00:00:00Z" },
  ]);
}
