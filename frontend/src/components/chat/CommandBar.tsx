"use client";

import { Rocket, BarChart3, Search, Mail, GitBranch, Flame, Shield, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { SLASH_COMMANDS, QUICK_ACTIONS } from "./types";

// ── Icon mapping ────────────────────────────────────────────────────────────

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  rocket: Rocket,
  chart: BarChart3,
  search: Search,
  mail: Mail,
  users: Search,
  "git-branch": GitBranch,
  flame: Flame,
  shield: Shield,
  help: HelpCircle,
};

// ── Slash Command Menu ──────────────────────────────────────────────────────

interface SlashMenuProps {
  filter: string;
  selectedIndex: number;
  onSelect: (command: string) => void;
  onHover: (index: number) => void;
}

export function SlashMenu({ filter, selectedIndex, onSelect, onHover }: SlashMenuProps) {
  const filtered = SLASH_COMMANDS.filter((c) =>
    c.command.toLowerCase().startsWith(filter.toLowerCase())
  );

  if (filtered.length === 0) return null;

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 max-h-48 overflow-y-auto flex-shrink-0">
      {filtered.map((cmd, i) => {
        const Icon = iconMap[cmd.icon] || HelpCircle;
        return (
          <button
            key={cmd.command}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors",
              i === selectedIndex && "bg-blue-50 dark:bg-blue-900/20"
            )}
            onClick={() => onSelect(cmd.command)}
            onMouseEnter={() => onHover(i)}
          >
            <Icon className="w-4 h-4 text-gray-400 dark:text-gray-500 flex-shrink-0" />
            <code className="text-blue-600 dark:text-blue-400 text-xs font-mono font-semibold flex-shrink-0">
              {cmd.command}
            </code>
            <span className="text-gray-500 dark:text-gray-400 text-xs truncate">
              {cmd.description}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Quick Action Chips ──────────────────────────────────────────────────────

interface QuickActionsProps {
  onAction: (message: string) => void;
}

export function QuickActions({ onAction }: QuickActionsProps) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 overflow-x-auto flex-shrink-0">
      {QUICK_ACTIONS.map((action) => {
        const Icon = iconMap[action.icon] || Rocket;
        return (
          <button
            key={action.label}
            onClick={() => onAction(action.message)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap",
              "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400",
              "hover:bg-blue-50 dark:hover:bg-blue-950/30 hover:text-blue-600 dark:hover:text-blue-400",
              "border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700",
              "transition-colors"
            )}
          >
            <Icon className="w-3 h-3" />
            {action.label}
          </button>
        );
      })}
    </div>
  );
}
