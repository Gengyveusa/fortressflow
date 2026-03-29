import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total_plugins: 28,
  installed: 6,
  available: 22,
  categories: ["CRM", "Analytics", "Communication", "Data Enrichment", "Automation"],
  plugins: [
    {
      id: "plg-001",
      name: "Salesforce Sync",
      category: "CRM",
      installed: true,
      version: "2.3.1",
      rating: 4.7,
      description: "Bi-directional sync with Salesforce CRM",
    },
    {
      id: "plg-002",
      name: "Slack Notifications",
      category: "Communication",
      installed: true,
      version: "1.8.0",
      rating: 4.5,
      description: "Real-time alerts and updates in Slack channels",
    },
    {
      id: "plg-003",
      name: "Clearbit Enrichment",
      category: "Data Enrichment",
      installed: false,
      version: "3.1.0",
      rating: 4.8,
      description: "Auto-enrich contacts with firmographic data",
    },
    {
      id: "plg-004",
      name: "Zapier Workflows",
      category: "Automation",
      installed: false,
      version: "2.0.4",
      rating: 4.3,
      description: "Connect to 5000+ apps via Zapier triggers and actions",
    },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/plugins/marketplace");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
