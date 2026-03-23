import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    items: [
      {
        id: "reply-001", enrollment_id: "enr-1", sequence_id: "seq-1", lead_id: "lead-001",
        lead_name: "Sarah Chen", lead_email: "sarah.chen@acmetech.io", channel: "email",
        subject: "Re: Quick question about AcmeTech", body_snippet: "Hi! Yes, we'd love to learn more about your platform. Can we schedule a call this week?",
        sentiment: "positive", sentiment_confidence: 0.92, ai_analysis: null, ai_suggested_action: "Schedule meeting",
        received_at: "2026-03-20T15:30:00Z", processed_at: "2026-03-20T15:31:00Z",
      },
      {
        id: "reply-002", enrollment_id: "enr-2", sequence_id: "seq-1", lead_id: "lead-002",
        lead_name: "Marcus Rivera", lead_email: "marcus.rivera@techcorp.com", channel: "email",
        subject: "Re: Quick question about TechCorp", body_snippet: "Please remove me from your mailing list.",
        sentiment: "negative", sentiment_confidence: 0.88, ai_analysis: null, ai_suggested_action: "Unsubscribe & add to DNC",
        received_at: "2026-03-19T11:45:00Z", processed_at: "2026-03-19T11:46:00Z",
      },
      {
        id: "reply-003", enrollment_id: "enr-5", sequence_id: "seq-2", lead_id: "lead-005",
        lead_name: "Lisa Johnson", lead_email: "lisa.johnson@scaleup.io", channel: "email",
        subject: "Re: We miss you!", body_snippet: "Interesting timing — we were just reviewing tools. Send me pricing?",
        sentiment: "positive", sentiment_confidence: 0.85, ai_analysis: null, ai_suggested_action: "Send pricing deck",
        received_at: "2026-03-18T09:20:00Z", processed_at: "2026-03-18T09:21:00Z",
      },
    ],
    total: 3,
    page: 1,
    page_size: 20,
  });
}
