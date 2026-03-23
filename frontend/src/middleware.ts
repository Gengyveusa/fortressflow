export { default } from "next-auth/middleware";

export const config = {
  matcher: [
    "/((?!login|register|forgot-password|reset-password|api/auth|_next/static|_next/image|favicon.ico).*)",
  ],
};
