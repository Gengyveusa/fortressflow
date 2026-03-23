import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/layout/AppShell";

// Force all pages to be server-rendered at request time.
// This app requires authentication on nearly every route, so static
// prerendering would fail (useSession, useSearchParams, etc.).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "FortressFlow — Ethical B2B Lead Generation",
  description: "Compliance-first B2B outreach platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
