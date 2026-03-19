"use client";

import { useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type Connection,
  type NodeProps,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  ArrowLeft,
  Mail,
  Linkedin,
  MessageSquare,
  Clock,
  GitBranch as SplitIcon,
  Save,
  UserPlus,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useSequence } from "@/lib/hooks";
import { sequencesApi, type SequenceStep } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

/* ── Node type config ────────────────────────────────── */
const STEP_TYPES = [
  { type: "email", label: "Email", icon: Mail, color: "bg-blue-50 border-blue-200 text-blue-700" },
  { type: "linkedin", label: "LinkedIn", icon: Linkedin, color: "bg-sky-50 border-sky-200 text-sky-700" },
  { type: "sms", label: "SMS", icon: MessageSquare, color: "bg-green-50 border-green-200 text-green-700" },
  { type: "wait", label: "Wait", icon: Clock, color: "bg-amber-50 border-amber-200 text-amber-700" },
  { type: "condition", label: "Condition", icon: SplitIcon, color: "bg-purple-50 border-purple-200 text-purple-700" },
];

function getStepConfig(stepType: string) {
  return STEP_TYPES.find((s) => s.type === stepType) ?? STEP_TYPES[0];
}

/* ── Custom ReactFlow node ───────────────────────────── */
function StepNode({ data }: NodeProps) {
  const cfg = getStepConfig(data.stepType);
  const Icon = cfg.icon;
  return (
    <div className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[160px] ${cfg.color}`}>
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4" />
        <span className="text-sm font-medium">{cfg.label}</span>
      </div>
      {data.label && (
        <p className="text-xs mt-1 opacity-70 truncate max-w-[140px]">{data.label}</p>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400" />
    </div>
  );
}

const nodeTypes = { stepNode: StepNode };

/* ── helpers ─────────────────────────────────────────── */
function stepsToFlow(steps: SequenceStep[]): { nodes: Node[]; edges: Edge[] } {
  const sorted = [...steps].sort((a, b) => a.position - b.position);
  const nodes: Node[] = sorted.map((s, i) => ({
    id: s.id,
    type: "stepNode",
    position: { x: 250, y: i * 120 },
    data: { stepType: s.step_type, label: typeof s.config?.subject === "string" ? s.config.subject : "" },
  }));
  const edges: Edge[] = sorted.slice(1).map((s, i) => ({
    id: `e-${sorted[i].id}-${s.id}`,
    source: sorted[i].id,
    target: s.id,
    animated: true,
  }));
  return { nodes, edges };
}

export default function SequenceBuilderPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data: sequence, isLoading, error } = useSequence(id);
  const queryClient = useQueryClient();

  const initial = useMemo(
    () => (sequence?.steps ? stepsToFlow(sequence.steps) : { nodes: [], edges: [] }),
    [sequence?.steps]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const onConnect = useCallback(
    (conn: Connection) => setEdges((eds) => addEdge({ ...conn, animated: true }, eds)),
    [setEdges]
  );

  // sync when data loads
  const [initialized, setInitialized] = useState(false);
  if (sequence?.steps && !initialized && initial.nodes.length > 0) {
    setNodes(initial.nodes);
    setEdges(initial.edges);
    setInitialized(true);
  }

  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [adding, setAdding] = useState(false);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [enrollIds, setEnrollIds] = useState("");
  const [enrolling, setEnrolling] = useState(false);

  const addStep = async (stepType: string) => {
    setAdding(true);
    try {
      await sequencesApi.addStep(id, {
        step_type: stepType,
        position: nodes.length,
        delay_hours: stepType === "wait" ? 24 : 0,
      });
      queryClient.invalidateQueries({ queryKey: ["sequence", id] });
      setInitialized(false);
    } finally {
      setAdding(false);
    }
  };

  const handleEnroll = async () => {
    const ids = enrollIds
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!ids.length) return;
    setEnrolling(true);
    try {
      await sequencesApi.enroll(id, ids);
      setEnrollOpen(false);
      setEnrollIds("");
      queryClient.invalidateQueries({ queryKey: ["sequence", id] });
    } finally {
      setEnrolling(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-2">
          <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-gray-500">Loading sequence…</p>
        </div>
      </div>
    );
  }

  if (error || !sequence) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/sequences">
            <ArrowLeft className="h-4 w-4 mr-1" /> Sequences
          </Link>
        </Button>
        <Card>
          <CardContent className="py-10 text-center text-red-500 text-sm">
            Failed to load sequence. It may not exist.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/sequences">
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Link>
          </Button>
          <h1 className="text-xl font-semibold">{sequence.name}</h1>
          <Badge
            className={
              sequence.status === "active"
                ? "bg-green-100 text-green-700"
                : sequence.status === "paused"
                  ? "bg-yellow-100 text-yellow-700"
                  : "bg-gray-100 text-gray-700"
            }
          >
            {sequence.status}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Dialog open={enrollOpen} onOpenChange={setEnrollOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <UserPlus className="h-4 w-4 mr-1" /> Enroll Leads
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Enroll Leads</DialogTitle>
                <DialogDescription>
                  Enter lead IDs separated by commas or newlines.
                </DialogDescription>
              </DialogHeader>
              <Textarea
                placeholder="lead-id-1, lead-id-2, ..."
                value={enrollIds}
                onChange={(e) => setEnrollIds(e.target.value)}
                rows={4}
              />
              <DialogFooter>
                <Button variant="outline" onClick={() => setEnrollOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleEnroll} disabled={enrolling || !enrollIds.trim()}>
                  {enrolling ? "Enrolling…" : "Enroll"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button size="sm">
            <Save className="h-4 w-4 mr-1" /> Save
          </Button>
        </div>
      </div>

      <div className="flex gap-4 h-[calc(100vh-220px)]">
        {/* Step palette */}
        <Card className="w-52 shrink-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Add Step</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {STEP_TYPES.map((st) => (
              <Button
                key={st.type}
                variant="outline"
                size="sm"
                className="w-full justify-start"
                disabled={adding}
                onClick={() => addStep(st.type)}
              >
                <st.icon className="h-4 w-4 mr-2" />
                {st.label}
              </Button>
            ))}
          </CardContent>
        </Card>

        {/* ReactFlow canvas */}
        <Card className="flex-1 p-0 overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNode(node)}
            nodeTypes={nodeTypes}
            fitView
            className="bg-gray-50"
          >
            <Background />
            <Controls />
            <MiniMap zoomable pannable className="!bg-white" />
          </ReactFlow>
        </Card>
      </div>

      {/* Config sheet */}
      <Sheet open={!!selectedNode} onOpenChange={(open) => !open && setSelectedNode(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>
              {selectedNode ? getStepConfig(selectedNode.data.stepType).label : "Step"} Configuration
            </SheetTitle>
            <SheetDescription>Edit this step&apos;s settings.</SheetDescription>
          </SheetHeader>
          {selectedNode && (
            <div className="space-y-4 mt-6">
              <div className="space-y-2">
                <Label>Step Type</Label>
                <Input value={getStepConfig(selectedNode.data.stepType).label} readOnly />
              </div>
              <div className="space-y-2">
                <Label>Subject / Label</Label>
                <Input
                  placeholder="Enter a subject or label…"
                  defaultValue={selectedNode.data.label ?? ""}
                />
              </div>
              <div className="space-y-2">
                <Label>Delay (hours)</Label>
                <Input type="number" defaultValue={0} min={0} />
              </div>
              <Button className="w-full mt-4" onClick={() => setSelectedNode(null)}>
                Done
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
