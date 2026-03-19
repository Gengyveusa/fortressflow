"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { ToastVariant } from "@/components/ui/toast";

export interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  open: boolean;
}

export interface ToastOptions {
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

// Global store using a simple pub/sub pattern
type Listener = (toasts: ToastItem[]) => void;
const listeners: Set<Listener> = new Set();
let toasts: ToastItem[] = [];
const timers = new Map<string, ReturnType<typeof setTimeout>>();

function notify() {
  const snapshot = [...toasts];
  listeners.forEach((l) => l(snapshot));
}

function addToast(options: ToastOptions): string {
  const id = Math.random().toString(36).slice(2);
  const item: ToastItem = {
    id,
    title: options.title,
    description: options.description,
    variant: options.variant ?? "default",
    open: true,
  };
  toasts = [item, ...toasts].slice(0, 5); // max 5 toasts
  notify();

  const duration = options.duration ?? 5000;
  const timer = setTimeout(() => {
    dismissToast(id);
  }, duration);
  timers.set(id, timer);

  return id;
}

function dismissToast(id: string) {
  toasts = toasts.map((t) => (t.id === id ? { ...t, open: false } : t));
  notify();
  // Remove from array after animation
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    notify();
    if (timers.has(id)) {
      clearTimeout(timers.get(id));
      timers.delete(id);
    }
  }, 300);
}

export function useToast() {
  const [localToasts, setLocalToasts] = useState<ToastItem[]>([...toasts]);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    const listener: Listener = (updated) => {
      if (isMountedRef.current) setLocalToasts(updated);
    };
    listeners.add(listener);
    return () => {
      isMountedRef.current = false;
      listeners.delete(listener);
    };
  }, []);

  const toast = useCallback((options: ToastOptions) => {
    return addToast(options);
  }, []);

  const dismiss = useCallback((id: string) => {
    dismissToast(id);
  }, []);

  return { toast, toasts: localToasts, dismiss };
}

// Standalone toast function for use outside React components
export const toast = (options: ToastOptions) => addToast(options);
