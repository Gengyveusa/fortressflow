"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { Toaster } from "@/components/ui/toaster";
import { ChatPanelProvider } from "@/components/chat/ChatPanelContext";

// ── QueryClient singleton ─────────────────────────────
// Use a module-scoped singleton so the QueryClient is available
// immediately during hydration. On the server a new instance is
// created per request; in the browser the same instance is reused.
// This avoids the race condition where page components that load
// heavy async chunks (e.g. recharts) call useQuery() before the
// layout's useState initialiser has run during streaming hydration.

let browserQueryClient: QueryClient | undefined;

function getQueryClient(): QueryClient {
  const opts = { defaultOptions: { queries: { staleTime: 60 * 1000 } } };
  if (typeof window === "undefined") {
    // Server: always create a fresh client (no cross-request leakage)
    return new QueryClient(opts);
  }
  // Browser: reuse the same singleton across renders
  if (!browserQueryClient) {
    browserQueryClient = new QueryClient(opts);
  }
  return browserQueryClient;
}

// ── Theme Context ──────────────────────────────────────

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  toggleTheme: () => {},
  setTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");

  // Read from localStorage on mount and apply
  useEffect(() => {
    try {
      const stored = localStorage.getItem("fortressflow-theme") as Theme | null;
      const preferred = stored ?? "dark";
      setThemeState(preferred);
      applyTheme(preferred);
    } catch {
      // SSR or blocked localStorage — ignore
    }
  }, []);

  const applyTheme = (t: Theme) => {
    const root = document.documentElement;
    if (t === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  };

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    applyTheme(t);
    try {
      localStorage.setItem("fortressflow-theme", t);
    } catch {
      // ignore
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem("fortressflow-theme", next);
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

// ── Root Providers ─────────────────────────────────────

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ChatPanelProvider>
          {children}
          <Toaster />
        </ChatPanelProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
