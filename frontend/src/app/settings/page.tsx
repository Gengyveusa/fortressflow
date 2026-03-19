"use client";

import { useState } from "react";
import {
  Settings,
  Key,
  Flame,
  AlertTriangle,
  Mail,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Plus,
  Trash2,
  RefreshCw,
  Save,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { useSettings } from "@/lib/hooks";
import { useToast } from "@/lib/hooks/use-toast";

// ── Types ─────────────────────────────────────────────────
interface ApiKeyEntry {
  name: string;
  label: string;
  description: string;
  placeholder: string;
}

interface SendingIdentity {
  id: string;
  email: string;
  name: string;
  status: "active" | "warming" | "paused";
}

// ── Static config ─────────────────────────────────────────
const API_KEYS: ApiKeyEntry[] = [
  { name: "hubspot",  label: "HubSpot",  description: "CRM integration for lead sync", placeholder: "pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
  { name: "zoominfo", label: "ZoomInfo", description: "Enrichment & contact data", placeholder: "eyJhbGciOiJSUzI1NiJ9..." },
  { name: "apollo",   label: "Apollo.io", description: "Prospecting & lead database", placeholder: "apk_xxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "twilio",   label: "Twilio",   description: "SMS sending via Twilio", placeholder: "SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "aws_ses",  label: "AWS SES",  description: "Email delivery via Amazon SES", placeholder: "AKIAIOSFODNN7EXAMPLE" },
];

const DEFAULT_IDENTITIES: SendingIdentity[] = [
  { id: "1", email: "outreach@fortressflow.io",   name: "FortressFlow Outreach", status: "active"  },
  { id: "2", email: "sales@fortressflow.io",       name: "FortressFlow Sales",    status: "warming" },
  { id: "3", email: "noreply@fortressflow.io",     name: "FortressFlow NoReply",  status: "paused"  },
];

// ── Masked key display ────────────────────────────────────
function maskKey(key: string): string {
  if (!key || key.length < 8) return "•".repeat(key.length || 8);
  return key.slice(0, 6) + "•".repeat(Math.max(0, key.length - 10)) + key.slice(-4);
}

// ── Status badge ──────────────────────────────────────────
function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <Badge
      className={
        connected
          ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
          : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
      }
    >
      {connected ? (
        <CheckCircle2 className="h-3 w-3 mr-1" />
      ) : (
        <XCircle className="h-3 w-3 mr-1" />
      )}
      {connected ? "Connected" : "Not configured"}
    </Badge>
  );
}

// ── Identity status badge ─────────────────────────────────
function IdentityBadge({ status }: { status: SendingIdentity["status"] }) {
  const map = {
    active:  "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    warming: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    paused:  "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  };
  return <Badge className={map[status]}>{status}</Badge>;
}

