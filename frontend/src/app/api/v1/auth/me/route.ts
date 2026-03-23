import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    id: "user-001",
    email: "thad@gengyveusa.com",
    full_name: "Thad Mitchell",
    role: "admin",
    is_active: true,
    created_at: "2026-01-15T00:00:00Z",
    last_login_at: "2026-03-22T20:00:00Z",
  });
}

export async function PUT() {
  return NextResponse.json({
    id: "user-001",
    email: "thad@gengyveusa.com",
    full_name: "Thad Mitchell",
    role: "admin",
    is_active: true,
    created_at: "2026-01-15T00:00:00Z",
    last_login_at: "2026-03-22T20:00:00Z",
  });
}
