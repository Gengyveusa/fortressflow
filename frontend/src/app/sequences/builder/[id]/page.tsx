"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import ReactFlow, {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  Node,
  NodeTypes,
  Panel,
  useEdgesState,
  useNodesState,
  useReactFlow,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  ArrowLeft,
  Save,
  Sparkles,
  Play,
  Pause,
  Mail,
  MessageSquare,
  Linkedin,
  Clock,
  GitBranch,
  Split,
  CircleStop,
  Plus,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { sequencesApi } from "@/lib/api";
import type { VisualConfig } from "@/lib/api";

/* ─── Custom Node Components ─────────────────────────────────────── */

function StartNode({ data }: { data: { label: string } }) {
  return (
    <div className="rounded-full bg-green-500 text-white px-4 py-2 text-sm font-medium shadow-md border-2 border-green-600 min-w-[80px] text-center">
      {data.label}
    </div>
  );
}

function EmailNode({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg bg-blue-50 border-2 border-blue-300 px-4 py-3 shadow-sm min-w-[200px]">
      <div className="flex items-center gap-2 mb-1">
        <Mail className="h-4 w-4 text-blue-600" />
        <span className="text-xs font-semibold text-blue-700 uppercase">Email</span>
      </div>
      <p className="text-sm text-gray-700 truncate">
        {(data.label as string) || "Send Email"}
      </p>
      {data.delayHours ? (
        <p className="text-xs text-gray-400 mt-1">After {data.delayHours as number}h delay</p>
      ) : null}
    </div>
  );
}

function SmsNode({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg bg-purple-50 border-2 border-purple-300 px-4 py-3 shadow-sm min-w-[200px]">
      <div className="flex items-center gap-2 mb-1">
        <MessageSquare className="h-4 w-4 text-purple-600" />
        <span className="text-xs font-semibold text-purple-700 uppercase">SMS</span>
      </div>
      <p className="text-sm text-gray-700 truncate">
        {(data.label as string) || "Send SMS"}
      </p>
    </div>
  );
}

function LinkedInNode({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg bg-sky-50 border-2 border-sky-300 px-4 py-3 shadow-sm min-w-[200px]">
      <div className="flex items-center gap-2 mb-1">
        <Linkedin className="h-4 w-4 text-sky-600" />
        <span className="text-xs font-semibold text-sky-700 uppercase">LinkedIn</span>
      </div>
      <p className="text-sm text-gray-700 truncate">
        {(data.label as string) || "LinkedIn Action"}
      </p>
    </div>
  );
}

function WaitNode({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg bg-amber-50 border-2 border-amber-300 px-4 py-3 shadow-sm min-w-[160px]">
      <div className="flex items-center gap-2">
        <Clock className="h-4 w-4 text-amber-600" />
        <span className="text-sm font-medium text-amber-800">
          {(data.label as string) || "Wait"}
        </span>
      </div>
    </div>
  );
}

function ConditionalNode({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="bg-orange-50 border-2 border-orange-400 px-4 py-3 shadow-sm min-w-[180px]"
      style={{ transform: "rotate(0deg)", borderRadius: "8px" }}>
      <div className="flex items-center gap-2 mb-1">
        <GitBranch className="h-4 w-4 text-orange-600" />
        <span className="text-xs font-semibold text-orange-700 uppercase">Condition</span>
      </div>
      <p className="text-sm text-gray-700">
        {(data.label as string) || "If/Else"}
      </p>
    </div>
  );
}

