import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    {
      deal_id: "deal-001",
      deal_name: "AcmeTech Enterprise License",
      pipeline: "default",
      stage: "qualified",
      amount: 45000,
      created_at: "2026-03-16T10:00:00Z",
      updated_at: "2026-03-20T14:00:00Z",
      hs_deal_id: null,
    },
  ]);
}

export async function POST() {
  return NextResponse.json({
    deal_id: "deal-new",
    deal_name: "New Deal",
    pipeline: "default",
    stage: "discovery",
    amount: null,
    created_at: "2026-03-22T08:00:00Z",
    updated_at: "2026-03-22T08:00:00Z",
    hs_deal_id: null,
  }, { status: 201 });
}
