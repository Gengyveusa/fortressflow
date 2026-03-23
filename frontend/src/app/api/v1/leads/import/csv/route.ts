import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({
    imported: 150,
    duplicates: 12,
    errors: 3,
  });
}
