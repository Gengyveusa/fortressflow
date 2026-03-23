"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { format } from "date-fns";
import {
  ArrowLeft,
  Building2,
  Mail,
  Phone,
  Briefcase,
  DollarSign,
  Plus,
  ChevronDown,
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
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/lib/hooks/use-toast";
import { leadsApi, dealsApi } from "@/lib/api";
import type { Lead, Deal } from "@/lib/api";

export default function LeadDetailPage() {
  const params = useParams();
  const leadId = params.id as string;
  const { toast } = useToast();

  const [lead, setLead] = useState<Lead | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [dealsLoading, setDealsLoading] = useState(true);
  const [showCreateDeal, setShowCreateDeal] = useState(false);
  const [newDeal, setNewDeal] = useState({ deal_name: "", pipeline: "default", stage: "appointmentscheduled", amount: "" });

  const fetchLead = useCallback(async () => {
    try {
      const res = await leadsApi.get(leadId);
      setLead(res.data);
    } catch {
      toast({ title: "Failed to load lead", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [leadId, toast]);

  const fetchDeals = useCallback(async () => {
    try {
      const res = await dealsApi.listForLead(leadId);
      setDeals(res.data);
    } catch {
      // HubSpot may not be configured — silent fail
    } finally {
      setDealsLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    fetchLead();
    fetchDeals();
  }, [fetchLead, fetchDeals]);

  const createDeal = async () => {
    if (!newDeal.deal_name.trim()) return;
    try {
      const res = await dealsApi.create(leadId, {
        deal_name: newDeal.deal_name,
        pipeline: newDeal.pipeline,
        stage: newDeal.stage,
        amount: newDeal.amount ? parseFloat(newDeal.amount) : undefined,
      });
      setDeals((prev) => [...prev, res.data]);
      setShowCreateDeal(false);
      setNewDeal({ deal_name: "", pipeline: "default", stage: "appointmentscheduled", amount: "" });
      toast({ title: "Deal created", variant: "success" });
    } catch {
      toast({ title: "Failed to create deal", variant: "destructive" });
    }
  };

  const updateStage = async (dealId: string, stage: string) => {
    try {
      const res = await dealsApi.updateStage(dealId, stage);
      setDeals((prev) => prev.map((d) => (d.deal_id === dealId ? res.data : d)));
      toast({ title: "Deal stage updated", variant: "success" });
    } catch {
      toast({ title: "Failed to update stage", variant: "destructive" });
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl space-y-4">
        <div className="h-8 w-48 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
        <div className="h-64 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="max-w-4xl text-center py-12">
        <p className="text-gray-500">Lead not found.</p>
        <Button variant="outline" className="mt-4" asChild>
          <Link href="/leads">Back to Leads</Link>
        </Button>
      </div>
    );
  }

  const stages = [
    { value: "appointmentscheduled", label: "Appointment Scheduled" },
    { value: "qualifiedtobuy", label: "Qualified to Buy" },
    { value: "presentationscheduled", label: "Presentation Scheduled" },
    { value: "decisionmakerboughtin", label: "Decision Maker Bought-In" },
    { value: "contractsent", label: "Contract Sent" },
    { value: "closedwon", label: "Closed Won" },
    { value: "closedlost", label: "Closed Lost" },
  ];

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/leads"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <div>
          <h1 className="text-xl font-semibold dark:text-gray-100">
            {lead.first_name} {lead.last_name}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{lead.title} at {lead.company}</p>
        </div>
        <Badge variant={lead.meeting_verified ? "default" : "secondary"} className="ml-auto">
          {lead.meeting_verified ? "Verified" : "Pending"}
        </Badge>
      </div>

      <Separator className="dark:border-gray-800" />

      {/* Lead Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm dark:text-gray-100">Contact Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Mail className="h-4 w-4 text-gray-400" />
              <span className="dark:text-gray-300">{lead.email}</span>
            </div>
            {lead.phone && (
              <div className="flex items-center gap-2 text-sm">
                <Phone className="h-4 w-4 text-gray-400" />
                <span className="dark:text-gray-300">{lead.phone}</span>
              </div>
            )}
            <div className="flex items-center gap-2 text-sm">
              <Building2 className="h-4 w-4 text-gray-400" />
              <span className="dark:text-gray-300">{lead.company}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Briefcase className="h-4 w-4 text-gray-400" />
              <span className="dark:text-gray-300">{lead.title}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm dark:text-gray-100">Metadata</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500 dark:text-gray-400">Source</span>
              <span className="dark:text-gray-300">{lead.source}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500 dark:text-gray-400">Created</span>
              <span className="dark:text-gray-300">{format(new Date(lead.created_at), "MMM d, yyyy")}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500 dark:text-gray-400">Updated</span>
              <span className="dark:text-gray-300">{format(new Date(lead.updated_at), "MMM d, yyyy")}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Deals Section */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm dark:text-gray-100 flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-green-600" />
                HubSpot Deals
              </CardTitle>
              <CardDescription className="dark:text-gray-400 text-xs mt-1">
                Deals associated with this lead in HubSpot CRM.
              </CardDescription>
            </div>
            <Button size="sm" variant="outline" onClick={() => setShowCreateDeal(!showCreateDeal)}
              className="dark:border-gray-700 dark:text-gray-300">
              <Plus className="h-4 w-4 mr-1" /> New Deal
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Create Deal Form */}
          {showCreateDeal && (
            <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs dark:text-gray-300">Deal Name</Label>
                  <Input
                    placeholder="e.g. Gengyve Enterprise"
                    value={newDeal.deal_name}
                    onChange={(e) => setNewDeal((p) => ({ ...p, deal_name: e.target.value }))}
                    className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs dark:text-gray-300">Amount ($)</Label>
                  <Input
                    type="number"
                    placeholder="0.00"
                    value={newDeal.amount}
                    onChange={(e) => setNewDeal((p) => ({ ...p, amount: e.target.value }))}
                    className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs dark:text-gray-300">Stage</Label>
                <select
                  value={newDeal.stage}
                  onChange={(e) => setNewDeal((p) => ({ ...p, stage: e.target.value }))}
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm dark:text-gray-100"
                >
                  {stages.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={createDeal} disabled={!newDeal.deal_name.trim()}>
                  Create Deal
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowCreateDeal(false)}
                  className="dark:border-gray-700 dark:text-gray-300">
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Deals List */}
          {dealsLoading ? (
            <p className="text-sm text-gray-400 text-center py-4">Loading deals...</p>
          ) : deals.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">
              No deals found. Create one to start tracking pipeline progress.
            </p>
          ) : (
            <div className="space-y-3">
              {deals.map((deal) => (
                <div
                  key={deal.deal_id}
                  className="flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800"
                >
                  <div>
                    <p className="text-sm font-medium dark:text-gray-200">{deal.deal_name}</p>
                    <div className="flex items-center gap-3 mt-1">
                      {deal.amount != null && (
                        <span className="text-xs text-green-600 dark:text-green-400 font-semibold">
                          ${deal.amount.toLocaleString()}
                        </span>
                      )}
                      <span className="text-xs text-gray-400">{deal.pipeline}</span>
                      {deal.created_at && (
                        <span className="text-xs text-gray-400">
                          {format(new Date(deal.created_at), "MMM d, yyyy")}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={deal.stage}
                      onChange={(e) => updateStage(deal.deal_id, e.target.value)}
                      className="text-xs rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 dark:text-gray-300"
                    >
                      {stages.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
