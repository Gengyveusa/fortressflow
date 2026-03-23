import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({
    access_token: "mock-access-token-demo",
    refresh_token: "mock-refresh-token-demo",
    user: {
      id: "user-001",
      email: "thad@gengyveusa.com",
      full_name: "Thad Mitchell",
      role: "admin",
    },
  });
}
