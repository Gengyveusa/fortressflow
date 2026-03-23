import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    insights: [
      {
        id: "ins-1",
        type: "high_performer",
        title: "Cold Outreach sequence is crushing it",
        description: "Your SaaS cold outreach sequence has a 18.7% response rate — 3x the industry average. Consider increasing enrollment.",
        action_label: "Enroll more leads",
        action_value: "/sequences/seq-1",
      },
      {
        id: "ins-2",
        type: "warning",
        title: "Domain warmup needs attention",
        description: "mail.gengyve.com is at 72% warmup — avoid increasing send volume until warmup completes.",
        action_label: "View domains",
        action_value: "/deliverability",
      },
      {
        id: "ins-3",
        type: "suggestion",
        title: "Try A/B testing your subject lines",
        description: "Your open rate could improve by 15-20% with systematic subject line testing on your top sequences.",
        action_label: "Learn more",
        action_value: "/sequences",
      },
    ],
  });
}
