import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({
    success: true,
    sequence_id: "seq-gen-1",
    sequence_name: "AI-Generated Outreach",
    steps_generated: 4,
    channels_used: ["email", "linkedin"],
    ai_platforms_consulted: ["gpt-4"],
    visual_config: null,
    error: null,
  });
}
