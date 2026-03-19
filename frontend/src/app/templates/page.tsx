"use client";

import { useState } from "react";
import { Mail, MessageSquare, Linkedin, Plus, Eye, ChevronLeft, ChevronRight, Search } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { useTemplates } from "@/lib/hooks";
import { templatesApi } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

const CHANNEL_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  sms: MessageSquare,
  linkedin: Linkedin,
};

const CHANNEL_COLORS: Record<string, string> = {
  email: "bg-blue-50 text-blue-700 border-blue-200",
  sms: "bg-green-50 text-green-700 border-green-200",
  linkedin: "bg-sky-50 text-sky-700 border-sky-200",
};

const CATEGORY_LABELS: Record<string, string> = {
  cold_outreach: "Cold Outreach",
  follow_up: "Follow-up",
  re_engagement: "Re-engagement",
  custom: "Custom",
};

function TemplateSkeleton() {
  return (
    <Card className="animate-pulse">
      <CardHeader>
        <div className="h-5 w-32 bg-gray-200 rounded" />
        <div className="h-3 w-48 bg-gray-100 rounded mt-2" />
      </CardHeader>
      <CardContent>
        <div className="h-16 bg-gray-100 rounded" />
      </CardContent>
    </Card>
  );
}

export default function TemplatesPage() {
  const [page, setPage] = useState(1);
  const [channelFilter, setChannelFilter] = useState<string | undefined>(undefined);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const pageSize = 12;
  const { data, isLoading, error } = useTemplates(page, pageSize, channelFilter, categoryFilter);
  const queryClient = useQueryClient();

  // Create dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTemplate, setNewTemplate] = useState({
    name: "",
    channel: "email",
    category: "custom",
    subject: "",
    plain_body: "",
    html_body: "",
    linkedin_action: "connection_request",
  });

  // Preview dialog state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<{
    subject: string | null;
    plain_body: string;
    html_body: string | null;
  } | null>(null);

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  const handleCreate = async () => {
    if (!newTemplate.name.trim() || !newTemplate.plain_body.trim()) return;
    setCreating(true);
    try {
      await templatesApi.create({
        name: newTemplate.name.trim(),
        channel: newTemplate.channel,
        category: newTemplate.category,
        subject: newTemplate.channel === "email" ? newTemplate.subject : undefined,
        plain_body: newTemplate.plain_body,
        html_body: newTemplate.channel === "email" && newTemplate.html_body ? newTemplate.html_body : undefined,
        linkedin_action: newTemplate.channel === "linkedin" ? newTemplate.linkedin_action : undefined,
      } as Record<string, unknown>);
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setNewTemplate({ name: "", channel: "email", category: "custom", subject: "", plain_body: "", html_body: "", linkedin_action: "connection_request" });
      setDialogOpen(false);
    } catch {
      // keep dialog open on error
    } finally {
      setCreating(false);
    }
  };

  const handlePreview = async (templateId: string) => {
    try {
      const result = await templatesApi.preview({ template_id: templateId });
      setPreviewData({
        subject: result.data.rendered_subject,
        plain_body: result.data.rendered_plain_body,
        html_body: result.data.rendered_html_body,
      });
      setPreviewOpen(true);
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold">Templates</h1>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-1" /> New Template
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create Template</DialogTitle>
              <DialogDescription>
                Build a reusable message template. Use {"{{variable}}"} syntax for dynamic content.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2 max-h-[60vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    placeholder="e.g. Cold Intro Email"
                    value={newTemplate.name}
                    onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Channel</Label>
                  <Select value={newTemplate.channel} onValueChange={(v) => setNewTemplate({ ...newTemplate, channel: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="email">Email</SelectItem>
                      <SelectItem value="sms">SMS</SelectItem>
                      <SelectItem value="linkedin">LinkedIn</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <Select value={newTemplate.category} onValueChange={(v) => setNewTemplate({ ...newTemplate, category: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cold_outreach">Cold Outreach</SelectItem>
                    <SelectItem value="follow_up">Follow-up</SelectItem>
                    <SelectItem value="re_engagement">Re-engagement</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {newTemplate.channel === "email" && (
                <div className="space-y-2">
                  <Label>Subject Line</Label>
                  <Input
                    placeholder="e.g. {{first_name}}, quick question about your patients' mouthwash"
                    value={newTemplate.subject}
                    onChange={(e) => setNewTemplate({ ...newTemplate, subject: e.target.value })}
                  />
                </div>
              )}
              {newTemplate.channel === "linkedin" && (
                <div className="space-y-2">
                  <Label>LinkedIn Action</Label>
                  <Select value={newTemplate.linkedin_action} onValueChange={(v) => setNewTemplate({ ...newTemplate, linkedin_action: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="connection_request">Connection Request</SelectItem>
                      <SelectItem value="inmail">InMail</SelectItem>
                      <SelectItem value="message">Direct Message</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="space-y-2">
                <Label>Message Body</Label>
                <Textarea
                  placeholder={`Hi {{first_name}},\n\nI wanted to reach out because...`}
                  value={newTemplate.plain_body}
                  onChange={(e) => setNewTemplate({ ...newTemplate, plain_body: e.target.value })}
                  rows={8}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-gray-400">
                  Available variables: {"{{first_name}}"}, {"{{last_name}}"}, {"{{company}}"}, {"{{title}}"}, {"{{sender_name}}"}, {"{{sender_company}}"}
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button
                onClick={handleCreate}
                disabled={!newTemplate.name.trim() || !newTemplate.plain_body.trim() || creating}
              >
                {creating ? "Creating\u2026" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={channelFilter ?? "all"} onValueChange={(v) => { setChannelFilter(v === "all" ? undefined : v); setPage(1); }}>
          <SelectTrigger className="w-[140px]"><SelectValue placeholder="All Channels" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Channels</SelectItem>
            <SelectItem value="email">Email</SelectItem>
            <SelectItem value="sms">SMS</SelectItem>
            <SelectItem value="linkedin">LinkedIn</SelectItem>
          </SelectContent>
        </Select>
        <Select value={categoryFilter ?? "all"} onValueChange={(v) => { setCategoryFilter(v === "all" ? undefined : v); setPage(1); }}>
          <SelectTrigger className="w-[160px]"><SelectValue placeholder="All Categories" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="cold_outreach">Cold Outreach</SelectItem>
            <SelectItem value="follow_up">Follow-up</SelectItem>
            <SelectItem value="re_engagement">Re-engagement</SelectItem>
            <SelectItem value="custom">Custom</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Template Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <TemplateSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-10 text-center text-red-500 text-sm">
            Failed to load templates. Please try again.
          </CardContent>
        </Card>
      ) : !data?.items.length ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Mail className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No templates yet</p>
            <p className="text-sm text-gray-400 mt-1">
              Create your first template or deploy a Gengyve preset sequence.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.items.map((template) => {
              const ChannelIcon = CHANNEL_ICONS[template.channel] ?? Mail;
              return (
                <Card key={template.id} className="h-full">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base leading-tight">{template.name}</CardTitle>
                      <Badge className={`shrink-0 ${CHANNEL_COLORS[template.channel] ?? ""}`}>
                        <ChannelIcon className="h-3 w-3 mr-1" />
                        {template.channel}
                      </Badge>
                    </div>
                    {template.subject && (
                      <CardDescription className="line-clamp-1 font-mono text-xs">
                        Subject: {template.subject}
                      </CardDescription>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-sm text-gray-600 line-clamp-3 whitespace-pre-wrap">
                      {template.plain_body}
                    </p>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {CATEGORY_LABELS[template.category] ?? template.category}
                        </Badge>
                        {template.is_system && (
                          <Badge variant="outline" className="text-xs bg-purple-50 text-purple-600 border-purple-200">
                            System
                          </Badge>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handlePreview(template.id)}
                      >
                        <Eye className="h-4 w-4 mr-1" /> Preview
                      </Button>
                    </div>
                    {template.variables && template.variables.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {template.variables.map((v) => (
                          <span
                            key={v}
                            className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded font-mono"
                          >
                            {`{{${v}}}`}
                          </span>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Page {page} of {totalPages} ({data.total} templates)
              </p>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Template Preview</DialogTitle>
            <DialogDescription>
              Preview with sample data (Sarah Chen, SmileCare Dental Group)
            </DialogDescription>
          </DialogHeader>
          {previewData && (
            <Tabs defaultValue={previewData.html_body ? "html" : "plain"}>
              <TabsList>
                {previewData.html_body && <TabsTrigger value="html">HTML</TabsTrigger>}
                <TabsTrigger value="plain">Plain Text</TabsTrigger>
              </TabsList>
              {previewData.html_body && (
                <TabsContent value="html">
                  {previewData.subject && (
                    <p className="text-sm font-medium mb-2 text-gray-600">
                      Subject: {previewData.subject}
                    </p>
                  )}
                  <div
                    className="border rounded-lg p-4 bg-white text-sm"
                    dangerouslySetInnerHTML={{ __html: previewData.html_body }}
                  />
                </TabsContent>
              )}
              <TabsContent value="plain">
                {previewData.subject && (
                  <p className="text-sm font-medium mb-2 text-gray-600">
                    Subject: {previewData.subject}
                  </p>
                )}
                <pre className="border rounded-lg p-4 bg-gray-50 text-sm whitespace-pre-wrap font-mono">
                  {previewData.plain_body}
                </pre>
              </TabsContent>
            </Tabs>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
