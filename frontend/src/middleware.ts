export { default } from "next-auth/middleware";

export const config = {
  matcher: [
    "/((?!login|register|forgot-password|reset-password|sms-consent|privacy|terms|api/auth|api/v1|_next/static|_next/image|favicon.ico|super-dashboard|community|churn-detection|deduplication|experiments|packaging|science-graph).*)",
  ],
};
