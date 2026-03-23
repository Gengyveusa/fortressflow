import { NextResponse } from "next/server";

const mockSequences = [
  {
    id: "seq-1", name: "Cold Outreach — SaaS", description: "Multi-channel cold outreach targeting SaaS decision makers", status: "active",
    created_at: "2026-03-10T09:00:00Z", updated_at: "2026-03-20T14:00:00Z",
    steps: [
      { id: "step-1", sequence_id: "seq-1", step_type: "email", position: 1, config: { subject: "Quick question about {{company}}" }, delay_hours: 0, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n1", created_at: "2026-03-10T09:00:00Z" },
      { id: "step-2", sequence_id: "seq-1", step_type: "linkedin_connect", position: 2, config: { message: "Hi {{first_name}}, loved your recent post." }, delay_hours: 24, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n2", created_at: "2026-03-10T09:00:00Z" },
      { id: "step-3", sequence_id: "seq-1", step_type: "email", position: 3, config: { subject: "Following up — {{company}}" }, delay_hours: 72, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n3", created_at: "2026-03-10T09:00:00Z" },
    ],
    enrolled_count: 420, visual_config: null, ai_generated: false, ai_generation_prompt: null, ai_generation_metadata: null,
  },
  {
    id: "seq-2", name: "Re-engagement Campaign", description: "Win back inactive leads with personalized content", status: "active",
    created_at: "2026-03-08T11:00:00Z", updated_at: "2026-03-19T16:30:00Z",
    steps: [
      { id: "step-4", sequence_id: "seq-2", step_type: "email", position: 1, config: { subject: "We miss you, {{first_name}}!" }, delay_hours: 0, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n4", created_at: "2026-03-08T11:00:00Z" },
      { id: "step-5", sequence_id: "seq-2", step_type: "sms", position: 2, config: { body: "Hi {{first_name}}, check your inbox!" }, delay_hours: 48, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n5", created_at: "2026-03-08T11:00:00Z" },
    ],
    enrolled_count: 310, visual_config: null, ai_generated: false, ai_generation_prompt: null, ai_generation_metadata: null,
  },
  {
    id: "seq-3", name: "Event Follow-Up", description: "Automated follow-up after trade shows and webinars", status: "paused",
    created_at: "2026-03-05T14:00:00Z", updated_at: "2026-03-18T10:00:00Z",
    steps: [
      { id: "step-6", sequence_id: "seq-3", step_type: "email", position: 1, config: { subject: "Great meeting you at {{event_name}}" }, delay_hours: 0, condition: null, true_next_position: null, false_next_position: null, ab_variants: null, is_ab_test: false, node_id: "n6", created_at: "2026-03-05T14:00:00Z" },
    ],
    enrolled_count: 150, visual_config: null, ai_generated: true, ai_generation_prompt: "Create a post-event follow-up sequence", ai_generation_metadata: null,
  },
  {
    id: "seq-4", name: "Trial Nurture Drip", description: "Nurture trial users toward conversion", status: "draft",
    created_at: "2026-03-01T08:00:00Z", updated_at: "2026-03-15T12:00:00Z",
    steps: [],
    enrolled_count: 0, visual_config: null, ai_generated: false, ai_generation_prompt: null, ai_generation_metadata: null,
  },
];

export async function GET() {
  return NextResponse.json({
    items: mockSequences,
    total: 4,
    page: 1,
    page_size: 20,
  });
}

export async function POST() {
  return NextResponse.json(mockSequences[0], { status: 201 });
}
