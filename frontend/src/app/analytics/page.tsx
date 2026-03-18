import Link from "next/link";
import { Shield, TrendingUp, BarChart2, Activity } from "lucide-react";

export default function AnalyticsPage() {
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
            <Link href="/compliance">Compliance</Link>
            <Link href="/analytics" className="text-blue-600">
              Analytics
            </Link>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="text-gray-500 mt-1">
            Delivery rates, response rates, and compliance metrics
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[
            { label: "Open Rate", value: "—", icon: Activity, color: "text-blue-600", bg: "bg-blue-50" },
            { label: "Reply Rate", value: "—", icon: TrendingUp, color: "text-green-600", bg: "bg-green-50" },
            { label: "Bounce Rate", value: "—", icon: BarChart2, color: "text-red-600", bg: "bg-red-50" },
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
              <p className="text-xs text-gray-400 mt-2">Connect backend to see live data</p>
            </div>
          ))}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm text-center">
          <BarChart2 className="w-16 h-16 mx-auto mb-4 text-gray-200" />
          <p className="text-gray-600 font-medium">Analytics data will appear here</p>
          <p className="text-sm text-gray-400 mt-1">
            Start sending sequences to track performance metrics
          </p>
        </div>
      </main>
    </div>
  );
}
