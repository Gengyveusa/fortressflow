"use client";

import Link from "next/link";
import { Bell, Search, User, Sun, Moon } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useTheme } from "@/app/providers";

export function Header() {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-20 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 transition-colors">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3 flex-1 max-w-md">
          <Search className="w-4 h-4 text-gray-400 dark:text-gray-500 flex-shrink-0" />
          <Input
            type="search"
            placeholder="Search leads, sequences..."
            className="h-9 border-0 bg-gray-50 dark:bg-gray-800 dark:text-gray-200 dark:placeholder-gray-500 focus-visible:ring-1"
          />
        </div>
        <div className="flex items-center gap-2">
          {/* Dark mode toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
          >
            {theme === "dark" ? (
              <Sun className="w-5 h-5" />
            ) : (
              <Moon className="w-5 h-5" />
            )}
          </button>

          {/* Notifications */}
          <button
            type="button"
            className="relative p-2 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
          </button>

          {/* User */}
          <Link
            href="/profile"
            className="flex items-center gap-2 pl-3 ml-1 border-l border-gray-200 dark:border-gray-700 hover:opacity-80 transition-opacity"
          >
            <div className="w-8 h-8 rounded-full bg-blue-600 dark:bg-blue-500 flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300 hidden lg:block">
              Profile
            </span>
          </Link>
        </div>
      </div>
    </header>
  );
}
