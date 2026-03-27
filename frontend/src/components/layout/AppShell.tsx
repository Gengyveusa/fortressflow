"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ChatAssistantV2 } from "@/components/chat/ChatAssistantV2";
import { useChatPanel } from "@/components/chat/ChatPanelContext";
import { cn } from "@/lib/utils";

// Routes that render their own full-screen layout (no sidebar/header)
const FULL_SCREEN_ROUTES = ["/onboarding", "/login", "/register", "/forgot-password", "/reset-password", "/sms-consent", "/privacy", "/terms"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { mode } = useChatPanel();
  const pathname = usePathname();
  const isExpanded = mode === "expanded";
  const isFullScreen = FULL_SCREEN_ROUTES.some(
    (r) => pathname === r || pathname.startsWith(r + "/")
  );

  if (isFullScreen) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
        {children}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
      <Sidebar />
      <div
        className={cn(
          "md:pl-64 flex flex-col min-h-screen transition-all duration-300",
          isExpanded && "sm:pr-[480px] lg:pr-[520px]"
        )}
      >
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
      <ChatAssistantV2 />
    </div>
  );
}
