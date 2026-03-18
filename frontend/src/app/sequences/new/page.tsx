"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import ReactFlow, {
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  Shield,
  ArrowLeft,
  Mail,
  MessageSquare,
  Linkedin,
  Clock,
  GitBranch,
  Plus,
} from "lucide-react";

const STEP_TYPES = [
  { type: "email", label: "Email", icon: Mail, color: "bg-blue-100 text-blue-700 border-blue-200" },
  { type: "linkedin", label: "LinkedIn", icon: Linkedin, color: "bg-sky-100 text-sky-700 border-sky-200" },
  { type: "sms", label: "SMS", icon: MessageSquare, color: "bg-green-100 text-green-700 border-green-200" },
  { type: "wait", label: "Wait", icon: Clock, color: "bg-yellow-100 text-yellow-700 border-yellow-200" },
  { type: "condition", label: "Condition", icon: GitBranch, color: "bg-purple-100 text-purple-700 border-purple-200" },
];

const initialNodes: Node[] = [
  {
    id: "start",
    type: "input",
    position: { x: 250, y: 50 },
    data: { label: "🚀 Start" },
    style: { background: "#dbeafe", border: "1px solid #93c5fd", borderRadius: 8, padding: 10, fontWeight: 600 },
  },
];

const initialEdges: Edge[] = [];

let nodeId = 1;

export default function SequenceBuilderPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [sequenceName, setSequenceName] = useState("New Sequence");
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const addStep = (stepType: (typeof STEP_TYPES)[number]) => {
    const id = `step-${nodeId++}`;
    const newNode: Node = {
      id,
      position: { x: 200 + Math.random() * 100, y: 150 + nodes.length * 100 },
      data: { label: stepType.label, type: stepType.type },
      style: {
        background: "white",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: 10,
        minWidth: 120,
      },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-full">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-600" />
            <span className="text-xl font-bold text-gray-900">FortressFlow</span>
          </div>
          <div className="flex items-center gap-4">
            <input
              type="text"
              value={sequenceName}
              onChange={(e) => setSequenceName(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
              Save Sequence
            </button>
          </div>
        </div>
      </nav>

      <div className="flex h-[calc(100vh-65px)]">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-gray-200 p-4 overflow-y-auto shrink-0">
          <div className="mb-4">
            <Link
              href="/sequences"
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Sequences
            </Link>
          </div>

          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Step Types
          </h3>
          <div className="space-y-2">
            {STEP_TYPES.map((step) => (
              <button
                key={step.type}
                onClick={() => addStep(step)}
                className={`w-full flex items-center gap-3 p-3 rounded-lg border text-sm font-medium hover:opacity-80 transition-opacity ${step.color}`}
              >
                <step.icon className="w-4 h-4" />
                <span>{step.label}</span>
                <Plus className="w-3 h-3 ml-auto" />
              </button>
            ))}
          </div>

          {selectedNode && (
            <div className="mt-6">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Step Config
              </h3>
              <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-700">
                <p className="font-medium">{String(selectedNode.data?.label ?? "")}</p>
                <p className="text-xs text-gray-500 mt-1">ID: {selectedNode.id}</p>
              </div>
            </div>
          )}
        </aside>

        {/* Canvas */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNode(node)}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}
