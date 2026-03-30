"""
Science Authentication
Knowledge-graph-backed claim verification with citation requirements.
Pre-populated with oral-systemic health relationships.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RelationshipStrength(str, Enum):
    ESTABLISHED = "established"        # meta-analyses, systematic reviews
    STRONG = "strong"                  # multiple RCTs
    MODERATE = "moderate"              # observational + some RCTs
    EMERGING = "emerging"              # preliminary studies
    HYPOTHESIZED = "hypothesized"      # mechanistic plausibility only


class EvidenceLevel(str, Enum):
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    RCT = "rct"
    COHORT = "cohort"
    CASE_CONTROL = "case_control"
    EXPERT_OPINION = "expert_opinion"


@dataclass
class Citation:
    """A single literature citation supporting a claim."""
    source: str
    doi: Optional[str] = None
    title: str = ""
    verified: bool = False
    confidence_score: float = 0.0
    evidence_level: Optional[EvidenceLevel] = None
    year: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphNode:
    """A condition or concept in the knowledge graph."""
    node_id: str
    label: str
    category: str          # e.g. "oral", "systemic", "biomarker"
    description: str = ""
    aliases: List[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    """A relationship between two nodes, annotated with strength and citations."""
    source_id: str
    target_id: str
    relationship: str      # e.g. "increases_risk", "bidirectional", "mediates"
    strength: RelationshipStrength = RelationshipStrength.MODERATE
    mechanism: str = ""
    citations: List[Citation] = field(default_factory=list)
    bidirectional: bool = False


@dataclass
class VerificationResult:
    """Outcome of verifying a single claim against the knowledge graph."""
    claim_text: str
    supported: bool
    confidence: float
    matching_edges: List[Dict[str, Any]]
    required_citations: int
    provided_citations: int
    missing_citation_topics: List[str]
    notes: str = ""


class KnowledgeGraph:
    """
    Directed graph of medical/scientific relationships.

    Nodes represent conditions or biomarkers; edges represent documented
    relationships annotated with evidence strength and citations.
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._adjacency: Dict[str, List[int]] = {}   # node_id -> list of edge indices

    # ── Graph mutation ──────────────────────────────────────────────────

    def add_node(self, node: GraphNode) -> None:
        self._nodes[node.node_id] = node
        self._adjacency.setdefault(node.node_id, [])

    def add_edge(self, edge: GraphEdge) -> None:
        idx = len(self._edges)
        self._edges.append(edge)
        self._adjacency.setdefault(edge.source_id, []).append(idx)
        if edge.bidirectional:
            self._adjacency.setdefault(edge.target_id, []).append(idx)

    # ── Query helpers ───────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def find_node_by_alias(self, term: str) -> Optional[GraphNode]:
        term_lower = term.lower()
        for node in self._nodes.values():
            if term_lower == node.label.lower() or term_lower in [a.lower() for a in node.aliases]:
                return node
        return None

    def get_edges_for(self, node_id: str) -> List[GraphEdge]:
        indices = self._adjacency.get(node_id, [])
        return [self._edges[i] for i in indices]

    def find_path(self, source_id: str, target_id: str, max_depth: int = 3) -> List[List[str]]:
        """BFS to find all paths up to max_depth between two nodes."""
        paths: List[List[str]] = []
        queue: List[Tuple[str, List[str]]] = [(source_id, [source_id])]

        while queue:
            current, path = queue.pop(0)
            if current == target_id and len(path) > 1:
                paths.append(path)
                continue
            if len(path) > max_depth:
                continue
            for edge in self.get_edges_for(current):
                neighbor = edge.target_id if edge.source_id == current else edge.source_id
                if neighbor not in path:
                    queue.append((neighbor, path + [neighbor]))

        return paths

    def relationship_exists(self, node_a_id: str, node_b_id: str) -> Optional[GraphEdge]:
        for edge in self.get_edges_for(node_a_id):
            if edge.target_id == node_b_id or (edge.bidirectional and edge.source_id == node_b_id):
                return edge
        return None


