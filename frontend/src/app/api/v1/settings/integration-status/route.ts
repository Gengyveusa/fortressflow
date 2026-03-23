import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    integrations: [
      { name: "HubSpot CRM", configured: true, mode: "active" },
      { name: "SendGrid", configured: true, mode: "active" },
      { name: "Twilio SMS", configured: true, mode: "active" },
      { name: "LinkedIn Sales Nav", configured: false, mode: "not_configured" },
      { name: "Slack Notifications", configured: true, mode: "manual" },
      { name: "OpenAI GPT-4", configured: true, mode: "active" },
      { name: "Anthropic Claude", configured: true, mode: "active" },
    ],
  });
}