// ── API Keys Tab ──────────────────────────────────────────
function ApiKeysTab() {
  const { settings, updateSettings } = useSettings();
  const { toast } = useToast();
  const [editing, setEditing] = useState<string | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});

  const startEdit = (name: string) => {
    setDraftKeys((prev) => ({ ...prev, [name]: settings.apiKeys?.[name] ?? "" }));
    setEditing(name);
  };

  const saveKey = (name: string) => {
    updateSettings({
      apiKeys: { ...(settings.apiKeys ?? {}), [name]: draftKeys[name] ?? "" },
    });
    setEditing(null);
    toast({ title: "API key saved", variant: "success" });
  };

  const clearKey = (name: string) => {
    const updated = { ...(settings.apiKeys ?? {}) };
    delete updated[name];
    updateSettings({ apiKeys: updated });
    setEditing(null);
    toast({ title: "API key removed" });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Configure your third-party integration credentials. Keys are stored locally and never logged.
      </p>
      {API_KEYS.map((entry) => {
        const storedKey = settings.apiKeys?.[entry.name] ?? "";
        const hasKey = !!storedKey;
        const isEditing = editing === entry.name;
        const isVisible = visible[entry.name];

        return (
          <Card key={entry.name} className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-semibold dark:text-gray-100">
                    {entry.label}
                  </CardTitle>
                  <CardDescription className="text-xs dark:text-gray-400">
                    {entry.description}
                  </CardDescription>
                </div>
                <StatusBadge connected={hasKey} />
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {isEditing ? (
                <div className="flex gap-2">
                  <Input
                    type={isVisible ? "text" : "password"}
                    placeholder={entry.placeholder}
                    value={draftKeys[entry.name] ?? ""}
                    onChange={(e) =>
                      setDraftKeys((p) => ({ ...p, [entry.name]: e.target.value }))
                    }
                    className="font-mono text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => setVisible((p) => ({ ...p, [entry.name]: !isVisible }))}
                    className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                  >
                    {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                  <Button size="sm" onClick={() => saveKey(entry.name)}>
                    <Save className="h-4 w-4 mr-1" /> Save
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setEditing(null)}
                    className="dark:border-gray-700 dark:text-gray-300">
                    Cancel
                  </Button>
                </div>
              ) : hasKey ? (
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-3 py-2 font-mono text-gray-600 dark:text-gray-300">
                    {maskKey(storedKey)}
                  </code>
                  <Button size="sm" variant="outline" onClick={() => startEdit(entry.name)}
                    className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
                    <Key className="h-4 w-4 mr-1" /> Edit
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => clearKey(entry.name)}
                    className="text-red-500 hover:text-red-700 dark:hover:bg-gray-800">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <Button size="sm" variant="outline" onClick={() => startEdit(entry.name)}
                  className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
                  <Plus className="h-4 w-4 mr-1" /> Add Key
                </Button>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

// ── Warmup Config Tab ─────────────────────────────────────
function WarmupConfigTab() {
  const { settings, updateSettings } = useSettings();
  const { toast } = useToast();
  const warmup = settings.warmup ?? {
    volumeCap: 200,
    rampMultiplier: 1.5,
    initialDailyVolume: 20,
    durationWeeks: 6,
  };

  const [draft, setDraft] = useState(warmup);

  const save = () => {
    updateSettings({ warmup: draft });
    toast({ title: "Warmup config saved", variant: "success" });
  };

  type DraftKey = keyof typeof draft;

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Configure email warmup behavior. Changes take effect on the next warmup cycle.
      </p>
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm dark:text-gray-100">Warmup Schedule</CardTitle>
          <CardDescription className="dark:text-gray-400">
            These values control how inbox warmup volumes ramp over time.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {[
            { key: "initialDailyVolume" as DraftKey, label: "Initial Daily Volume", description: "Emails per day at start", min: 5, max: 100 },
            { key: "volumeCap" as DraftKey, label: "Volume Cap", description: "Max emails per day after ramp", min: 50, max: 2000 },
            { key: "rampMultiplier" as DraftKey, label: "Ramp Multiplier", description: "Daily volume growth factor", min: 1.1, max: 3.0, step: 0.1 },
            { key: "durationWeeks" as DraftKey, label: "Duration (weeks)", description: "Total warmup duration", min: 2, max: 16 },
          ].map(({ key, label, description, min, max, step = 1 }) => (
            <div key={key} className="space-y-2">
              <Label className="dark:text-gray-300">{label}</Label>
              <p className="text-xs text-gray-400 dark:text-gray-500 -mt-1">{description}</p>
              <Input
                type="number"
                min={min}
                max={max}
                step={step}
                value={draft[key] as number}
                onChange={(e) =>
                  setDraft((p) => ({
                    ...p,
                    [key]: parseFloat(e.target.value) || 0,
                  }))
                }
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
              <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500">
                <span>Min: {min}</span>
                <span>Max: {max}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm dark:text-gray-100">Current Thresholds</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Start Vol.", value: draft.initialDailyVolume },
              { label: "Cap Vol.", value: draft.volumeCap },
              { label: "Multiplier", value: `×${draft.rampMultiplier}` },
              { label: "Duration", value: `${draft.durationWeeks}w` },
            ].map(({ label, value }) => (
              <div key={label} className="text-center p-3 rounded-lg bg-gray-50 dark:bg-gray-800">
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{value}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{label}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Button onClick={save} className="w-full sm:w-auto">
        <Save className="h-4 w-4 mr-2" /> Save Warmup Config
      </Button>
    </div>
  );
}

// ── Alert Thresholds Tab ──────────────────────────────────
function AlertThresholdsTab() {
  const { settings, updateSettings } = useSettings();
  const { toast } = useToast();
  const thresholds = settings.alertThresholds ?? {
    bounceRatePause: 5,
    spamRatePause: 0.1,
    openRateMinimum: 10,
  };
  const [draft, setDraft] = useState(thresholds);

  const getBounceColor = (v: number) =>
    v <= 2 ? "text-green-600 dark:text-green-400" : v <= 5 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400";
  const getSpamColor  = (v: number) =>
    v <= 0.08 ? "text-green-600 dark:text-green-400" : v <= 0.3 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400";
  const getOpenColor  = (v: number) =>
    v >= 20 ? "text-green-600 dark:text-green-400" : v >= 10 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400";

  const save = () => {
    updateSettings({ alertThresholds: draft });
    toast({ title: "Alert thresholds saved", variant: "success" });
  };

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Define thresholds that trigger automatic pausing or alerts for deliverability issues.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Bounce rate */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm dark:text-gray-100 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              Bounce Rate Pause
            </CardTitle>
            <CardDescription className="dark:text-gray-400 text-xs">
              Auto-pause sequence when bounce rate exceeds this %
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={20}
                step={0.5}
                value={draft.bounceRatePause}
                onChange={(e) => setDraft((p) => ({ ...p, bounceRatePause: parseFloat(e.target.value) || 0 }))}
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
              <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
            </div>
            <div className={`text-2xl font-bold ${getBounceColor(draft.bounceRatePause)}`}>
              {draft.bounceRatePause}%
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {draft.bounceRatePause <= 2 ? "✓ Excellent threshold" : draft.bounceRatePause <= 5 ? "⚠ Acceptable" : "✗ Too permissive"}
            </p>
          </CardContent>
        </Card>

        {/* Spam rate */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm dark:text-gray-100 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              Spam Rate Pause
            </CardTitle>
            <CardDescription className="dark:text-gray-400 text-xs">
              Auto-pause when spam complaint rate exceeds this %
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={0.01}
                max={2}
                step={0.01}
                value={draft.spamRatePause}
                onChange={(e) => setDraft((p) => ({ ...p, spamRatePause: parseFloat(e.target.value) || 0 }))}
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
              <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
            </div>
            <div className={`text-2xl font-bold ${getSpamColor(draft.spamRatePause)}`}>
              {draft.spamRatePause}%
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {draft.spamRatePause <= 0.08 ? "✓ Google/Yahoo compliant" : draft.spamRatePause <= 0.3 ? "⚠ Watch carefully" : "✗ Risky threshold"}
            </p>
          </CardContent>
        </Card>

        {/* Open rate minimum */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm dark:text-gray-100 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
              Open Rate Minimum
            </CardTitle>
            <CardDescription className="dark:text-gray-400 text-xs">
              Alert when open rate falls below this %
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={50}
                step={1}
                value={draft.openRateMinimum}
                onChange={(e) => setDraft((p) => ({ ...p, openRateMinimum: parseFloat(e.target.value) || 0 }))}
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
              <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
            </div>
            <div className={`text-2xl font-bold ${getOpenColor(draft.openRateMinimum)}`}>
              {draft.openRateMinimum}%
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {draft.openRateMinimum >= 20 ? "✓ Healthy target" : draft.openRateMinimum >= 10 ? "⚠ Moderate" : "✗ Very low bar"}
            </p>
          </CardContent>
        </Card>
      </div>

      <Button onClick={save} className="w-full sm:w-auto">
        <Save className="h-4 w-4 mr-2" /> Save Thresholds
      </Button>
    </div>
  );
}

// ── Sending Identity Tab ──────────────────────────────────
function SendingIdentityTab() {
  const { toast } = useToast();
  const [identities, setIdentities] = useState<SendingIdentity[]>(DEFAULT_IDENTITIES);
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");

  const addIdentity = () => {
    if (!newEmail.trim() || !newName.trim()) return;
    setIdentities((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).slice(2),
        email: newEmail.trim(),
        name: newName.trim(),
        status: "paused",
      },
    ]);
    setNewEmail("");
    setNewName("");
    toast({ title: "Sending identity added", variant: "success" });
  };

  const removeIdentity = (id: string) => {
    setIdentities((prev) => prev.filter((i) => i.id !== id));
    toast({ title: "Sending identity removed" });
  };

  const cycleStatus = (id: string) => {
    const cycle: Record<SendingIdentity["status"], SendingIdentity["status"]> = {
      active: "paused",
      warming: "active",
      paused: "warming",
    };
    setIdentities((prev) =>
      prev.map((i) => (i.id === id ? { ...i, status: cycle[i.status] } : i))
    );
  };

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Manage sending identities for email rotation. Active identities are used in round-robin delivery.
      </p>

      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm dark:text-gray-100">Sending Identities</CardTitle>
          <CardDescription className="dark:text-gray-400">
            {identities.filter((i) => i.status === "active").length} active ·{" "}
            {identities.filter((i) => i.status === "warming").length} warming up ·{" "}
            {identities.filter((i) => i.status === "paused").length} paused
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {identities.map((identity) => (
            <div
              key={identity.id}
              className="flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 group"
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-950 flex items-center justify-center">
                  <Mail className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-medium dark:text-gray-200">{identity.name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{identity.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => cycleStatus(identity.id)}
                  title="Click to cycle status"
                >
                  <IdentityBadge status={identity.status} />
                </button>
                <button
                  type="button"
                  onClick={() => cycleStatus(identity.id)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-blue-500 dark:hover:text-blue-400 transition-opacity"
                  title="Cycle rotation status"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => removeIdentity(identity.id)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-opacity"
                  title="Remove identity"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}

          {identities.length === 0 && (
            <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">
              No sending identities configured.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Add new identity */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm dark:text-gray-100">Add Identity</CardTitle>
          <CardDescription className="dark:text-gray-400">
            New identities start in paused state — begin warmup before activating.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 space-y-1">
              <Label className="text-xs dark:text-gray-300">Display Name</Label>
              <Input
                placeholder="e.g. Sales Team"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <div className="flex-1 space-y-1">
              <Label className="text-xs dark:text-gray-300">Email Address</Label>
              <Input
                type="email"
                placeholder="e.g. sales@yourdomain.com"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={addIdentity}
                disabled={!newEmail.trim() || !newName.trim()}
                className="w-full sm:w-auto"
              >
                <Plus className="h-4 w-4 mr-1" /> Add
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────
export default function SettingsPage() {
  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800">
          <Settings className="h-5 w-5 text-gray-600 dark:text-gray-300" />
        </div>
        <div>
          <h1 className="text-xl font-semibold dark:text-gray-100">Settings</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Manage integrations, warmup config, and alert thresholds.
          </p>
        </div>
      </div>

      <Separator className="dark:border-gray-800" />

      <Tabs defaultValue="api-keys">
        <TabsList className="dark:bg-gray-800 flex-wrap h-auto gap-1">
          <TabsTrigger value="api-keys" className="dark:text-gray-400 dark:data-[state=active]:bg-gray-700 dark:data-[state=active]:text-gray-100">
            <Key className="h-4 w-4 mr-1.5" /> API Keys
          </TabsTrigger>
          <TabsTrigger value="warmup" className="dark:text-gray-400 dark:data-[state=active]:bg-gray-700 dark:data-[state=active]:text-gray-100">
            <Flame className="h-4 w-4 mr-1.5" /> Warmup Config
          </TabsTrigger>
          <TabsTrigger value="alerts" className="dark:text-gray-400 dark:data-[state=active]:bg-gray-700 dark:data-[state=active]:text-gray-100">
            <AlertTriangle className="h-4 w-4 mr-1.5" /> Alert Thresholds
          </TabsTrigger>
          <TabsTrigger value="identity" className="dark:text-gray-400 dark:data-[state=active]:bg-gray-700 dark:data-[state=active]:text-gray-100">
            <Mail className="h-4 w-4 mr-1.5" /> Sending Identity
          </TabsTrigger>
        </TabsList>

        <div className="mt-6">
          <TabsContent value="api-keys">
            <ApiKeysTab />
          </TabsContent>
          <TabsContent value="warmup">
            <WarmupConfigTab />
          </TabsContent>
          <TabsContent value="alerts">
            <AlertThresholdsTab />
          </TabsContent>
          <TabsContent value="identity">
            <SendingIdentityTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
