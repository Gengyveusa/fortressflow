"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, Users, Search, Upload, ChevronLeft, ChevronRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { leadsApi, type Lead } from "@/lib/api";

export default function LeadsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["leads", page],
    queryFn: () => leadsApi.list(page, 20).then((r) => r.data),
  });

  const leads: Lead[] = data?.items ?? [];
  const totalPages = data?.pages ?? 1;

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
            <Link href="/leads" className="text-blue-600">Leads</Link>
            <Link href="/sequences">Sequences</Link>
            <Link href="/compliance">Compliance</Link>
            <Link href="/analytics">Analytics</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
            <p className="text-gray-500 mt-1">Manage verified contacts and consent status</p>
          </div>
          <Link
            href="/leads/import"
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            <Upload className="w-4 h-4" />
            Import Leads
          </Link>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="p-4 border-b border-gray-200">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search leads by name, email, or company..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            {isLoading ? (
              <div className="p-8 text-center text-gray-500">Loading leads...</div>
            ) : error ? (
              <div className="p-8 text-center text-red-500">
                Could not load leads. Make sure the backend is running.
              </div>
            ) : leads.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Users className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p className="font-medium">No leads yet</p>
                <p className="text-sm mt-1">Import a CSV to get started</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Company</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Title</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Source</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Verified</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.map((lead) => (
                    <tr key={lead.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {lead.first_name} {lead.last_name}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{lead.email}</td>
                      <td className="px-4 py-3 text-gray-600">{lead.company ?? "—"}</td>
                      <td className="px-4 py-3 text-gray-600">{lead.title ?? "—"}</td>
                      <td className="px-4 py-3 text-gray-600">{lead.source}</td>
                      <td className="px-4 py-3">
                        {lead.meeting_verified ? (
                          <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-1 rounded-full">
                            ✓ Verified
                          </span>
                        ) : (
                          <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                            Unverified
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {totalPages > 1 && (
            <div className="p-4 border-t border-gray-200 flex items-center justify-between">
              <span className="text-sm text-gray-500">
                Page {page} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-2 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-2 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
