import Link from "next/link";
import { Users, Shield, Activity, TrendingUp } from "lucide-react";

export default function Dashboard() {
  const stats = [
    {
      title: "Total Leads",
      value: "0",
      icon: Users,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      title: "Consents Active",
      value: "0",
      icon: Shield,
      color: "text-green-600",
      bg: "bg-green-50",
    },
    {
      title: "Touches Sent",
      value: "0",
      icon: Activity,
      color: "text-purple-600",
      bg: "bg-purple-50",
    },
    {
      title: "Response Rate",
      value: "0%",
      icon: TrendingUp,
      color: "text-orange-600",
      bg: "bg-orange-50",
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-600" />
            <span className="text-xl font-bold text-gray-900">FortressFlow</span>
          </div>
          <div className="flex items-center gap-6 text-sm font-medium text-gray-600">
            <Link href="/" className="text-blue-600">
              Dashboard
            </Link>
            <Link href="/leads">Leads</Link>
            <Link href="/sequences">Sequences</Link>
            <Link href="/compliance">Compliance</Link>
            <Link href="/analytics">Analytics</Link>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">
            Compliance-first B2B outreach platform
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat) => (
            <div
              key={stat.title}
              className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm"
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-medium text-gray-500">
                  {stat.title}
                </span>
                <div className={`p-2 rounded-lg ${stat.bg}`}>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
              </div>
              <div className="text-3xl font-bold text-gray-900">
                {stat.value}
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Quick Actions
            </h2>
            <div className="space-y-3">
              <Link
                href="/leads/import"
                className="flex items-center gap-3 p-3 rounded-lg bg-blue-50 hover:bg-blue-100 transition-colors"
              >
                <Users className="w-5 h-5 text-blue-600" />
                <div>
                  <div className="font-medium text-blue-900">Import Leads</div>
                  <div className="text-xs text-blue-600">
                    Upload CSV with verified contacts
                  </div>
                </div>
              </Link>
              <Link
                href="/sequences/new"
                className="flex items-center gap-3 p-3 rounded-lg bg-purple-50 hover:bg-purple-100 transition-colors"
              >
                <Activity className="w-5 h-5 text-purple-600" />
                <div>
                  <div className="font-medium text-purple-900">
                    Create Sequence
                  </div>
                  <div className="text-xs text-purple-600">
                    Build a multi-touch outreach flow
                  </div>
                </div>
              </Link>
              <Link
                href="/compliance"
                className="flex items-center gap-3 p-3 rounded-lg bg-green-50 hover:bg-green-100 transition-colors"
              >
                <Shield className="w-5 h-5 text-green-600" />
                <div>
                  <div className="font-medium text-green-900">
                    Compliance Check
                  </div>
                  <div className="text-xs text-green-600">
                    Verify consent and DNC status
                  </div>
                </div>
              </Link>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Compliance Status
            </h2>
            <div className="space-y-3">
              {[
                { label: "Email consent gate", status: "active" },
                { label: "SMS consent gate", status: "active" },
                { label: "LinkedIn consent gate", status: "active" },
                { label: "DNC checks enabled", status: "active" },
                { label: "Audit logging active", status: "active" },
                { label: "One-click unsubscribe", status: "active" },
              ].map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between"
                >
                  <span className="text-sm text-gray-600">{item.label}</span>
                  <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-1 rounded-full">
                    ✓ {item.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
