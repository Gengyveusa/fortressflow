import { NextResponse } from "next/server";

export async function POST() {
  // Return a streaming-style response with mock AI assistant data
  const responseText = JSON.stringify({
    response: "Based on your current data, your **Cold Outreach — SaaS** sequence is performing well with an 18.7% response rate. Here are a few suggestions:\n\n1. **Optimize Step 2**: LinkedIn connect messages have a 22% reply rate — consider adding a personalized note referencing the prospect's recent activity.\n\n2. **A/B Test Subject Lines**: Your open rate of 62% could improve with subject line testing.\n\n3. **Timing**: Most replies come in between 9-11 AM local time. Consider scheduling sends accordingly.\n\nWould you like me to create an A/B test for your email subjects?",
    sources: ["sequence_analytics", "best_practices_db"],
    session_id: "demo-session",
  });

  return new NextResponse(responseText, {
    headers: { "Content-Type": "application/json" },
  });
}
