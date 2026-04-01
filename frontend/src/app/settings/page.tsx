"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Settings,
  Key,
  Flame,
  AlertTriangle,
  Mail,
  Linkedin,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Plus,
  Trash2,
  RefreshCw,
  Save,
  Bot,
  Cpu,
  Zap,
  Phone,
  Building2,
  Search,
  Telescope,
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
import { settingsApi } from "@/lib/api";
import type { ApiKeyEntry as ApiKeyData, IntegrationStatusEntry } from "@/lib/api";

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
  { name: "groq",     label: "Groq (AI Chat)",   description: "Powers the FortressFlow Assistant chatbot — Llama 3.3 70B", placeholder: "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "openai",   label: "OpenAI (AI Chat Fallback)", description: "Fallback AI model for chatbot — GPT-4o Mini", placeholder: "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "hubspot",  label: "HubSpot",  description: "CRM integration for lead sync", placeholder: "pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
  { name: "zoominfo_client_id", label: "ZoomInfo Client ID", description: "Client ID for ZoomInfo API (RSA private key set via env var)", placeholder: "725d72a6-8bab-4df6-b3aa-xxxxxxxxxxxx" },
  { name: "zoominfo", label: "ZoomInfo API Key", description: "Direct API key for ZoomInfo (alternative to Client ID + private key)", placeholder: "eyJhbGciOiJSUzI1NiJ9..." },
  { name: "apollo",   label: "Apollo.io", description: "Sales intelligence — 210M+ contacts, sequences, deals", placeholder: "apk_xxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "twilio_account_sid", label: "Twilio Account SID", description: "Primary Twilio account SID used for SMS, voice, and verification", placeholder: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "twilio", label: "Twilio Auth Token", description: "Auth token for the Twilio account above", placeholder: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "twilio_phone_number", label: "Twilio Phone Number", description: "Default sending number in E.164 format", placeholder: "+15551234567" },
  { name: "twilio_messaging_service_sid", label: "Twilio Messaging Service SID", description: "Required for scheduling and opt-out list management", placeholder: "MGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "twilio_verify_service_sid", label: "Twilio Verify Service SID", description: "Required for OTP / verification flows", placeholder: "VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" },
  { name: "twilio_whatsapp_number", label: "Twilio WhatsApp Number", description: "WhatsApp-enabled sender, usually your Twilio sandbox or approved WA number", placeholder: "whatsapp:+14155238886" },
  { name: "taplio_webhook", label: "Taplio (Zapier)", description: "Zapier webhook FortressFlow uses to schedule and execute Taplio LinkedIn actions", placeholder: "https://hooks.zapier.com/hooks/catch/..." },
  { name: "aws_ses",  label: "AWS SES",  description: "Email delivery via Amazon SES", placeholder: "AKIAIOSFODNN7EXAMPLE" },
];

const DEFAULT_IDENTITIES: SendingIdentity[] = [
  { id: "1", email: "outreach@fortressflow.io",   name: "FortressFlow Outreach", status: "active"  },
  { id: "2", email: "sales@fortressflow.io",       name: "FortressFlow Sales",    status: "warming" },
  { id: "3", email: "noreply@fortressflow.io",     name: "FortressFlow NoReply",  status: "paused"  },
];

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
  const { toast } = useToast();
  const [editing, setEditing] = useState<string | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [serverKeys, setServerKeys] = useState<Record<string, string>>({});
  const [loadingKeys, setLoadingKeys] = useState(true);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await settingsApi.listApiKeys();
      const map: Record<string, string> = {};
      res.data.forEach((k: ApiKeyData) => { map[k.service_name] = k.masked_key; });
      setServerKeys(map);
    } catch {
      // Silent fail — keys just won't show
    } finally {
      setLoadingKeys(false);
    }
  }, []);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const startEdit = (name: string) => {
    setDraftKeys((prev) => ({ ...prev, [name]: "" }));
    setEditing(name);
  };

  const saveKey = async (name: string) => {
    const key = draftKeys[name]?.trim();
    if (!key) return;
    try {
      const res = await settingsApi.upsertApiKey(name, key);
      setServerKeys((prev) => ({ ...prev, [name]: res.data.masked_key }));
      setEditing(null);
      toast({ title: "API key saved", variant: "success" });
    } catch {
      toast({ title: "Failed to save API key", variant: "destructive" });
    }
  };

  const clearKey = async (name: string) => {
    try {
      await settingsApi.deleteApiKey(name);
      setServerKeys((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
      setEditing(null);
      toast({ title: "API key removed" });
    } catch {
      toast({ title: "Failed to remove API key", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Configure your third-party integration credentials. Keys are encrypted and stored securely on the server.
      </p>
      {loadingKeys ? (
        <p className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">Loading API keys...</p>
      ) : (
        API_KEYS.map((entry) => {
          const maskedKey = serverKeys[entry.name] ?? "";
          const hasKey = !!maskedKey;
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
                      {maskedKey}
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
        })
      )}
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

// ── LinkedIn / Phantombuster Tab ──────────────────────────
function LinkedInTab() {
  const { toast } = useToast();
  const [status, setStatus] = useState<IntegrationStatusEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [serverKeys, setServerKeys] = useState<Record<string, string>>({});

  const linkedinKeys = [
    { name: "phantombuster", label: "Phantombuster API Key", description: "API key from phantombuster.com/api", placeholder: "pb_xxxxxxxxxxxxxxxx" },
    { name: "phantombuster_connect_agent", label: "Connect Agent ID", description: "Phantombuster phantom ID for connection requests", placeholder: "1234567890" },
    { name: "phantombuster_message_agent", label: "Message Agent ID", description: "Phantombuster phantom ID for messages", placeholder: "1234567890" },
  ];

  useEffect(() => {
    (async () => {
      try {
        const [statusRes, keysRes] = await Promise.all([
          settingsApi.integrationStatus(),
          settingsApi.listApiKeys(),
        ]);
        const li = statusRes.data.integrations.find((i) => i.name === "linkedin");
        setStatus(li ?? null);
        const map: Record<string, string> = {};
        keysRes.data.forEach((k: ApiKeyData) => { map[k.service_name] = k.masked_key; });
        setServerKeys(map);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const saveKey = async (name: string) => {
    const key = draftKeys[name]?.trim();
    if (!key) return;
    try {
      const res = await settingsApi.upsertApiKey(name, key);
      setServerKeys((prev) => ({ ...prev, [name]: res.data.masked_key }));
      setEditing(null);
      toast({ title: "Key saved", variant: "success" });
    } catch {
      toast({ title: "Failed to save key", variant: "destructive" });
    }
  };

  const isActive = status?.mode === "active";

  return (
    <div className="space-y-4">
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm dark:text-gray-100 flex items-center gap-2">
                <Linkedin className="h-4 w-4 text-blue-600" />
                LinkedIn Automation Status
              </CardTitle>
              <CardDescription className="dark:text-gray-400 text-xs mt-1">
                {isActive
                  ? "Phantombuster is configured — LinkedIn actions will be automated."
                  : "No Phantombuster credentials — LinkedIn actions will be exported to CSV for manual execution."}
              </CardDescription>
            </div>
            <Badge
              className={
                isActive
                  ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                  : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
              }
            >
              {isActive ? (
                <><CheckCircle2 className="h-3 w-3 mr-1" /> Automation active</>
              ) : (
                <><AlertTriangle className="h-3 w-3 mr-1" /> Manual mode</>
              )}
            </Badge>
          </div>
        </CardHeader>
      </Card>

      <p className="text-sm text-gray-500 dark:text-gray-400">
        Configure Phantombuster credentials to enable automated LinkedIn outreach.
        Create phantoms at phantombuster.com and enter their IDs below.
      </p>

      {loading ? (
        <p className="text-sm text-gray-400 py-4 text-center">Loading...</p>
      ) : (
        linkedinKeys.map((entry) => {
          const maskedKey = serverKeys[entry.name] ?? "";
          const hasKey = !!maskedKey;
          const isEditing = editing === entry.name;

          return (
            <Card key={entry.name} className="dark:bg-gray-900 dark:border-gray-800">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-semibold dark:text-gray-100">{entry.label}</CardTitle>
                    <CardDescription className="text-xs dark:text-gray-400">{entry.description}</CardDescription>
                  </div>
                  <StatusBadge connected={hasKey} />
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {isEditing ? (
                  <div className="flex gap-2">
                    <Input
                      type="password"
                      placeholder={entry.placeholder}
                      value={draftKeys[entry.name] ?? ""}
                      onChange={(e) => setDraftKeys((p) => ({ ...p, [entry.name]: e.target.value }))}
                      className="font-mono text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                      autoFocus
                    />
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
                      {maskedKey}
                    </code>
                    <Button size="sm" variant="outline" onClick={() => { setDraftKeys((p) => ({ ...p, [entry.name]: "" })); setEditing(entry.name); }}
                      className="dark:border-gray-700 dark:text-gray-300">
                      <Key className="h-4 w-4 mr-1" /> Edit
                    </Button>
                  </div>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => { setDraftKeys((p) => ({ ...p, [entry.name]: "" })); setEditing(entry.name); }}
                    className="dark:border-gray-700 dark:text-gray-300">
                    <Plus className="h-4 w-4 mr-1" /> Add Key
                  </Button>
                )}
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
}

// ── Agent Status + Training Tab ───────────────────────────

interface AgentStatusEntry {
  agent_name: string;
  configured: boolean;
  has_db_key: boolean;
  has_env_key: boolean;
}

interface TrainingConfig {
  id: string;
  agent_name: string;
  config_type: string;
  config_key: string;
  config_value: string | string[] | Record<string, unknown>[] | Record<string, unknown>;
  is_active: boolean;
  priority: number;
  updated_at: string;
}

interface FewShotExample {
  input: string;
  output: string;
}

const AGENT_META: Record<string, { label: string; description: string; icon: React.ReactNode; capabilities: string[] }> = {
  groq: {
    label: "Groq (LLM)",
    description: "Primary AI engine — Llama 3.3 70B for chat, content generation, reply classification, compliance checks",
    icon: <Cpu className="h-5 w-5 text-purple-500" />,
    capabilities: ["Chat completions", "Sequence content generation", "Reply classification", "Compliance checking", "A/B variants", "Warmup emails", "Lead scoring narratives", "Analytics summaries"],
  },
  openai: {
    label: "OpenAI (LLM Fallback)",
    description: "Fallback AI + embeddings + content moderation — GPT-4o Mini",
    icon: <Zap className="h-5 w-5 text-green-500" />,
    capabilities: ["Chat completions (fallback)", "Text embeddings", "Content moderation", "Structured extraction", "Template analysis", "Improvement suggestions"],
  },
  hubspot: {
    label: "HubSpot CRM",
    description: "Full CRM operations — contacts, deals, companies, lists, activities, analytics",
    icon: <Building2 className="h-5 w-5 text-orange-500" />,
    capabilities: ["Contact CRUD + bulk", "Deal pipeline", "Company management", "Marketing emails", "Campaigns", "Forms", "Workflows", "Sequences", "Conversations", "Commerce", "Associations", "Imports/Exports", "Webhooks"],
  },
  zoominfo: {
    label: "ZoomInfo Intelligence",
    description: "Lead & company enrichment, intent signals, org charts, news, verification",
    icon: <Search className="h-5 w-5 text-blue-500" />,
    capabilities: ["Person enrichment", "Company enrichment", "People search", "Company search", "Intent signals", "Scoops & news", "Tech stack", "Email/phone verification", "Bulk enrichment"],
  },
  twilio: {
    label: "Twilio Communications",
    description: "SMS, MMS, WhatsApp, voice, OTP, phone lookup, A2P compliance",
    icon: <Phone className="h-5 w-5 text-red-500" />,
    capabilities: ["SMS send + bulk", "MMS", "WhatsApp", "Voice calls", "OTP verification", "Phone lookup", "Message scheduling", "Recordings & transcriptions", "A2P compliance", "Number management"],
  },
  apollo: {
    label: "Apollo.io Intelligence",
    description: "Sales intelligence — 210M+ contacts, enrichment, sequences, deals, tasks",
    icon: <Telescope className="h-5 w-5 text-indigo-500" />,
    capabilities: ["People search", "Company search", "Person enrichment", "Bulk enrichment", "Contact CRM", "Deal management", "Email sequences", "Task management", "Call logging", "Job postings"],
  },
  taplio: {
    label: "Taplio (LinkedIn)",
    description: "LinkedIn growth — AI posts, DMs, scheduling, lead database via Zapier",
    icon: <Linkedin className="h-5 w-5 text-sky-500" />,
    capabilities: ["AI post generation", "Post scheduling", "Carousel creation", "Hook generation", "Personalized DMs", "Bulk DMs", "Lead search", "Connection requests", "Post analytics"],
  },
};

// ── Agent Training Editor Sub-Component ──────────────────
function AgentTrainingEditor({ agentName, toast: toastFn }: { agentName: string; toast: (opts: { title: string; variant?: string }) => void }) {
  const [configs, setConfigs] = useState<TrainingConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  // Editable state
  const [systemPrompt, setSystemPrompt] = useState("");
  const [fewShot, setFewShot] = useState<FewShotExample[]>([]);
  const [guardrails, setGuardrails] = useState<string[]>([]);
  const [newGuardrail, setNewGuardrail] = useState("");
  const [newExampleInput, setNewExampleInput] = useState("");
  const [newExampleOutput, setNewExampleOutput] = useState("");

  useEffect(() => {
    if (!expanded) return;
    (async () => {
      try {
        const res = await fetch(`/api/v1/agents/training/${agentName}`);
        if (res.ok) {
          const data: TrainingConfig[] = await res.json();
          setConfigs(data);

          // Extract system prompt (default key)
          const sp = data.find((c) => c.config_type === "system_prompt" && c.config_key === "default");
          if (sp && typeof sp.config_value === "string") setSystemPrompt(sp.config_value);

          // Extract few-shot examples (default key)
          const fs = data.find((c) => c.config_type === "few_shot" && c.config_key === "default");
          if (fs && Array.isArray(fs.config_value)) {
            setFewShot(fs.config_value as FewShotExample[]);
          } else {
            // Try action-specific few-shot
            const fsAny = data.find((c) => c.config_type === "few_shot");
            if (fsAny && Array.isArray(fsAny.config_value)) {
              setFewShot(fsAny.config_value as FewShotExample[]);
            }
          }

          // Extract guardrails
          const gr = data.find((c) => c.config_type === "guardrails" && c.config_key === "default");
          if (gr && Array.isArray(gr.config_value)) setGuardrails(gr.config_value as string[]);
        }
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    })();
  }, [agentName, expanded]);

  const saveTraining = async () => {
    setSaving(true);
    try {
      const updates: { config_type: string; config_key: string; config_value: string | string[] | FewShotExample[]; is_active: boolean; priority: number }[] = [];

      if (systemPrompt.trim()) {
        updates.push({
          config_type: "system_prompt",
          config_key: "default",
          config_value: systemPrompt,
          is_active: true,
          priority: 0,
        });
      }

      if (fewShot.length > 0) {
        // Find what key the few-shot was stored under
        const existingFs = configs.find((c) => c.config_type === "few_shot");
        updates.push({
          config_type: "few_shot",
          config_key: existingFs?.config_key || "default",
          config_value: fewShot,
          is_active: true,
          priority: 0,
        });
      }

      if (guardrails.length > 0) {
        updates.push({
          config_type: "guardrails",
          config_key: "default",
          config_value: guardrails,
          is_active: true,
          priority: 0,
        });
      }

      const res = await fetch(`/api/v1/agents/training/${agentName}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ configs: updates }),
      });

      if (res.ok) {
        toastFn({ title: `${agentName} training saved`, variant: "success" });
      } else {
        toastFn({ title: "Failed to save training", variant: "destructive" });
      }
    } catch {
      toastFn({ title: "Failed to save training", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const addGuardrail = () => {
    if (!newGuardrail.trim()) return;
    setGuardrails((prev) => [...prev, newGuardrail.trim()]);
    setNewGuardrail("");
  };

  const removeGuardrail = (idx: number) => {
    setGuardrails((prev) => prev.filter((_, i) => i !== idx));
  };

  const addExample = () => {
    if (!newExampleInput.trim() || !newExampleOutput.trim()) return;
    setFewShot((prev) => [...prev, { input: newExampleInput.trim(), output: newExampleOutput.trim() }]);
    setNewExampleInput("");
    setNewExampleOutput("");
  };

  const removeExample = (idx: number) => {
    setFewShot((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="mt-3 border-t border-gray-200 dark:border-gray-700 pt-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
      >
        {expanded ? "Hide Training" : "Edit Training"}
      </button>

      {expanded && (
        <div className="mt-3 space-y-4">
          {loading ? (
            <p className="text-xs text-gray-400 py-2">Loading training config...</p>
          ) : (
            <>
              {/* System Prompt */}
              <div className="space-y-1">
                <Label className="text-xs dark:text-gray-300">System Prompt</Label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={4}
                  className="w-full text-xs font-mono rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 dark:text-gray-100 p-2 resize-y"
                  placeholder="Enter the system prompt for this agent..."
                />
              </div>

              {/* Few-Shot Examples */}
              <div className="space-y-2">
                <Label className="text-xs dark:text-gray-300">Few-Shot Examples ({fewShot.length})</Label>
                {fewShot.map((ex, idx) => (
                  <div key={idx} className="relative p-2 rounded border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                    <button
                      type="button"
                      onClick={() => removeExample(idx)}
                      className="absolute top-1 right-1 text-gray-400 hover:text-red-500"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                    <p className="text-xs dark:text-gray-300"><span className="font-semibold">Input:</span> {typeof ex.input === "string" ? ex.input.slice(0, 120) : "..."}{typeof ex.input === "string" && ex.input.length > 120 ? "..." : ""}</p>
                    <p className="text-xs dark:text-gray-400 mt-1"><span className="font-semibold">Output:</span> {typeof ex.output === "string" ? ex.output.slice(0, 120) : "..."}{typeof ex.output === "string" && ex.output.length > 120 ? "..." : ""}</p>
                  </div>
                ))}
                <div className="space-y-1">
                  <Input
                    placeholder="Example input..."
                    value={newExampleInput}
                    onChange={(e) => setNewExampleInput(e.target.value)}
                    className="text-xs dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                  />
                  <Input
                    placeholder="Expected output..."
                    value={newExampleOutput}
                    onChange={(e) => setNewExampleOutput(e.target.value)}
                    className="text-xs dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                  />
                  <Button size="sm" variant="outline" onClick={addExample}
                    disabled={!newExampleInput.trim() || !newExampleOutput.trim()}
                    className="dark:border-gray-700 dark:text-gray-300">
                    <Plus className="h-3 w-3 mr-1" /> Add Example
                  </Button>
                </div>
              </div>

              {/* Guardrails */}
              <div className="space-y-2">
                <Label className="text-xs dark:text-gray-300">Guardrails ({guardrails.length})</Label>
                {guardrails.map((g, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-xs">
                    <span className="flex-1 text-gray-700 dark:text-gray-300">- {g}</span>
                    <button type="button" onClick={() => removeGuardrail(idx)} className="text-gray-400 hover:text-red-500">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
                <div className="flex gap-2">
                  <Input
                    placeholder="New guardrail rule..."
                    value={newGuardrail}
                    onChange={(e) => setNewGuardrail(e.target.value)}
                    className="text-xs dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                    onKeyDown={(e) => { if (e.key === "Enter") addGuardrail(); }}
                  />
                  <Button size="sm" variant="outline" onClick={addGuardrail}
                    disabled={!newGuardrail.trim()}
                    className="dark:border-gray-700 dark:text-gray-300">
                    <Plus className="h-3 w-3 mr-1" /> Add
                  </Button>
                </div>
              </div>

              {/* Save button */}
              <Button size="sm" onClick={saveTraining} disabled={saving}>
                <Save className="h-4 w-4 mr-1" /> {saving ? "Saving..." : "Save Training"}
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function AgentStatusTab() {
  const { toast } = useToast();
  const [agents, setAgents] = useState<AgentStatusEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/v1/agents/status");
        if (res.ok) {
          const data = await res.json();
          setAgents(data.agents || data || []);
        }
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        FortressFlow agents are autonomous workers that operate within each platform.
        Configure API keys in the API Keys tab to activate each agent. Expand any agent to edit its training.
      </p>

      {loading ? (
        <p className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">Loading agent status...</p>
      ) : (
        Object.entries(AGENT_META).map(([name, meta]) => {
          const agent = agents.find((a) => a.agent_name === name);
          const isConfigured = agent?.configured ?? false;

          return (
            <Card key={name} className="dark:bg-gray-900 dark:border-gray-800">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                      {meta.icon}
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold dark:text-gray-100">
                        {meta.label}
                      </CardTitle>
                      <CardDescription className="text-xs dark:text-gray-400">
                        {meta.description}
                      </CardDescription>
                    </div>
                  </div>
                  <Badge
                    className={
                      isConfigured
                        ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                        : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                    }
                  >
                    {isConfigured ? (
                      <><CheckCircle2 className="h-3 w-3 mr-1" /> Active</>
                    ) : (
                      <><XCircle className="h-3 w-3 mr-1" /> Not configured</>
                    )}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {meta.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className={`text-xs px-2 py-0.5 rounded-full border ${
                        isConfigured
                          ? "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300"
                          : "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-400 dark:text-gray-500"
                      }`}
                    >
                      {cap}
                    </span>
                  ))}
                </div>
                {agent?.has_db_key && (
                  <p className="text-xs text-green-600 dark:text-green-400 mt-2">Using user-configured API key</p>
                )}
                {agent?.has_env_key && !agent?.has_db_key && (
                  <p className="text-xs text-blue-600 dark:text-blue-400 mt-2">Using system environment key</p>
                )}

                {/* Training Editor */}
                <AgentTrainingEditor agentName={name} toast={toast} />
              </CardContent>
            </Card>
          );
        })
      )}
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
          <TabsTrigger value="linkedin" className="dark:text-gray-400 dark:data-[state=active]:bg-gray-700 dark:data-[state=active]:text-gray-100">
            <Linkedin className="h-4 w-4 mr-1.5" /> LinkedIn
          </TabsTrigger>
          <TabsTrigger value="agents" className="dark:text-gray-400 dark:data-[state=active]:bg-gray-700 dark:data-[state=active]:text-gray-100">
            <Bot className="h-4 w-4 mr-1.5" /> AI Agents
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
          <TabsContent value="linkedin">
            <LinkedInTab />
          </TabsContent>
          <TabsContent value="agents">
            <AgentStatusTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
