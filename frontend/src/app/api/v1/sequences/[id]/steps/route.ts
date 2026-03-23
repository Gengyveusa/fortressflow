import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({
    id: "step-new",
    sequence_id: "seq-1",
    step_type: "email",
    position: 1,
    config: {},
    delay_hours: 0,
    condition: null,
    true_next_position: null,
    false_next_position: null,
    ab_variants: null,
    is_ab_test: false,
    node_id: null,
    created_at: "2026-03-22T08:00:00Z",
  }, { status: 201 });
}
