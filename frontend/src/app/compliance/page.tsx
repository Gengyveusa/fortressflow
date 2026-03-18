"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, CheckCircle, XCircle, AlertTriangle, Search } from "lucide-react";
import { complianceApi } from "@/lib/api";

const CHANNEL_OPTIONS = ["email", "sms", "linkedin"] as const;

interface CheckResult {
  can_send: boolean;
  reason: string;
}

export default function CompliancePage() {
  const [leadId, setLeadId] = useState("");
  const [channel, setChannel] = useState<string>("email");
  const [result, setResult] = useState<CheckResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  const handleCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadId.trim()) return;
    setChecking(true);
    setResult(null);
    setError("");
    try {
      const res = await complianceApi.check(leadId.trim(), channel);
      setResult(res.data);
    } catch {
      setError("Check failed. Verify the lead ID and backend connectivity.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-600" />
            <span className="text-xl font-bold text-gray-900">FortressFlow</span>
          </div>
          <div className="flex items-center gap-6 text-sm font-medium text-gray-600">
            <Link href="/">Dashboard</Link>
            <Link href="/leads">Leads</Link>
            <Link href="/sequences">Sequences</Link>
            <Link href="/compliance" className="text-blue-600">
              Compliance
            </Link>
            <Link href="/analytics">Analytics</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Compliance</h1>
          <p className="text-gray-500 mt-1">
            Manage consent, DNC lists, and verify outreach eligibility
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {[
            { label: "Active Consents", value: "—", icon: CheckCircle, color: "text-green-600", bg: "bg-green-50" },
            { label: "DNC List Size", value: "—", icon: XCircle, color: "text-red-600", bg: "bg-red-50" },
            { label: "Pending Review", value: "—", icon: AlertTriangle, color: "text-yellow-600", bg: "bg-yellow-50" },
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm"
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-medium text-gray-500">
                  {stat.label}
                </span>
                <div className={`p-2 rounded-lg ${stat.bg}`}>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
              </div>
              <div className="text-3xl font-bold text-gray-900">{stat.value}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Compliance Check Tool */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Search className="w-5 h-5 text-blue-600" />
              Compliance Check
            </h2>
            <form onSubmit={handleCheck} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Lead ID
                </label>
                <input
                  type="text"
                  value={leadId}
                  onChange={(e) => setLeadId(e.target.value)}
                  placeholder="Enter lead UUID..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Channel
                </label>
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {CHANNEL_OPTIONS.map((c) => (
                    <option key={c} value={c}>
                      {c.charAt(0).toUpperCase() + c.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="submit"
                disabled={checking || !leadId.trim()}
                className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium disabled:opacity-50"
              >
                {checking ? "Checking..." : "Run Compliance Check"}
              </button>
            </form>

            {result && (
              <div
                className={`mt-4 p-4 rounded-lg ${result.can_send ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {result.can_send ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-600" />
                  )}
                  <span
                    className={`font-semibold ${result.can_send ? "text-green-800" : "text-red-800"}`}
                  >
                    {result.can_send ? "Can Send" : "Cannot Send"}
                  </span>
                </div>
                <p
                  className={`text-sm ${result.can_send ? "text-green-700" : "text-red-700"}`}
                >
                  {result.reason}
                </p>
              </div>
            )}

            {error && (
              <div className="mt-4 p-4 rounded-lg bg-red-50 border border-red-200">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}
          </div>

          {/* Compliance Rules */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-green-600" />
              Active Rules
            </h2>
            <div className="space-y-3">
              {[
                { rule: "Email consent required before sending", enforced: true },
                { rule: "SMS consent required before sending", enforced: true },
                { rule: "LinkedIn consent required before sending", enforced: true },
                { rule: "Global DNC check on every touch", enforced: true },
                { rule: "Channel DNC check on every touch", enforced: true },
                { rule: "Email: max 100/day per lead", enforced: true },
                { rule: "SMS: max 30/day per lead", enforced: true },
                { rule: "LinkedIn: max 25/day per lead", enforced: true },
                { rule: "HMAC-signed unsubscribe tokens", enforced: true },
                { rule: "SMS STOP keyword auto-DNC", enforced: true },
                { rule: "Full audit trail retained 5+ years", enforced: true },
              ].map((item) => (
                <div
                  key={item.rule}
                  className="flex items-start gap-3 text-sm"
                >
                  <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                  <span className="text-gray-700">{item.rule}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
