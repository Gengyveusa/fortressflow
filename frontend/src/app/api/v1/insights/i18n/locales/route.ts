import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  default_locale: "en-US",
  supported_locales: [
    { code: "en-US", name: "English (US)", coverage: 100, status: "active" },
    { code: "es-ES", name: "Spanish (Spain)", coverage: 94, status: "active" },
    { code: "fr-FR", name: "French (France)", coverage: 91, status: "active" },
    { code: "de-DE", name: "German (Germany)", coverage: 88, status: "active" },
    { code: "pt-BR", name: "Portuguese (Brazil)", coverage: 85, status: "active" },
    { code: "ja-JP", name: "Japanese", coverage: 78, status: "beta" },
    { code: "zh-CN", name: "Chinese (Simplified)", coverage: 72, status: "beta" },
  ],
  total_keys: 1842,
  last_updated: "2026-03-26T09:15:00Z",
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/i18n/locales");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
