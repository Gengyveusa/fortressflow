"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Users,
  GitBranch,
  Shield,
  Mail,
  BarChart3,
  FileText,
  Rocket,
  Inbox,
  Settings,
  Menu,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useChatPanel } from "@/components/chat/ChatPanelContext";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/sequences", label: "Sequences", icon: GitBranch },
  { href: "/sequences/replies", label: "Reply Inbox", icon: Inbox },
  { href: "/templates", label: "Templates", icon: FileText },
  { href: "/presets", label: "Presets", icon: Rocket },
  { href: "/compliance", label: "Compliance", icon: Shield },
  { href: "/deliverability", label: "Deliverability", icon: Mail },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface NavLinkProps {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  pathname: string;
  onClick?: () => void;
}

function NavLink({ href, label, icon: Icon, pathname, onClick }: NavLinkProps) {
  const isActive =
    pathname === href || (href !== "/" && pathname.startsWith(href));

  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors",
        isActive
          ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
          : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100"
      )}
    >
      <Icon className="w-5 h-5 flex-shrink-0" />
      {label}
    </Link>
  );
}

function AIAssistantButton({ onNavClick }: { onNavClick?: () => void }) {
  const { open, hasInsights, mode } = useChatPanel();
  const isActive = mode !== "closed";

  return (
    <button
      onClick={() => {
        open(true);
        onNavClick?.();
      }}
      className={cn(
        "w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors relative",
        isActive
          ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
          : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100"
      )}
    >
      <Sparkles className="w-5 h-5 flex-shrink-0" />
      AI Assistant
      {hasInsights && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 w-2 h-2 bg-red-500 rounded-full" />
      )}
    </button>
  );
}

function SidebarContent({
  pathname,
  onNavClick,
}: {
  pathname: string;
  onNavClick?: () => void;
}) {
  return (
    <div className="flex flex-col flex-grow bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 pt-5 pb-4 overflow-y-auto h-full">
      <div className="flex items-center flex-shrink-0 px-4 mb-6">
        <Shield className="w-8 h-8 text-blue-600 dark:text-blue-400" />
        <span className="ml-2 text-xl font-bold text-gray-900 dark:text-gray-100">
          FortressFlow
        </span>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {/* AI Assistant — primary nav item */}
        <AIAssistantButton onNavClick={onNavClick} />

        <div className="my-2 border-t border-gray-100 dark:border-gray-800" />

        {navItems.map((item) => (
          <NavLink
            key={item.href}
            href={item.href}
            label={item.label}
            icon={item.icon}
            pathname={pathname}
            onClick={onNavClick}
          />
        ))}
      </nav>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 z-30">
        <SidebarContent pathname={pathname} />
      </aside>

      {/* Mobile sidebar via Sheet */}
      <div className="md:hidden fixed top-3 left-4 z-40">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <button
              type="button"
              aria-label="Open navigation"
              className="p-2 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 shadow-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800">
            <SheetHeader className="sr-only">
              <SheetTitle>Navigation</SheetTitle>
            </SheetHeader>
            <SidebarContent
              pathname={pathname}
              onNavClick={() => setMobileOpen(false)}
            />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