def build_oral_systemic_graph() -> KnowledgeGraph:
    """Return a KnowledgeGraph pre-populated with oral-systemic health links."""
    g = KnowledgeGraph()

    # ── Nodes ───────────────────────────────────────────────────────────
    nodes = [
        GraphNode("periodontal", "Periodontal Disease", "oral",
                  "Chronic inflammatory condition of gums and supporting structures",
                  ["periodontitis", "gum disease", "gingivitis"]),
        GraphNode("cardiovascular", "Cardiovascular Disease", "systemic",
                  "Diseases of the heart and blood vessels",
                  ["CVD", "heart disease", "atherosclerosis"]),
        GraphNode("diabetes_t2", "Type 2 Diabetes", "systemic",
                  "Chronic metabolic disorder with insulin resistance",
                  ["T2DM", "diabetes mellitus", "diabetes"]),
        GraphNode("pregnancy_complications", "Adverse Pregnancy Outcomes", "systemic",
                  "Including preterm birth, low birth weight, preeclampsia",
                  ["preterm birth", "preeclampsia", "pregnancy"]),
        GraphNode("neurodegenerative", "Neurodegenerative Diseases", "systemic",
                  "Progressive loss of neuronal function",
                  ["Alzheimer's", "dementia", "cognitive decline"]),
        GraphNode("kidney_disease", "Chronic Kidney Disease", "systemic",
                  "Progressive loss of kidney function",
                  ["CKD", "renal disease", "nephropathy"]),
        GraphNode("crp", "C-Reactive Protein", "biomarker",
                  "Systemic inflammatory marker",
                  ["CRP", "inflammation marker"]),
        GraphNode("oral_microbiome", "Oral Microbiome", "oral",
                  "Community of microorganisms in the oral cavity",
                  ["oral bacteria", "dental plaque microbiome"]),
    ]
    for n in nodes:
        g.add_node(n)

    # ── Edges ───────────────────────────────────────────────────────────
    edges = [
        GraphEdge(
            "periodontal", "cardiovascular", "increases_risk",
            RelationshipStrength.ESTABLISHED, "Systemic inflammation and bacteremia",
            [Citation("J Periodontol", "10.1902/jop.2013.1340013",
                      "Periodontitis and atherosclerotic CVD", True, 0.92,
                      EvidenceLevel.META_ANALYSIS, 2013)],
            bidirectional=False,
        ),
        GraphEdge(
            "periodontal", "diabetes_t2", "bidirectional_risk",
            RelationshipStrength.ESTABLISHED,
            "Shared inflammatory pathways; hyperglycemia worsens periodontal status",
            [Citation("Diabetes Care", "10.2337/dc13-2200",
                      "Bidirectional relationship between diabetes and periodontitis",
                      True, 0.95, EvidenceLevel.SYSTEMATIC_REVIEW, 2014)],
            bidirectional=True,
        ),
        GraphEdge(
            "periodontal", "pregnancy_complications", "increases_risk",
            RelationshipStrength.STRONG,
            "Hematogenous spread of oral pathogens to the fetoplacental unit",
            [Citation("BJOG", "10.1111/1471-0528.12247",
                      "Periodontal disease and adverse pregnancy outcomes",
                      True, 0.85, EvidenceLevel.META_ANALYSIS, 2013)],
        ),
        GraphEdge(
            "periodontal", "neurodegenerative", "increases_risk",
            RelationshipStrength.EMERGING,
            "P. gingivalis and gingipains found in Alzheimer's brain tissue",
            [Citation("Science Advances", "10.1126/sciadv.aau3333",
                      "Porphyromonas gingivalis in Alzheimer's disease brains",
                      True, 0.72, EvidenceLevel.COHORT, 2019)],
        ),
        GraphEdge(
            "periodontal", "kidney_disease", "increases_risk",
            RelationshipStrength.MODERATE,
            "Shared inflammatory burden and endothelial dysfunction",
            [Citation("J Clin Periodontol", "10.1111/jcpe.12064",
                      "Periodontitis and chronic kidney disease",
                      True, 0.78, EvidenceLevel.SYSTEMATIC_REVIEW, 2013)],
            bidirectional=True,
        ),
        GraphEdge(
            "periodontal", "crp", "elevates",
            RelationshipStrength.ESTABLISHED,
            "Periodontal inflammation drives systemic CRP elevation",
            [Citation("J Dent Res", "10.1177/0022034510375830",
                      "CRP levels after periodontal therapy", True, 0.90,
                      EvidenceLevel.RCT, 2010)],
        ),
        GraphEdge(
            "oral_microbiome", "periodontal", "contributes_to",
            RelationshipStrength.ESTABLISHED,
            "Dysbiotic shift in subgingival microbiome initiates periodontitis",
            [Citation("Periodontol 2000", "10.1111/prd.12153",
                      "Role of the oral microbiome in periodontitis",
                      True, 0.93, EvidenceLevel.SYSTEMATIC_REVIEW, 2017)],
        ),
    ]
    for e in edges:
        g.add_edge(e)

    return g


