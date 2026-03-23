import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    sequence_id: id,
    total_enrolled: 420,
    active: 185,
    completed: 210,
    steps: [
      { step_position: 1, step_type: "email", sent: 420, opened: 260, replied: 75, bounced: 5 },
      { step_position: 2, step_type: "linkedin_connect", sent: 350, opened: 0, replied: 45, bounced: 0 },
      { step_position: 3, step_type: "email", sent: 280, opened: 175, replied: 52, bounced: 3 },
    ],
    ab_results: [],
  });
}
