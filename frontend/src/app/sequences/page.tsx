"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  Plus,
  GitBranch,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Pencil,
  MoreVertical,
  Copy,
  Pause,
  Play,
  Archive,
  Trash2,
  ArrowUpDown,
} from "lucide-react";
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
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSequences, useSequencePerformance } from "@/lib/hooks";
import { sequencesApi, type Sequence } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/lib/hooks/use-toast";

// ── Types ─────────────────────────────────────────────────
type StatusFilter = "all" | "active" | "draft" | "paused" | "archived";
type SortKey = "name" | "created" | "enrolled";

// ── Helpers ───────────────────────────────────────────────
const STATUS_BADGE: Record<string, string> = {
  draft:    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  active:   "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  paused:   "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  archived: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

interface SequencePerf {
  open_rate: number;
  reply_rate: number;
  bounce_rate: number;
}

// ── Skeleton ──────────────────────────────────────────────
function SequenceSkeleton() {
  return (
    <Card className="animate-pulse dark:bg-gray-900 dark:border-gray-800">
      <CardHeader>
        <div className="h-5 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
        <div className="h-3 w-48 bg-gray-100 dark:bg-gray-800 rounded mt-2" />
      </CardHeader>
      <CardContent>
        <div className="h-4 w-20 bg-gray-100 dark:bg-gray-800 rounded" />
      </CardContent>
    </Card>
  );
}

// ── Sequence Card ─────────────────────────────────────────
interface SequenceCardProps {
  seq: Sequence;
  perf: SequencePerf;
  onAction: (action: string, seq: Sequence) => void;
}

function SequenceCard({ seq, perf, onAction }: SequenceCardProps) {

  return (
    <Card className="hover:shadow-md transition-shadow h-full relative group dark:bg-gray-900 dark:border-gray-800 dark:hover:border-gray-700">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <Link href={`/sequences/${seq.id}`} className="flex-1 min-w-0">
            <CardTitle className="text-base truncate dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
              {seq.name}
            </CardTitle>
          </Link>
          <div className="flex items-center gap-1 flex-shrink-0">
            <Badge className={STATUS_BADGE[seq.status] ?? "bg-gray-100"}>
              {seq.status}
            </Badge>
            {/* Action dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 dark:text-gray-500 transition-opacity"
                  aria-label="Sequence actions"
                >
                  <MoreVertical className="h-4 w-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44 dark:bg-gray-900 dark:border-gray-700">
                <DropdownMenuItem
                  className="dark:text-gray-300 dark:focus:bg-gray-800"
                  onClick={() => onAction("edit", seq)}
                >
                  <Pencil className="h-4 w-4 mr-2" /> Edit in Builder
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="dark:text-gray-300 dark:focus:bg-gray-800"
                  onClick={() => onAction("duplicate", seq)}
                >
                  <Copy className="h-4 w-4 mr-2" /> Duplicate
                </DropdownMenuItem>
                <DropdownMenuSeparator className="dark:border-gray-700" />
                {seq.status === "paused" ? (
                  <DropdownMenuItem
                    className="dark:text-gray-300 dark:focus:bg-gray-800"
                    onClick={() => onAction("resume", seq)}
                  >
                    <Play className="h-4 w-4 mr-2" /> Resume
                  </DropdownMenuItem>
                ) : seq.status === "active" ? (
                  <DropdownMenuItem
                    className="dark:text-gray-300 dark:focus:bg-gray-800"
                    onClick={() => onAction("pause", seq)}
                  >
                    <Pause className="h-4 w-4 mr-2" /> Pause
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuItem
                  className="dark:text-gray-300 dark:focus:bg-gray-800"
                  onClick={() => onAction("archive", seq)}
                >
                  <Archive className="h-4 w-4 mr-2" /> Archive
                </DropdownMenuItem>
                <DropdownMenuSeparator className="dark:border-gray-700" />
                <DropdownMenuItem
                  className="text-red-600 dark:text-red-400 dark:focus:bg-gray-800"
                  onClick={() => onAction("delete", seq)}
                >
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        {seq.description && (
          <CardDescription className="line-clamp-2 dark:text-gray-400">
            {seq.description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Steps + enrolled */}
        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
          <span>{seq.steps?.length ?? 0} steps</span>
          <span>{seq.enrolled_count} enrolled</span>
          {seq.ai_generated && (
            <span className="flex items-center gap-1 text-purple-500 dark:text-purple-400">
              <Sparkles className="h-3 w-3" /> AI
            </span>
          )}
        </div>

        {/* Performance mini-bars */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400 dark:text-gray-500">Open</span>
            <span className="text-gray-600 dark:text-gray-300 font-medium tabular-nums">
              {(perf.open_rate * 100).toFixed(0)}%
            </span>
          </div>
          <Progress value={perf.open_rate * 100} className="h-1.5" />

          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400 dark:text-gray-500">Reply</span>
            <span className="text-gray-600 dark:text-gray-300 font-medium tabular-nums">
              {(perf.reply_rate * 100).toFixed(0)}%
            </span>
          </div>
          <Progress value={perf.reply_rate * 100} className="h-1.5" />

          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400 dark:text-gray-500">Bounce</span>
            <span className="text-gray-600 dark:text-gray-300 font-medium tabular-nums">
              {(perf.bounce_rate * 100).toFixed(1)}%
            </span>
          </div>
          <Progress value={perf.bounce_rate * 100} className="h-1.5" />
        </div>

        {/* Builder CTA */}
        <Link
          href={`/sequences/builder/${seq.id}`}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex"
        >
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800">
            <Pencil className="h-3.5 w-3.5 mr-1" /> Edit Builder
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────
export default function SequencesPage() {
  const [page, setPage] = useState(1);
  const pageSize = 12;
  const { data, isLoading, error } = useSequences(page, pageSize);
  const { data: perfData } = useSequencePerformance();
  const queryClient = useQueryClient();

  const perfMap = useMemo(() => {
    const map: Record<string, SequencePerf> = {};
    const entries = Array.isArray(perfData) ? perfData : [];
    for (const entry of entries) {
      map[entry.sequence_id] = {
        open_rate: (entry.open_rate ?? 0) / 100,
        reply_rate: (entry.reply_rate ?? 0) / 100,
        bounce_rate: (entry.bounce_rate ?? 0) / 100,
      };
    }
    return map;
  }, [perfData]);

  const NO_PERF: SequencePerf = { open_rate: 0, reply_rate: 0, bounce_rate: 0 };
  const { toast } = useToast();

  // Dialog
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("created");

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  // Client-side filter + sort
  const filteredItems = useMemo(() => {
    let items = data?.items ?? [];
    if (statusFilter !== "all") {
      items = items.filter((s) => s.status === statusFilter);
    }
    return [...items].sort((a, b) => {
      if (sortKey === "name") return a.name.localeCompare(b.name);
      if (sortKey === "enrolled") return b.enrolled_count - a.enrolled_count;
      // default: created (newest first)
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [data?.items, statusFilter, sortKey]);

  // Create handler
  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await sequencesApi.create({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["sequences"] });
      setNewName("");
      setNewDesc("");
      setDialogOpen(false);
      toast({ title: "Sequence created", variant: "success" });
    } catch {
      toast({ title: "Failed to create sequence", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  // Action handler
  const handleAction = async (action: string, seq: Sequence) => {
    try {
      if (action === "edit") {
        window.location.href = `/sequences/builder/${seq.id}`;
        return;
      }
      if (action === "delete") {
        await sequencesApi.delete(seq.id);
        queryClient.invalidateQueries({ queryKey: ["sequences"] });
        toast({ title: `"${seq.name}" deleted`, variant: "default" });
        return;
      }
      if (action === "pause") {
        await sequencesApi.update(seq.id, { status: "paused" });
        queryClient.invalidateQueries({ queryKey: ["sequences"] });
        toast({ title: `"${seq.name}" paused` });
        return;
      }
      if (action === "resume") {
        await sequencesApi.update(seq.id, { status: "active" });
        queryClient.invalidateQueries({ queryKey: ["sequences"] });
        toast({ title: `"${seq.name}" resumed`, variant: "success" });
        return;
      }
      if (action === "archive") {
        await sequencesApi.update(seq.id, { status: "archived" });
        queryClient.invalidateQueries({ queryKey: ["sequences"] });
        toast({ title: `"${seq.name}" archived` });
        return;
      }
      if (action === "duplicate") {
        await sequencesApi.create({
          name: `${seq.name} (copy)`,
          description: seq.description ?? undefined,
        });
        queryClient.invalidateQueries({ queryKey: ["sequences"] });
        toast({ title: `"${seq.name}" duplicated`, variant: "success" });
      }
    } catch {
      toast({ title: "Action failed", variant: "destructive" });
    }
  };

  const statusCounts = useMemo(() => {
    const items = data?.items ?? [];
    return {
      all:      items.length,
      active:   items.filter((s) => s.status === "active").length,
      draft:    items.filter((s) => s.status === "draft").length,
      paused:   items.filter((s) => s.status === "paused").length,
      archived: items.filter((s) => s.status === "archived").length,
    };
  }, [data?.items]);

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold dark:text-gray-100">Sequences</h1>
        <div className="flex items-center gap-2">
          {/* Sort */}
          <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
            <SelectTrigger className="h-9 w-40 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-300">
              <ArrowUpDown className="h-3.5 w-3.5 mr-1 text-gray-400" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="dark:bg-gray-900 dark:border-gray-700">
              <SelectItem value="created" className="dark:text-gray-300 dark:focus:bg-gray-800">Created (newest)</SelectItem>
              <SelectItem value="name" className="dark:text-gray-300 dark:focus:bg-gray-800">Name (A–Z)</SelectItem>
              <SelectItem value="enrolled" className="dark:text-gray-300 dark:focus:bg-gray-800">Most enrolled</SelectItem>
            </SelectContent>
          </Select>

          {/* Create dialog */}
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-1" /> New Sequence
              </Button>
            </DialogTrigger>
            <DialogContent className="dark:bg-gray-900 dark:border-gray-700">
              <DialogHeader>
                <DialogTitle className="dark:text-gray-100">Create Sequence</DialogTitle>
                <DialogDescription className="dark:text-gray-400">
                  Set up a new outreach sequence. You can add steps after creating it.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="space-y-2">
                  <Label htmlFor="seq-name" className="dark:text-gray-300">Name</Label>
                  <Input
                    id="seq-name"
                    placeholder="e.g. Q4 Enterprise Outreach"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="seq-desc" className="dark:text-gray-300">Description (optional)</Label>
                  <Textarea
                    id="seq-desc"
                    placeholder="Describe the goal of this sequence…"
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    rows={3}
                    className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)} className="dark:border-gray-700 dark:text-gray-300">
                  Cancel
                </Button>
                <Button onClick={handleCreate} disabled={!newName.trim() || creating}>
                  {creating ? "Creating…" : "Create"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* ── Status Filter Tabs ── */}
      <Tabs value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
        <TabsList className="dark:bg-gray-800">
          {(["all", "active", "draft", "paused", "archived"] as const).map((s) => (
            <TabsTrigger key={s} value={s} className="capitalize dark:data-[state=active]:bg-gray-700 dark:text-gray-400 dark:data-[state=active]:text-gray-100">
              {s}
              {!isLoading && (
                <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
                  {statusCounts[s]}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* ── Content ── */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SequenceSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-10 text-center text-red-500 text-sm">
            Failed to load sequences. Please try again.
          </CardContent>
        </Card>
      ) : !filteredItems.length ? (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-16 text-center">
            <GitBranch className="h-10 w-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400 font-medium">
              {statusFilter === "all" ? "No sequences yet" : `No ${statusFilter} sequences`}
            </p>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
              {statusFilter === "all"
                ? "Create your first outreach sequence to get started."
                : `No sequences with "${statusFilter}" status found.`}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredItems.map((seq) => (
              <SequenceCard key={seq.id} seq={seq} perf={perfMap[seq.id] ?? NO_PERF} onAction={handleAction} />
            ))}
          </div>

          {totalPages > 1 && statusFilter === "all" && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Page {page} of {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
