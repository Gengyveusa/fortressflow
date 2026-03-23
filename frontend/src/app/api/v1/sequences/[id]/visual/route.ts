import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    sequence_id: id,
    visual_config: null,
    steps: [],
  });
}

export async function PUT() {
  return NextResponse.json({ success: true });
}
