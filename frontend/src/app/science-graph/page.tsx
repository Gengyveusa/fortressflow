"use client";

import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  BrainCircuit,
  Link2,
  BookOpen,
  X,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  FileText,
  Shield,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  Info,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────

interface GraphNode {
  id: string;
  label: string;
  type: "oral" | "systemic" | "mechanism" | "treatment";
  description: string;
  related_conditions: string[];
  evidence_level: "strong" | "moderate" | "emerging";
  x: number;
  y: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: string;
  strength: number;
  evidence_level: "strong" | "moderate" | "emerging";
  bidirectional: boolean;
  citations: Citation[];
}

interface Citation {
  id: string;
  title: string;
  authors: string;
  journal: string;
  year: number;
  doi?: string;
}

interface ScienceGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  citation_requirements: CitationRequirement[];
  last_updated: string;
}

interface CitationRequirement {
  claim_type: string;
  minimum_citations: number;
  required_evidence_level: string;
  description: string;
}

// ── Mock Data ───────────────────────────────────────────────

const MOCK_DATA: ScienceGraphData = {
  nodes: [
    { id: "n1", label: "Periodontal Disease", type: "oral", description: "Chronic inflammatory condition affecting the tissues surrounding and supporting the teeth. Associated with deep gum pockets, bone loss, and eventual tooth loss if untreated.", related_conditions: ["Cardiovascular Disease", "Diabetes", "Alzheimer's Disease"], evidence_level: "strong", x: 400, y: 200 },
    { id: "n2", label: "Cardiovascular Disease", type: "systemic", description: "Group of disorders of the heart and blood vessels. Growing evidence links oral bacteria to arterial plaque formation and endothelial dysfunction.", related_conditions: ["Periodontal Disease", "Systemic Inflammation"], evidence_level: "strong", x: 150, y: 80 },
    { id: "n3", label: "Type 2 Diabetes", type: "systemic", description: "Metabolic disorder characterized by insulin resistance. Bidirectional relationship with periodontal disease - each condition worsens the other.", related_conditions: ["Periodontal Disease", "Systemic Inflammation"], evidence_level: "strong", x: 650, y: 80 },
    { id: "n4", label: "Systemic Inflammation", type: "mechanism", description: "Chronic low-grade inflammation driven by oral pathogens entering the bloodstream. Elevated CRP, IL-6, and TNF-alpha markers observed in patients with periodontitis.", related_conditions: ["Periodontal Disease", "Cardiovascular Disease", "Type 2 Diabetes"], evidence_level: "strong", x: 400, y: 400 },
    { id: "n5", label: "Alzheimer's Disease", type: "systemic", description: "Neurodegenerative condition. P. gingivalis and its toxic proteases (gingipains) have been detected in brain tissue of Alzheimer's patients.", related_conditions: ["Periodontal Disease", "Systemic Inflammation"], evidence_level: "moderate", x: 150, y: 350 },
    { id: "n6", label: "Oral Microbiome", type: "oral", description: "Complex community of microorganisms in the oral cavity. Dysbiosis of the oral microbiome is a precursor to periodontal disease and may influence systemic health.", related_conditions: ["Periodontal Disease", "Systemic Inflammation", "Respiratory Infections"], evidence_level: "strong", x: 650, y: 350 },
    { id: "n7", label: "Respiratory Infections", type: "systemic", description: "Including pneumonia and COPD exacerbations. Aspiration of oral pathogens into the lower respiratory tract is a recognized risk factor.", related_conditions: ["Oral Microbiome", "Periodontal Disease"], evidence_level: "moderate", x: 650, y: 200 },
    { id: "n8", label: "Fluoride Therapy", type: "treatment", description: "Topical and systemic fluoride application for caries prevention. Reduces demineralization and enhances remineralization of tooth enamel.", related_conditions: ["Periodontal Disease", "Oral Microbiome"], evidence_level: "strong", x: 400, y: 550 },
    { id: "n9", label: "Adverse Pregnancy Outcomes", type: "systemic", description: "Preterm birth and low birth weight associated with maternal periodontal disease. Inflammatory mediators may affect fetal development.", related_conditions: ["Periodontal Disease", "Systemic Inflammation"], evidence_level: "emerging", x: 150, y: 200 },
  ],
  edges: [
    { id: "e1", source: "n1", target: "n2", relationship: "Increases risk of", strength: 0.85, evidence_level: "strong", bidirectional: false, citations: [
      { id: "c1", title: "Periodontal disease and cardiovascular disease: epidemiology and possible mechanisms", authors: "Lockhart PB et al.", journal: "J Am Dent Assoc", year: 2012, doi: "10.14219/jada.archive.2012.0113" },
      { id: "c2", title: "Oral infections and cardiovascular disease", authors: "Mattila KJ et al.", journal: "J Periodontol", year: 2005 },
    ]},
    { id: "e2", source: "n1", target: "n3", relationship: "Bidirectional exacerbation", strength: 0.9, evidence_level: "strong", bidirectional: true, citations: [
      { id: "c3", title: "Diabetes and periodontal disease: a two-way relationship", authors: "Preshaw PM et al.", journal: "Diabetologia", year: 2012, doi: "10.1007/s00125-011-2342-y" },
    ]},
    { id: "e3", source: "n1", target: "n4", relationship: "Triggers", strength: 0.92, evidence_level: "strong", bidirectional: false, citations: [
      { id: "c4", title: "Systemic effects of periodontitis: biomarker and inflammatory evidence", authors: "D'Aiuto F et al.", journal: "J Clin Periodontol", year: 2004 },
    ]},
    { id: "e4", source: "n4", target: "n2", relationship: "Contributes to", strength: 0.78, evidence_level: "strong", bidirectional: false, citations: [
      { id: "c5", title: "Inflammation and atherosclerosis", authors: "Libby P et al.", journal: "Circulation", year: 2002 },
    ]},
    { id: "e5", source: "n4", target: "n3", relationship: "Worsens insulin resistance", strength: 0.72, evidence_level: "moderate", bidirectional: true, citations: [
      { id: "c6", title: "Inflammation, insulin resistance, and diabetes", authors: "Shoelson SE et al.", journal: "J Clin Invest", year: 2006 },
    ]},
    { id: "e6", source: "n1", target: "n5", relationship: "Linked via P. gingivalis", strength: 0.6, evidence_level: "moderate", bidirectional: false, citations: [
      { id: "c7", title: "Porphyromonas gingivalis in Alzheimer's disease brains", authors: "Dominy SS et al.", journal: "Science Advances", year: 2019, doi: "10.1126/sciadv.aau3333" },
    ]},
    { id: "e7", source: "n6", target: "n1", relationship: "Dysbiosis leads to", strength: 0.88, evidence_level: "strong", bidirectional: false, citations: [
      { id: "c8", title: "The oral microbiome in health and disease", authors: "Deo PN, Deshmukh R.", journal: "J Oral Maxillofac Pathol", year: 2019 },
    ]},
    { id: "e8", source: "n6", target: "n7", relationship: "Pathogen aspiration", strength: 0.65, evidence_level: "moderate", bidirectional: false, citations: [
      { id: "c9", title: "Role of oral bacteria in respiratory infection", authors: "Scannapieco FA.", journal: "J Periodontol", year: 1999 },
    ]},
    { id: "e9", source: "n8", target: "n1", relationship: "Preventive therapy for", strength: 0.75, evidence_level: "strong", bidirectional: false, citations: [
      { id: "c10", title: "Fluoride mechanisms of action and clinical implications", authors: "Buzalaf MAR et al.", journal: "Braz Oral Res", year: 2011 },
    ]},
    { id: "e10", source: "n1", target: "n9", relationship: "Associated with", strength: 0.55, evidence_level: "emerging", bidirectional: false, citations: [
      { id: "c11", title: "Periodontal disease and adverse pregnancy outcomes", authors: "Offenbacher S et al.", journal: "J Periodontol", year: 2006 },
    ]},
  ],
  citation_requirements: [
    { claim_type: "Causal Relationship", minimum_citations: 3, required_evidence_level: "strong", description: "Claims asserting that one condition directly causes another require at least 3 peer-reviewed citations with strong evidence." },
    { claim_type: "Correlation", minimum_citations: 2, required_evidence_level: "moderate", description: "Claims of statistical association require at least 2 peer-reviewed studies." },
    { claim_type: "Treatment Efficacy", minimum_citations: 2, required_evidence_level: "strong", description: "Claims about treatment effectiveness require RCT or systematic review evidence." },
    { claim_type: "Emerging Research", minimum_citations: 1, required_evidence_level: "emerging", description: "Preliminary findings require at least 1 published study and must be labeled as emerging." },
  ],
  last_updated: "2026-03-15T00:00:00Z",
};

