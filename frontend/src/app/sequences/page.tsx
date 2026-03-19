"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, GitBranch, ChevronLeft, ChevronRight, Sparkles, Pencil } from "lucide-react";
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
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useSequences } from "@/lib/hooks";
import { sequencesApi } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  active: "bg-green-100 text-green-700",
  paused: "bg-yellow-100 text-yellow-700",
  archived: "bg-red-100 text-red-700",
};

function SequenceSkeleton() {
  return (
    <Card className="animate-pulse">
      <CardHeader>
        <div className="h-5 w-32 bg-gray-200 rounded" />
        <div className="h-3 w-48 bg-gray-100 rounded mt-2" />
      </CardHeader>
      <CardContent>
        <div className="h-4 w-20 bg-gray-100 rounded" />
      </CardContent>
    </Card>
  );
}

export default function SequencesPage() {
  const [page, setPage] = useState(1);
  const pageSize = 12;
  const { data, isLoading, error } = useSequences(page, pageSize);
  const queryClient = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

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
    } catch {
      // keep dialog open on error
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Sequences</h1>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-1" /> New Sequence
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Sequence</DialogTitle>
              <DialogDescription>
                Set up a new outreach sequence. You can add steps after creating it.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="seq-name">Name</Label>
                <Input
                  id="seq-name"
                  placeholder="e.g. Q4 Enterprise Outreach"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="seq-desc">Description (optional)</Label>
                <Textarea
                  id="seq-desc"
                  placeholder="Describe the goal of this sequence…"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={!newName.trim() || creating}>
                {creating ? "Creating…" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SequenceSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-10 text-center text-red-500 text-sm">
            Failed to load sequences. Please try again.
          </CardContent>
        </Card>
      ) : !data?.items.length ? (
        <Card>
          <CardContent className="py-16 text-center">
            <GitBranch className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No sequences yet</p>
            <p className="text-sm text-gray-400 mt-1">
              Create your first outreach sequence to get started.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.items.map((seq) => (
              <Link key={seq.id} href={`/sequences/${seq.id}`}>
                <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base">{seq.name}</CardTitle>
                      <Badge className={STATUS_COLORS[seq.status] ?? "bg-gray-100"}>
                        {seq.status}
                      </Badge>
                    </div>
                    {seq.description && (
                      <CardDescription className="line-clamp-2">
                        {seq.description}
                      </CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <span>{seq.steps?.length ?? 0} steps</span>
                        <span>{seq.enrolled_count} enrolled</span>
                      </div>
                      <Link
                        href={`/sequences/builder/${seq.id}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button variant="ghost" size="sm" className="h-7 px-2">
                          <Pencil className="h-3.5 w-3.5 mr-1" /> Builder
                        </Button>
                      </Link>
                    </div>
                    {seq.ai_generated && (
                      <div className="flex items-center gap-1 text-xs text-purple-500 mt-1">
                        <Sparkles className="h-3 w-3" /> AI Generated
                      </div>
                    )}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Page {page} of {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
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
