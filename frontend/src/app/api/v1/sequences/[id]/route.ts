import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    id,
    name: "Cold Outreach — SaaS",
    description: "Multi-channel cold outreach targeting SaaS decision makers",
    status: "active",
    created_at: "2026-03-10T09:00:00Z",
    updated_at: "2026-03-20T14:00:00Z",
    steps: [
      { id: "step-1", sequence_id: id, step_type: "email", position: 1, config: { subject: "Quick question about {{company}}" }, delay_hours: 0, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n1", created_at: "2026-03-10T09:00:00Z" },
      { id: "step-2", sequence_id: id, step_type: "linkedin_connect", position: 2, config: { message: "Hi {{first_name}}" }, delay_hours: 24, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n2", created_at: "2026-03-10T09:00:00Z" },
      { id: "step-3", sequence_id: id, step_type: "email", position: 3, config: { subject: "Following up" }, delay_hours: 72, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n3", created_at: "2026-03-10T09:00:00Z" },
    ],
    enrolled_count: 420,
    visual_config: null,
    ai_generated: false,
    ai_generation_prompt: null,
    ai_generation_metadata: null,
  });
}

export async function PUT() {
  return NextResponse.json({ success: true });
}

export async function DELETE() {
  return NextResponse.json({ success: true });
}
