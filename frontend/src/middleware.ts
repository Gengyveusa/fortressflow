export { default } from "next-auth/middleware";

export const config = {
  matcher: [
    "/((?!login|register|forgot-password|reset-password|sms-consent|privacy|terms|api/auth|_next/static|_next/image|favicon.ico).*)",
  ],
};
