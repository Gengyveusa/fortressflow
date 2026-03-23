import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    {
      name: "5-Step SaaS Outreach",
      description: "Proven multi-channel sequence for SaaS prospects",
      category: "outreach",
      steps: [
        { step_type: "email", position: 1, delay_hours: 0, has_template: true, template_name: "Cold Intro", channel: "email" },
        { step_type: "linkedin_connect", position: 2, delay_hours: 24, has_template: true, template_name: "Connect Request", channel: "linkedin" },
        { step_type: "email", position: 3, delay_hours: 72, has_template: true, template_name: "Follow-Up #1", channel: "email" },
        { step_type: "sms", position: 4, delay_hours: 120, has_template: true, template_name: "Quick Check-In", channel: "sms" },
        { step_type: "email", position: 5, delay_hours: 168, has_template: true, template_name: "Break-Up Email", channel: "email" },
      ],
    },
    {
      name: "3-Step Re-engagement",
      description: "Win back cold leads with personalized touches",
      category: "re-engagement",
      steps: [
        { step_type: "email", position: 1, delay_hours: 0, has_template: true, template_name: "We Miss You", channel: "email" },
        { step_type: "email", position: 2, delay_hours: 72, has_template: true, template_name: "Value Reminder", channel: "email" },
        { step_type: "email", position: 3, delay_hours: 168, has_template: true, template_name: "Last Chance", channel: "email" },
      ],
    },
  ]);
}