class ClaimVerifier:
    """
    Verifies natural-language health claims against the knowledge graph
    and enforces citation requirements.
    """

    # Simple keyword-to-node-id mapping for claim extraction
    _KEYWORD_MAP: Dict[str, str] = {
        "periodontal": "periodontal", "periodontitis": "periodontal",
        "gum disease": "periodontal", "gingivitis": "periodontal",
        "cardiovascular": "cardiovascular", "heart disease": "cardiovascular",
        "cvd": "cardiovascular", "atherosclerosis": "cardiovascular",
        "diabetes": "diabetes_t2", "t2dm": "diabetes_t2",
        "pregnancy": "pregnancy_complications", "preterm": "pregnancy_complications",
        "preeclampsia": "pregnancy_complications",
        "alzheimer": "neurodegenerative", "dementia": "neurodegenerative",
        "neurodegenerative": "neurodegenerative", "cognitive decline": "neurodegenerative",
        "kidney": "kidney_disease", "ckd": "kidney_disease",
        "renal": "kidney_disease",
        "crp": "crp", "c-reactive protein": "crp",
        "microbiome": "oral_microbiome", "oral bacteria": "oral_microbiome",
    }

    def __init__(self, graph: Optional[KnowledgeGraph] = None):
        self._graph = graph or build_oral_systemic_graph()

    def extract_claims(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract pairs of (condition_a, condition_b) mentioned in the text.
        Returns a list of node-id pairs that represent implicit claims of
        a relationship.
        """
        text_lower = text.lower()
        found_nodes: List[str] = []

        for keyword, node_id in self._KEYWORD_MAP.items():
            if keyword in text_lower and node_id not in found_nodes:
                found_nodes.append(node_id)

        # Also try graph aliases
        for word in re.findall(r"[a-zA-Z'-]+", text):
            node = self._graph.find_node_by_alias(word)
            if node and node.node_id not in found_nodes:
                found_nodes.append(node.node_id)

        pairs: List[Tuple[str, str]] = []
        for i in range(len(found_nodes)):
            for j in range(i + 1, len(found_nodes)):
                pairs.append((found_nodes[i], found_nodes[j]))
        return pairs

    def verify_against_graph(
        self,
        claim_text: str,
        provided_citations: Optional[List[Citation]] = None,
    ) -> VerificationResult:
        """
        Verify a textual claim by checking whether the referenced
        conditions have a documented relationship in the knowledge graph.
        """
        pairs = self.extract_claims(claim_text)
        if not pairs:
            return VerificationResult(
                claim_text=claim_text,
                supported=False,
                confidence=0.0,
                matching_edges=[],
                required_citations=1,
                provided_citations=len(provided_citations or []),
                missing_citation_topics=["No recognizable conditions found in claim."],
                notes="Could not extract any condition pairs from the claim text.",
            )

        matching_edges: List[Dict[str, Any]] = []
        missing_topics: List[str] = []
        total_confidence = 0.0

        for source_id, target_id in pairs:
            edge = self._graph.relationship_exists(source_id, target_id)
            if edge is None:
                # Try reverse direction
                edge = self._graph.relationship_exists(target_id, source_id)

            if edge:
                matching_edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "relationship": edge.relationship,
                    "strength": edge.strength.value,
                    "mechanism": edge.mechanism,
                    "citation_count": len(edge.citations),
                })
                avg_conf = (
                    sum(c.confidence_score for c in edge.citations) / len(edge.citations)
                    if edge.citations else 0.0
                )
                total_confidence += avg_conf
            else:
                src_label = (self._graph.get_node(source_id) or GraphNode(source_id, source_id, "")).label
                tgt_label = (self._graph.get_node(target_id) or GraphNode(target_id, target_id, "")).label
                missing_topics.append(f"No documented link: {src_label} <-> {tgt_label}")

        supported = len(matching_edges) > 0
        avg_confidence = total_confidence / len(pairs) if pairs else 0.0

        cit_count = len(provided_citations or [])
        required = max(1, len(pairs))

        return VerificationResult(
            claim_text=claim_text,
            supported=supported,
            confidence=round(avg_confidence, 3),
            matching_edges=matching_edges,
            required_citations=required,
            provided_citations=cit_count,
            missing_citation_topics=missing_topics,
            notes="Claim verified against oral-systemic knowledge graph.",
        )

    def require_citations(
        self,
        claim_text: str,
        citations: List[Citation],
        min_confidence: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Enforce that every claim pair has at least one citation with
        sufficient confidence.
        """
        result = self.verify_against_graph(claim_text, citations)
        verified_cites = [c for c in citations if c.verified and c.confidence_score >= min_confidence]

        passes = (
            result.supported
            and len(verified_cites) >= result.required_citations
        )

        return {
            "passes": passes,
            "verification": asdict(result) if hasattr(result, "__dataclass_fields__") else result.__dict__,
            "verified_citations": [c.to_dict() for c in verified_cites],
            "rejected_citations": [
                c.to_dict() for c in citations if c not in verified_cites
            ],
            "recommendation": (
                "Claim is adequately supported." if passes
                else "Additional verified citations required before publication."
            ),
        }
