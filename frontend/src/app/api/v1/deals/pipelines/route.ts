import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    {
      pipeline_id: "default",
      label: "Sales Pipeline",
      stages: [
        { stage_id: "discovery", label: "Discovery" },
        { stage_id: "qualified", label: "Qualified" },
        { stage_id: "proposal", label: "Proposal" },
        { stage_id: "negotiation", label: "Negotiation" },
        { stage_id: "closed_won", label: "Closed Won" },
        { stage_id: "closed_lost", label: "Closed Lost" },
      ],
    },
  ]);
}
