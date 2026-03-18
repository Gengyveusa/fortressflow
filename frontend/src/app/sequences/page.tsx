import Link from "next/link";
import { Shield, Plus, Activity, Play, Pause } from "lucide-react";

const MOCK_SEQUENCES = [
  {
    id: "1",
    name: "Cold Outreach - SaaS",
    steps: 5,
    enrolled: 0,
    status: "draft",
    channels: ["email", "linkedin"],
  },
  {
    id: "2",
    name: "Follow-up Sequence",
    steps: 3,
    enrolled: 0,
    status: "draft",
    channels: ["email"],
  },
];

export default function SequencesPage() {
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
            <Link href="/sequences" className="text-blue-600">
              Sequences
            </Link>
            <Link href="/compliance">Compliance</Link>
            <Link href="/analytics">Analytics</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Sequences</h1>
            <p className="text-gray-500 mt-1">
              Build and manage multi-touch outreach flows
            </p>
          </div>
          <Link
            href="/sequences/new"
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Sequence
          </Link>
        </div>

        <div className="grid gap-4">
          {MOCK_SEQUENCES.map((seq) => (
            <div
              key={seq.id}
              className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div className="p-3 bg-purple-50 rounded-lg">
                  <Activity className="w-6 h-6 text-purple-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{seq.name}</h3>
                  <p className="text-sm text-gray-500">
                    {seq.steps} steps · {seq.enrolled} enrolled ·{" "}
                    {seq.channels.join(", ")}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs font-medium px-2 py-1 rounded-full ${
                    seq.status === "active"
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {seq.status}
                </span>
                <button className="p-2 rounded-lg hover:bg-gray-100 text-gray-500">
                  {seq.status === "active" ? (
                    <Pause className="w-4 h-4" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                </button>
                <Link
                  href={`/sequences/${seq.id}`}
                  className="text-sm font-medium text-blue-600 hover:text-blue-700"
                >
                  Edit
                </Link>
              </div>
            </div>
          ))}
        </div>

        {MOCK_SEQUENCES.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-sm">
            <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="font-medium text-gray-700">No sequences yet</p>
            <p className="text-sm text-gray-500 mt-1 mb-4">
              Create your first outreach sequence to get started
            </p>
            <Link
              href="/sequences/new"
              className="inline-flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              New Sequence
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