function ABSplitNode({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-lg bg-pink-50 border-2 border-pink-400 px-4 py-3 shadow-sm min-w-[180px]">
      <div className="flex items-center gap-2 mb-1">
        <Split className="h-4 w-4 text-pink-600" />
        <span className="text-xs font-semibold text-pink-700 uppercase">A/B Test</span>
      </div>
      <p className="text-sm text-gray-700">
        {(data.label as string) || "A/B Split"}
      </p>
      {data.abVariants != null && typeof data.abVariants === "object" && (
        <div className="flex gap-1 mt-1">
          {Object.keys(data.abVariants as Record<string, unknown>).map((v) => (
            <Badge key={v} variant="secondary" className="text-xs">
              {v}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function EndNode({ data }: { data: { label: string } }) {
  return (
    <div className="rounded-full bg-gray-500 text-white px-4 py-2 text-sm font-medium shadow-md border-2 border-gray-600 min-w-[80px] text-center flex items-center gap-2 justify-center">
      <CircleStop className="h-3 w-3" />
      {data.label}
    </div>
  );
}

const nodeTypes: NodeTypes = {
  start: StartNode,
  email: EmailNode,
  sms: SmsNode,
  linkedin: LinkedInNode,
  wait: WaitNode,
  conditional: ConditionalNode,
  ab_split: ABSplitNode,
  end: EndNode,
};

/* ─── Node Toolbar / Add Panel ───────────────────────────────────── */

const NODE_PALETTE = [
  { type: "email", label: "Email", icon: Mail, color: "bg-blue-100 text-blue-700" },
  { type: "sms", label: "SMS", icon: MessageSquare, color: "bg-purple-100 text-purple-700" },
  { type: "linkedin", label: "LinkedIn", icon: Linkedin, color: "bg-sky-100 text-sky-700" },
  { type: "wait", label: "Wait", icon: Clock, color: "bg-amber-100 text-amber-700" },
  { type: "conditional", label: "Condition", icon: GitBranch, color: "bg-orange-100 text-orange-700" },
  { type: "ab_split", label: "A/B Test", icon: Split, color: "bg-pink-100 text-pink-700" },
  { type: "end", label: "End", icon: CircleStop, color: "bg-gray-100 text-gray-700" },
];

/* ─── Main Builder ───────────────────────────────────────────────── */

function BuilderCanvas() {
  const params = useParams();
  const router = useRouter();
  const sequenceId = params.id as string;
  const { fitView } = useReactFlow();

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [sequenceName, setSequenceName] = useState("");
  const [sequenceStatus, setSequenceStatus] = useState("draft");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // Load sequence and visual config
  useEffect(() => {
    async function load() {
      try {
        const seqRes = await sequencesApi.get(sequenceId);
        const seq = seqRes.data;
        setSequenceName(seq.name);
        setSequenceStatus(seq.status);

        if (seq.visual_config) {
          setNodes(seq.visual_config.nodes || []);
          setEdges(seq.visual_config.edges || []);
        } else if (seq.steps.length > 0) {
          // Generate visual config from steps
          const generatedNodes: Node[] = [
            {
              id: "start",
              type: "start",
              position: { x: 400, y: 0 },
              data: { label: "Start" },
            },
          ];
          const generatedEdges: Edge[] = [];
          let yPos = 120;

          seq.steps.forEach((step, i) => {
            const nodeId = step.node_id || `step_${step.position}`;
            generatedNodes.push({
              id: nodeId,
              type: step.step_type,
              position: { x: 400, y: yPos },
              data: {
                label: step.config?.subject_hint || step.config?.description || step.step_type,
                stepType: step.step_type,
                position: step.position,
                delayHours: step.delay_hours,
                config: step.config,
                condition: step.condition,
                abVariants: step.ab_variants,
              },
            });

            const prevId = i === 0 ? "start" : (seq.steps[i - 1].node_id || `step_${seq.steps[i - 1].position}`);
            generatedEdges.push({
              id: `e_${prevId}_${nodeId}`,
              source: prevId,
              target: nodeId,
            });

            yPos += 120;
          });

          setNodes(generatedNodes);
          setEdges(generatedEdges);
        } else {
          // Empty — start with just a start node
          setNodes([
            {
              id: "start",
              type: "start",
              position: { x: 400, y: 0 },
              data: { label: "Start" },
            },
          ]);
        }
      } catch {
        // Handle error
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sequenceId, setNodes, setEdges]);

  // Fit view once loaded
  useEffect(() => {
    if (!loading && nodes.length > 0) {
      setTimeout(() => fitView({ padding: 0.2 }), 100);
    }
  }, [loading, nodes.length, fitView]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, animated: true }, eds));
    },
    [setEdges]
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const addNode = useCallback(
    (type: string) => {
      const id = `${type}_${Date.now()}`;
      const maxY = nodes.reduce((max, n) => Math.max(max, n.position.y), 0);
      const newNode: Node = {
        id,
        type,
        position: { x: 400, y: maxY + 120 },
        data: {
          label: type === "wait" ? "Wait 24h" : type.replace("_", " ").replace(/^\w/, (c: string) => c.toUpperCase()),
          stepType: type,
          delayHours: type === "wait" ? 24 : 0,
        },
      };
      setNodes((nds) => [...nds, newNode]);

      // Auto-connect to last node
      if (nodes.length > 0) {
        const lastNode = nodes[nodes.length - 1];
        setEdges((eds) => [
          ...eds,
          {
            id: `e_${lastNode.id}_${id}`,
            source: lastNode.id,
            target: id,
            animated: true,
          },
        ]);
      }
    },
    [nodes, setNodes, setEdges]
  );

  const deleteSelectedNode = useCallback(() => {
    if (!selectedNode || selectedNode.id === "start") return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
    setEdges((eds) =>
      eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id)
    );
    setSelectedNode(null);
  }, [selectedNode, setNodes, setEdges]);

  // Save visual config
  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const visualConfig: VisualConfig = {
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type || "default",
          position: n.position,
          data: n.data as Record<string, unknown>,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? undefined,
          label: typeof e.label === "string" ? e.label : undefined,
        })),
        viewport: { x: 0, y: 0, zoom: 1 },
      };
      await sequencesApi.saveVisualConfig(sequenceId, {
        visual_config: visualConfig,
      });
    } catch {
      // Handle save error
    } finally {
      setSaving(false);
    }
  }, [sequenceId, nodes, edges]);

  // AI generation
  const handleGenerate = useCallback(async () => {
    if (!generatePrompt.trim()) return;
    setGenerating(true);
    try {
      const res = await sequencesApi.generate({
        prompt: generatePrompt,
        include_ab_test: true,
        include_conditionals: true,
      });
      const result = res.data;
      if (result.success && result.visual_config) {
        setNodes(result.visual_config.nodes || []);
        setEdges(result.visual_config.edges || []);
        setGenerateOpen(false);
        setGeneratePrompt("");
        // Navigate to the newly generated sequence
        if (result.sequence_id) {
          router.push(`/sequences/builder/${result.sequence_id}`);
        }
      }
    } catch {
      // Handle generation error
    } finally {
      setGenerating(false);
    }
  }, [generatePrompt, setNodes, setEdges, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push("/sequences")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-lg font-semibold">{sequenceName || "Sequence Builder"}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <Badge variant="outline">{sequenceStatus}</Badge>
              <span className="text-xs text-gray-400">{nodes.length - 1} steps</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Sparkles className="h-4 w-4 mr-1" /> AI Generate
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Generate Sequence with AI</DialogTitle>
                <DialogDescription>
                  Describe your outreach sequence in plain English. Our AI will consult HubSpot Breeze,
                  ZoomInfo Copilot, and Apollo AI to build an optimized multi-step sequence.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-2">
                <Label>Describe your sequence</Label>
                <Textarea
                  rows={4}
                  placeholder="e.g., Create a 7-step outreach sequence for dental offices introducing Gengyve natural mouthwash. Start with email, follow up on LinkedIn, use SMS as a final touch. Include A/B testing on the first email subject line."
                  value={generatePrompt}
                  onChange={(e) => setGeneratePrompt(e.target.value)}
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setGenerateOpen(false)}>Cancel</Button>
                <Button onClick={handleGenerate} disabled={!generatePrompt.trim() || generating}>
                  {generating ? "Generating…" : "Generate"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button size="sm" onClick={handleSave} disabled={saving}>
            <Save className="h-4 w-4 mr-1" /> {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          className="bg-gray-50"
          defaultEdgeOptions={{ animated: true }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} size={1} />
          <Controls />
          <MiniMap
            nodeStrokeWidth={3}
            className="bg-white rounded-lg border border-gray-200"
          />

          {/* Add Node Panel */}
          <Panel position="top-left">
            <Card className="shadow-lg">
              <CardHeader className="py-2 px-3">
                <CardTitle className="text-xs font-medium text-gray-500 uppercase">
                  Add Node
                </CardTitle>
              </CardHeader>
              <CardContent className="p-2 space-y-1">
                {NODE_PALETTE.map((item) => (
                  <button
                    key={item.type}
                    onClick={() => addNode(item.type)}
                    className={`flex items-center gap-2 w-full px-3 py-1.5 rounded text-sm font-medium transition-colors hover:opacity-80 ${item.color}`}
                  >
                    <item.icon className="h-3.5 w-3.5" />
                    {item.label}
                  </button>
                ))}
              </CardContent>
            </Card>
          </Panel>

          {/* Selected Node Properties */}
          {selectedNode && selectedNode.id !== "start" && (
            <Panel position="top-right">
              <Card className="shadow-lg w-72">
                <CardHeader className="py-2 px-3 flex flex-row items-center justify-between">
                  <CardTitle className="text-sm">Node Properties</CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-red-500"
                    onClick={deleteSelectedNode}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </CardHeader>
                <CardContent className="p-3 space-y-3">
                  <div>
                    <Label className="text-xs">Type</Label>
                    <Badge variant="secondary" className="mt-1">
                      {selectedNode.type}
                    </Badge>
                  </div>
                  <div>
                    <Label className="text-xs">Label</Label>
                    <Input
                      className="mt-1 h-8 text-sm"
                      value={(selectedNode.data?.label as string) || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? { ...n, data: { ...n.data, label: val } }
                              : n
                          )
                        );
                        setSelectedNode((prev) =>
                          prev ? { ...prev, data: { ...prev.data, label: val } } : null
                        );
                      }}
                    />
                  </div>
                  {selectedNode.type === "wait" && (
                    <div>
                      <Label className="text-xs">Delay (hours)</Label>
                      <Input
                        type="number"
                        className="mt-1 h-8 text-sm"
                        value={(selectedNode.data?.delayHours as number) || 0}
                        onChange={(e) => {
                          const val = parseInt(e.target.value) || 0;
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? { ...n, data: { ...n.data, delayHours: val, label: val >= 24 ? `Wait ${Math.round(val/24)}d` : `Wait ${val}h` } }
                                : n
                            )
                          );
                        }}
                      />
                    </div>
                  )}
                  {selectedNode.type === "conditional" && (
                    <div>
                      <Label className="text-xs">Condition Type</Label>
                      <Select
                        value={(selectedNode.data?.condition as Record<string, string>)?.type || "opened"}
                        onValueChange={(val) => {
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? { ...n, data: { ...n.data, condition: { type: val }, label: `If: ${val}` } }
                                : n
                            )
                          );
                        }}
                      >
                        <SelectTrigger className="mt-1 h-8 text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="opened">Opened</SelectItem>
                          <SelectItem value="not_opened">Not Opened</SelectItem>
                          <SelectItem value="replied">Replied</SelectItem>
                          <SelectItem value="not_replied">Not Replied</SelectItem>
                          <SelectItem value="clicked">Clicked</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  <p className="text-xs text-gray-400">ID: {selectedNode.id}</p>
                </CardContent>
              </Card>
            </Panel>
          )}
        </ReactFlow>
      </div>
    </div>
  );
}

export default function SequenceBuilderPage() {
  return (
    <ReactFlowProvider>
      <BuilderCanvas />
    </ReactFlowProvider>
  );
}
