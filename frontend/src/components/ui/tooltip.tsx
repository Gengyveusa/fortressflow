"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

interface TooltipProviderProps {
  children: React.ReactNode
}

const TooltipProvider = ({ children }: TooltipProviderProps) => {
  return <>{children}</>
}
TooltipProvider.displayName = "TooltipProvider"

const Tooltip = ({ children }: { children: React.ReactNode }) => {
  return <div className="relative inline-flex group">{children}</div>
}
Tooltip.displayName = "Tooltip"

const TooltipTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ className, ...props }, ref) => (
  <button ref={ref} className={cn("inline-flex", className)} {...props} />
))
TooltipTrigger.displayName = "TooltipTrigger"

const TooltipContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    side?: "top" | "bottom" | "left" | "right"
  }
>(({ className, side = "top", ...props }, ref) => (
  <div
    ref={ref}
    role="tooltip"
    className={cn(
      "invisible group-hover:visible absolute z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95",
      side === "top" && "bottom-full left-1/2 -translate-x-1/2 mb-2",
      side === "bottom" && "top-full left-1/2 -translate-x-1/2 mt-2",
      side === "left" && "right-full top-1/2 -translate-y-1/2 mr-2",
      side === "right" && "left-full top-1/2 -translate-y-1/2 ml-2",
      className
    )}
    {...props}
  />
))
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
