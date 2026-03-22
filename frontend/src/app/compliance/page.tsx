"use client";

import { useState, useEffect, useCallback } from "react";
import { ShieldCheck, Search, Plus, AlertTriangle, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { complianceApi, type ComplianceCheck, type DNCEntry, type AuditTrailEntry } from "@/lib/api";

const CHANNELS = ["email", "linkedin", "sms", "phone"] as const;

export default function CompliancePage() {
  /* ── compliance check tool state ───────────────────── */
  const [checkLeadId, setCheckLeadId] = useState("");
  const [checkChannel, setCheckChannel] = useState("email");
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<ComplianceCheck | null>(null);
  const [checkError, setCheckError] = useState("");

  /* ── DNC state ─────────────────────────────────────── */
  const [dncSearch, setDncSearch] = useState("");
  const [dncEmail, setDncEmail] = useState("");
  const [dncList, setDncList] = useState<DNCEntry[]>([]);
  const [dncLoading, setDncLoading] = useState(false);

  /* ── Audit trail state ─────────────────────────────── */
  const [auditTrail, setAuditTrail] = useState<AuditTrailEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  /* ── Fetch DNC list from backend ───────────────────── */
  const fetchDnc = useCallback(async (search = "") => {
    setDncLoading(true);
    try {
      const res = await complianceApi.listDnc(1, 200, search);
      setDncList(res.data.items);
    } catch {
      // Silently handle — show empty list
    } finally {
      setDncLoading(false);
    }
  }, []);

  /* ── Fetch audit trail from backend ────────────────── */
  const fetchAuditTrail = useCallback(async () => {
    setAuditLoading(true);
    try {
      const res = await fetch("/api/v1/analytics/audit-trail");
      if (res.ok) {
        const data = await res.json();
        setAuditTrail(data.items || []);
      }
    } catch {
      // Silently handle
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDnc();
    fetchAuditTrail();
  }, [fetchDnc, fetchAuditTrail]);

  const handleCheck = async () => {
    if (!checkLeadId.trim()) return;
    setChecking(true);
    setCheckResult(null);
    setCheckError("");
    try {
      const res = await complianceApi.check(checkLeadId.trim(), checkChannel);
      setCheckResult(res.data);
    } catch {
      setCheckError("Failed to check compliance. Verify the lead ID exists.");
    } finally {
      setChecking(false);
    }
  };

  const addDnc = async () => {
    if (!dncEmail.trim()) return;
    try {
      await complianceApi.addDnc(dncEmail.trim(), "email", "Manual DNC addition", "manual");
      setDncEmail("");
      fetchDnc(dncSearch);
    } catch {
      // Silently handle
    }
  };

  const removeDnc = async (id: string) => {
    try {
      await complianceApi.removeDnc(id);
      fetchDnc(dncSearch);
    } catch {
      // Silently handle
    }
  };

  const handleDncSearch = (value: string) => {
    setDncSearch(value);
    fetchDnc(value);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Compliance</h1>

      <Tabs defaultValue="audit">
        <TabsList>
          <TabsTrigger value="audit">Audit Log</TabsTrigger>
          <TabsTrigger value="dnc">DNC Management</TabsTrigger>
          <TabsTrigger value="health">Compliance Health</TabsTrigger>
        </TabsList>

        {/* ── Audit Log Tab ──────────────────────────── */}
        <TabsContent value="audit" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Consent Audit Trail</CardTitle>
              <CardDescription>Record of all consent-related activity.</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {auditLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Who</TableHead>
                      <TableHead>When</TableHead>
                      <TableHead>Channel</TableHead>
                      <TableHead>Method</TableHead>
                      <TableHead>Proof / Source</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {auditTrail.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-gray-400 py-8">
                          No audit trail entries found.
                        </TableCell>
                      </TableRow>
                    ) : (
                      auditTrail.map((row) => (
                        <TableRow key={row.id}>
                          <TableCell className="font-medium">{row.who}</TableCell>
                          <TableCell className="text-gray-500 text-xs">{row.when}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{row.channel}</Badge>
                          </TableCell>
                          <TableCell>{row.method}</TableCell>
                          <TableCell className="text-gray-500 text-sm">{row.proof}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── DNC Management Tab ─────────────────────── */}
        <TabsContent value="dnc" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Do-Not-Contact List</CardTitle>
              <CardDescription>Manage contacts that should never be contacted.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Add email to DNC list…"
                  value={dncEmail}
                  onChange={(e) => setDncEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addDnc()}
                />
                <Button onClick={addDnc} disabled={!dncEmail.trim()}>
                  <Plus className="h-4 w-4 mr-1" /> Add
                </Button>
              </div>

              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search DNC list…"
                  value={dncSearch}
                  onChange={(e) => handleDncSearch(e.target.value)}
                  className="max-w-xs h-9"
                />
              </div>

              {dncLoading ? (
                <div className="flex justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                </div>
              ) : dncList.length === 0 ? (
                <p className="text-sm text-gray-400 py-4 text-center">
                  No entries in the DNC list.
                </p>
              ) : (
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {dncList.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded text-sm"
                    >
                      <div>
                        <span className="font-medium">{entry.identifier}</span>
                        <span className="text-gray-400 ml-2 text-xs">
                          {entry.channel} · {entry.source}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-500 h-7"
                        onClick={() => removeDnc(entry.id)}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Compliance Health Tab ──────────────────── */}
        <TabsContent value="health" className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {CHANNELS.map((ch) => (
              <Card key={ch}>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-green-50">
                      <ShieldCheck className="h-5 w-5 text-green-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium capitalize">{ch}</p>
                      <Badge className="bg-green-100 text-green-700 mt-1">Active</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Compliance check tool */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Compliance Check Tool</CardTitle>
              <CardDescription>
                Verify whether a lead can be contacted on a specific channel.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-2">
                  <Label>Lead ID</Label>
                  <Input
                    placeholder="Enter lead ID…"
                    value={checkLeadId}
                    onChange={(e) => setCheckLeadId(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Channel</Label>
                  <Select value={checkChannel} onValueChange={setCheckChannel}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CHANNELS.map((ch) => (
                        <SelectItem key={ch} value={ch}>
                          {ch}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button
                    onClick={handleCheck}
                    disabled={checking || !checkLeadId.trim()}
                    className="w-full"
                  >
                    {checking ? "Checking…" : "Check Compliance"}
                  </Button>
                </div>
              </div>

              {checkError && (
                <div className="flex items-center gap-2 text-red-500 text-sm">
                  <AlertTriangle className="h-4 w-4" />
                  {checkError}
                </div>
              )}

              {checkResult && (
                <div
                  className={`flex items-center gap-3 p-4 rounded-lg ${
                    checkResult.can_send
                      ? "bg-green-50 border border-green-200"
                      : "bg-red-50 border border-red-200"
                  }`}
                >
                  {checkResult.can_send ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  <div>
                    <p className="font-medium text-sm">
                      {checkResult.can_send ? "Allowed to send" : "Cannot send"}
                    </p>
                    <p className="text-xs text-gray-600">{checkResult.reason}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
