import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({
    rendered_subject: "Quick question about AcmeTech",
    rendered_plain_body: "Hi Sarah,\n\nI noticed AcmeTech is growing fast...",
    rendered_html_body: null,
    variables_used: ["first_name", "company"],
    warnings: [],
  });
}