// ── Helpers ─────────────────────────────────────────────────

const NODE_TYPE_STYLES: Record<string, { bg: string; border: string; text: string; label: string }> = {
  oral: { bg: "bg-blue-500/20", border: "border-blue-500/50", text: "text-blue-300", label: "Oral" },
  systemic: { bg: "bg-rose-500/20", border: "border-rose-500/50", text: "text-rose-300", label: "Systemic" },
  mechanism: { bg: "bg-amber-500/20", border: "border-amber-500/50", text: "text-amber-300", label: "Mechanism" },
  treatment: { bg: "bg-emerald-500/20", border: "border-emerald-500/50", text: "text-emerald-300", label: "Treatment" },
};

function evidenceBadge(level: string) {
  switch (level) {
    case "strong":
      return (
        <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-[10px]">
          <CheckCircle2 className="w-2.5 h-2.5 mr-0.5" /> Strong
        </Badge>
      );
    case "moderate":
      return (
        <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 text-[10px]">
          <Info className="w-2.5 h-2.5 mr-0.5" /> Moderate
        </Badge>
      );
    case "emerging":
      return (
        <Badge className="bg-violet-500/15 text-violet-400 border-violet-500/30 text-[10px]">
          <AlertCircle className="w-2.5 h-2.5 mr-0.5" /> Emerging
        </Badge>
      );
    default:
      return null;
  }
}

