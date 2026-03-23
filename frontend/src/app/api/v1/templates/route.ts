import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    items: [
      { id: "tpl-1", name: "Cold Intro Email", channel: "email", category: "outreach", subject: "Quick question about {{company}}", html_body: null, plain_body: "Hi {{first_name}},\n\nI noticed {{company}} is growing fast...", linkedin_action: null, variables: ["first_name", "company"], variant_group: null, variant_label: null, is_system: false, is_active: true, created_at: "2026-03-01T00:00:00Z", updated_at: "2026-03-15T00:00:00Z" },
      { id: "tpl-2", name: "Follow-Up #1", channel: "email", category: "follow_up", subject: "Re: {{company}} — quick follow-up", html_body: null, plain_body: "Hi {{first_name}},\n\nJust circling back...", linkedin_action: null, variables: ["first_name", "company"], variant_group: null, variant_label: null, is_system: false, is_active: true, created_at: "2026-03-02T00:00:00Z", updated_at: "2026-03-16T00:00:00Z" },
      { id: "tpl-3", name: "LinkedIn Connect", channel: "linkedin", category: "outreach", subject: null, html_body: null, plain_body: "Hi {{first_name}}, I enjoyed your recent post about...", linkedin_action: "connection_request", variables: ["first_name"], variant_group: null, variant_label: null, is_system: false, is_active: true, created_at: "2026-03-03T00:00:00Z", updated_at: "2026-03-17T00:00:00Z" },
    ],
    total: 3,
    page: 1,
    page_size: 20,
  });
}

export async function POST() {
  return NextResponse.json({ id: "tpl-new", name: "New Template" }, { status: 201 });
}
