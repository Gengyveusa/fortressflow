import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  plans: [
    {
      id: "plan-starter",
      name: "Starter",
      tier: "free",
      max_users: 3,
      features: ["Basic CRM", "Email Integration", "Community Access"],
      monthly_price: 0,
    },
    {
      id: "plan-pro",
      name: "Professional",
      tier: "pro",
      max_users: 25,
      features: ["Advanced CRM", "Call Analytics", "Deduplication", "Experiments", "API Access"],
      monthly_price: 49,
    },
    {
      id: "plan-enterprise",
      name: "Enterprise",
      tier: "enterprise",
      max_users: -1,
      features: ["Everything in Pro", "SSO/SAML", "Custom Plugins", "Priority Support", "SLA"],
      monthly_price: 149,
    },
  ],
  current_plan: "plan-pro",
  usage: {
    users: 12,
    max_users: 25,
    api_calls_this_month: 48200,
    api_limit: 100000,
  },
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/auth/packaging");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