function strengthColor(strength: number): string {
  if (strength >= 0.8) return "stroke-emerald-500";
  if (strength >= 0.6) return "stroke-amber-500";
  return "stroke-gray-500";
}

function strengthOpacity(strength: number): number {
  return 0.3 + strength * 0.7;
}

// ── Graph Visualization ─────────────────────────────────────

function KnowledgeGraph({
  nodes,
  edges,
  selectedNodeId,
  selectedEdgeId,
  onSelectNode,
  onSelectEdge,
  zoom,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onSelectNode: (id: string | null) => void;
  onSelectEdge: (id: string | null) => void;
  zoom: number;
}) {
  const nodeMap = useMemo(() => {
    const m = new Map<string, GraphNode>();
    nodes.forEach((n) => m.set(n.id, n));
    return m;
  }, [nodes]);

  return (
    <div
      className="relative w-full overflow-auto rounded-xl bg-gray-950/80 border border-gray-800"
      style={{ height: 500 }}
      role="img"
      aria-label="Oral-systemic health knowledge graph"
    >
      <svg
        width={800 * zoom}
        height={600 * zoom}
        viewBox="0 0 800 600"
        className="mx-auto"
      >
        {/* Edges */}
        {edges.map((edge) => {
          const src = nodeMap.get(edge.source);
          const tgt = nodeMap.get(edge.target);
          if (!src || !tgt) return null;

          const isSelected = selectedEdgeId === edge.id;
          const isConnected =
            selectedNodeId === edge.source || selectedNodeId === edge.target;
          const dimmed =
            (selectedNodeId && !isConnected) || (selectedEdgeId && !isSelected);

          // Midpoint for label
          const mx = (src.x + tgt.x) / 2;
          const my = (src.y + tgt.y) / 2;

          return (
            <g key={edge.id} style={{ opacity: dimmed ? 0.15 : 1 }}>
              <line
                x1={src.x}
                y1={src.y}
                x2={tgt.x}
                y2={tgt.y}
                className={`${strengthColor(edge.strength)} cursor-pointer`}
                strokeWidth={isSelected ? 3 : 1.5}
                strokeOpacity={strengthOpacity(edge.strength)}
                strokeDasharray={edge.evidence_level === "emerging" ? "6 3" : undefined}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectEdge(isSelected ? null : edge.id);
                  onSelectNode(null);
                }}
              />
              {/* Arrowhead */}
              {!edge.bidirectional && (
                <polygon
                  points={computeArrow(src.x, src.y, tgt.x, tgt.y)}
                  className={strengthColor(edge.strength).replace("stroke-", "fill-")}
                  opacity={strengthOpacity(edge.strength)}
                />
              )}
              {/* Strength indicator on hover */}
              <text
                x={mx}
                y={my - 8}
                textAnchor="middle"
                className="fill-gray-500 pointer-events-none"
                fontSize={9}
              >
                {(edge.strength * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const style = NODE_TYPE_STYLES[node.type] ?? NODE_TYPE_STYLES.oral;
          const isSelected = selectedNodeId === node.id;
          const isConnectedToSelectedEdge =
            selectedEdgeId &&
            edges.some(
              (e) =>
                e.id === selectedEdgeId &&
                (e.source === node.id || e.target === node.id)
            );
          const connectedToSelectedNode =
            selectedNodeId &&
            edges.some(
              (e) =>
                (e.source === selectedNodeId && e.target === node.id) ||
                (e.target === selectedNodeId && e.source === node.id)
            );
          const dimmed =
            (selectedNodeId && !isSelected && !connectedToSelectedNode) ||
            (selectedEdgeId && !isConnectedToSelectedEdge);

          return (
            <g
              key={node.id}
              style={{ opacity: dimmed ? 0.2 : 1 }}
              className="cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onSelectNode(isSelected ? null : node.id);
                onSelectEdge(null);
              }}
              role="button"
              aria-label={`Node: ${node.label}`}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onSelectNode(isSelected ? null : node.id);
                  onSelectEdge(null);
                }
              }}
            >
              {/* Glow ring for selected */}
              {isSelected && (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={38}
                  className={style.border.replace("border-", "stroke-")}
                  fill="none"
                  strokeWidth={2}
                  strokeDasharray="4 2"
                  opacity={0.6}
                >
                  <animate
                    attributeName="r"
                    values="36;40;36"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}
              {/* Node circle */}
              <circle
                cx={node.x}
                cy={node.y}
                r={30}
                className={`${style.bg.replace("bg-", "fill-").replace("/20", "")} ${style.border.replace("border-", "stroke-")}`}
                fillOpacity={0.25}
                strokeWidth={isSelected ? 2.5 : 1.5}
              />
              {/* Label */}
              <text
                x={node.x}
                y={node.y}
                textAnchor="middle"
                dominantBaseline="middle"
                className={`${style.text.replace("text-", "fill-")} pointer-events-none`}
                fontSize={node.label.length > 18 ? 7.5 : 9}
                fontWeight={600}
              >
                {wrapText(node.label, 16).map((line, i, arr) => (
                  <tspan
                    key={i}
                    x={node.x}
                    dy={i === 0 ? -(arr.length - 1) * 5 : 11}
                  >
                    {line}
                  </tspan>
                ))}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── SVG Helpers ─────────────────────────────────────────────

function computeArrow(x1: number, y1: number, x2: number, y2: number): string {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const r = 32; // offset from center
  const tipX = x2 - r * Math.cos(angle);
  const tipY = y2 - r * Math.sin(angle);
  const size = 6;
  const p1x = tipX - size * Math.cos(angle - Math.PI / 6);
  const p1y = tipY - size * Math.sin(angle - Math.PI / 6);
  const p2x = tipX - size * Math.cos(angle + Math.PI / 6);
  const p2y = tipY - size * Math.sin(angle + Math.PI / 6);
  return `${tipX},${tipY} ${p1x},${p1y} ${p2x},${p2y}`;
}

function wrapText(text: string, maxLen: number): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    if ((current + " " + word).trim().length > maxLen) {
      if (current) lines.push(current);
      current = word;
    } else {
      current = (current + " " + word).trim();
    }
  }
  if (current) lines.push(current);
  return lines;
}

// ── Main Page ───────────────────────────────────────────────

export default function ScienceGraphPage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [showCitations, setShowCitations] = useState(false);

  const { data, isLoading } = useQuery<ScienceGraphData>({
    queryKey: ["science-graph"],
    queryFn: async () => {
      try {
        const res = await api.get("/insights/auth/science-graph");
        return res.data;
      } catch {
        return MOCK_DATA;
      }
    },
    staleTime: 1000 * 60 * 10,
  });

  const graph = data ?? MOCK_DATA;

  const selectedNode = useMemo(
    () => graph.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId]
  );

  const selectedEdge = useMemo(
    () => graph.edges.find((e) => e.id === selectedEdgeId) ?? null,
    [graph.edges, selectedEdgeId]
  );

  const connectedEdges = useMemo(
    () =>
      selectedNodeId
        ? graph.edges.filter(
            (e) => e.source === selectedNodeId || e.target === selectedNodeId
          )
        : [],
    [graph.edges, selectedNodeId]
  );

  const handleZoomIn = useCallback(() => setZoom((z) => Math.min(z + 0.15, 2)), []);
  const handleZoomOut = useCallback(() => setZoom((z) => Math.max(z - 0.15, 0.5)), []);
  const handleReset = useCallback(() => {
    setZoom(1);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
        <div className="h-10 w-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-gray-400">Loading knowledge graph...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Header ────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-100 flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-cyan-400" />
            Oral-Systemic Health Knowledge Graph
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Evidence-based relationships between oral and systemic conditions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleZoomIn} aria-label="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleZoomOut} aria-label="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleReset} aria-label="Reset view">
            <RotateCcw className="w-4 h-4" />
          </Button>
          <Button
            variant={showCitations ? "default" : "outline"}
            size="sm"
            onClick={() => setShowCitations(!showCitations)}
          >
            <FileText className="w-4 h-4 mr-1" />
            Citations
          </Button>
        </div>
      </div>

      {/* ── Legend ────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-4 px-1">
        {Object.entries(NODE_TYPE_STYLES).map(([key, style]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 rounded-full ${style.bg} border ${style.border}`} />
            <span className="text-xs text-gray-400">{style.label}</span>
          </div>
        ))}
        <div className="border-l border-gray-700 pl-4 flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-emerald-500" />
            <span className="text-xs text-gray-400">Strong</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-amber-500" />
            <span className="text-xs text-gray-400">Moderate</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-gray-500 border-dashed border-t border-gray-500" />
            <span className="text-xs text-gray-400">Emerging</span>
          </div>
        </div>
      </div>

      {/* ── Graph + Detail Panel ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Graph */}
        <div className="lg:col-span-2">
          <KnowledgeGraph
            nodes={graph.nodes}
            edges={graph.edges}
            selectedNodeId={selectedNodeId}
            selectedEdgeId={selectedEdgeId}
            onSelectNode={setSelectedNodeId}
            onSelectEdge={setSelectedEdgeId}
            zoom={zoom}
          />
        </div>

        {/* Detail Panel */}
        <div className="space-y-4">
          {/* Node Detail */}
          {selectedNode ? (
            <Card className="dark:bg-gray-900 dark:border-gray-800">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-sm dark:text-gray-100">
                      {selectedNode.label}
                    </CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge
                        className={`${NODE_TYPE_STYLES[selectedNode.type]?.bg} ${NODE_TYPE_STYLES[selectedNode.type]?.text} border ${NODE_TYPE_STYLES[selectedNode.type]?.border} text-[10px]`}
                      >
                        {NODE_TYPE_STYLES[selectedNode.type]?.label}
                      </Badge>
                      {evidenceBadge(selectedNode.evidence_level)}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setSelectedNodeId(null)}
                    aria-label="Close node detail"
                  >
                    <X className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-gray-300 leading-relaxed">
                  {selectedNode.description}
                </p>

                {/* Related Conditions */}
                <div>
                  <h5 className="text-[11px] text-gray-500 uppercase tracking-wide mb-1.5">
                    Related Conditions
                  </h5>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedNode.related_conditions.map((rc, i) => (
                      <Badge
                        key={i}
                        variant="outline"
                        className="text-[10px] text-gray-300 border-gray-700"
                      >
                        {rc}
                      </Badge>
                    ))}
                  </div>
                </div>

                {/* Connected edges */}
                {connectedEdges.length > 0 && (
                  <div>
                    <h5 className="text-[11px] text-gray-500 uppercase tracking-wide mb-1.5">
                      Connections ({connectedEdges.length})
                    </h5>
                    <div className="space-y-1.5">
                      {connectedEdges.map((edge) => {
                        const other = graph.nodes.find(
                          (n) =>
                            n.id ===
                            (edge.source === selectedNode.id
                              ? edge.target
                              : edge.source)
                        );
                        return (
                          <button
                            key={edge.id}
                            className="w-full flex items-center gap-2 p-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-gray-600/50 transition-colors text-left"
                            onClick={() => {
                              setSelectedEdgeId(edge.id);
                              setSelectedNodeId(null);
                            }}
                          >
                            <Link2 className="w-3 h-3 text-gray-500 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <p className="text-[11px] text-gray-300 truncate">
                                {edge.relationship}
                              </p>
                              <p className="text-[10px] text-gray-500 truncate">
                                {other?.label ?? "Unknown"}
                              </p>
                            </div>
                            <span className="text-[10px] text-gray-500 flex-shrink-0">
                              {(edge.strength * 100).toFixed(0)}%
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : selectedEdge ? (
            /* Edge Detail */
            <Card className="dark:bg-gray-900 dark:border-gray-800">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-sm dark:text-gray-100 flex items-center gap-2">
                    <Link2 className="w-4 h-4 text-cyan-400" />
                    Relationship Detail
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setSelectedEdgeId(null)}
                    aria-label="Close edge detail"
                  >
                    <X className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Source -> Target */}
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-gray-200">
                    {graph.nodes.find((n) => n.id === selectedEdge.source)?.label}
                  </span>
                  <ArrowRight className="w-4 h-4 text-gray-500" />
                  <span className="font-medium text-gray-200">
                    {graph.nodes.find((n) => n.id === selectedEdge.target)?.label}
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Type</span>
                    <span className="text-gray-200">{selectedEdge.relationship}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Strength</span>
                    <span className="text-gray-200">
                      {(selectedEdge.strength * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Evidence</span>
                    {evidenceBadge(selectedEdge.evidence_level)}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Direction</span>
                    <span className="text-gray-200">
                      {selectedEdge.bidirectional ? "Bidirectional" : "Unidirectional"}
                    </span>
                  </div>
                </div>

                {/* Citations */}
                {selectedEdge.citations.length > 0 && (
                  <div>
                    <h5 className="text-[11px] text-gray-500 uppercase tracking-wide mb-1.5">
                      Citations ({selectedEdge.citations.length})
                    </h5>
                    <div className="space-y-2">
                      {selectedEdge.citations.map((cite) => (
                        <div
                          key={cite.id}
                          className="p-2 rounded-lg bg-gray-800/50 border border-gray-700/50"
                        >
                          <p className="text-[11px] text-gray-200 font-medium leading-snug">
                            {cite.title}
                          </p>
                          <p className="text-[10px] text-gray-400 mt-0.5">
                            {cite.authors} - {cite.journal} ({cite.year})
                          </p>
                          {cite.doi && (
                            <p className="text-[10px] text-cyan-500 mt-0.5 font-mono">
                              DOI: {cite.doi}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            /* Empty state */
            <Card className="dark:bg-gray-900 dark:border-gray-800">
              <CardContent className="py-12 text-center">
                <BrainCircuit className="w-8 h-8 text-gray-600 mx-auto mb-3" />
                <p className="text-sm text-gray-400">
                  Click a node or edge to view details
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {graph.nodes.length} conditions, {graph.edges.length} relationships
                </p>
              </CardContent>
            </Card>
          )}

          {/* Quick Stats */}
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="p-4">
              <div className="grid grid-cols-2 gap-3 text-center">
                <div>
                  <p className="text-lg font-bold text-gray-100">{graph.nodes.length}</p>
                  <p className="text-[10px] text-gray-500 uppercase">Conditions</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-100">{graph.edges.length}</p>
                  <p className="text-[10px] text-gray-500 uppercase">Relationships</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-100">
                    {graph.edges.reduce((sum, e) => sum + e.citations.length, 0)}
                  </p>
                  <p className="text-[10px] text-gray-500 uppercase">Citations</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-100">
                    {graph.nodes.filter((n) => n.evidence_level === "strong").length}
                  </p>
                  <p className="text-[10px] text-gray-500 uppercase">Strong Evidence</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── Citation Requirements Panel ───────────────────── */}
      {showCitations && (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
              <Shield className="w-4 h-4 text-cyan-400" />
              Citation Requirements
            </CardTitle>
            <CardDescription>
              Standards for scientific claims in the knowledge graph
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {graph.citation_requirements.map((req, i) => (
                <div
                  key={i}
                  className="p-4 rounded-xl bg-gray-800/40 border border-gray-700/50 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium text-sm text-gray-100">
                      {req.claim_type}
                    </h4>
                    <Badge variant="outline" className="text-[10px] text-gray-300 border-gray-600">
                      Min {req.minimum_citations} citation{req.minimum_citations > 1 ? "s" : ""}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-400">{req.description}</p>
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="w-3 h-3 text-gray-500" />
                    <span className="text-[10px] text-gray-500">
                      Required level: {req.required_evidence_level}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Footer ───────────────────────────────────────── */}
      <div className="text-center py-2">
        <p className="text-xs text-gray-600">
          Last updated: {new Date(graph.last_updated).toLocaleDateString()} | Data sourced from peer-reviewed literature
        </p>
      </div>
    </div>
  );
}
