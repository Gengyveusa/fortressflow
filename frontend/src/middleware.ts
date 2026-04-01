import { NextResponse, type NextRequest } from "next/server";
import { withAuth } from "next-auth/middleware";

const authMiddleware = withAuth({
  pages: {
    signIn: "/login",
  },
});

export default function middleware(request: NextRequest) {
  if (process.env.E2E_AUTH_BYPASS === "true") {
    return NextResponse.next();
  }

  return authMiddleware(request);
}

export const config = {
  matcher: [
    "/((?!login|register|forgot-password|reset-password|sms-consent|privacy|terms|api/auth|api/v1|_next/static|_next/image|favicon.ico|super-dashboard|community|churn-detection|deduplication|experiments|packaging|science-graph|testing).*)",
  ],
};
