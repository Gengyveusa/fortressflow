import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatAssistant } from "@/components/ChatAssistant";

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
          <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
            <Sidebar />
            <div className="md:pl-64 flex flex-col min-h-screen">
              <Header />
              <main className="flex-1 p-6">{children}</main>
            </div>
          </div>
          <ChatAssistant />
        </Providers>
      </body>
    </html>
  );
}
