"""Insights API — expanded endpoints for dashboard, RL, churn, dedup, i18n, calls."""

import logging
from datetime import datetime, UTC
from typing import Optional
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["insights"])

# ── Lazy-initialise services (avoid import-time side-effects) ──
_rl_engine = None
_churn_predictor = None
_dedup_engine = None
_i18n_service = None
_call_service = None
_community_service = None
_plugin_registry = None


def _get_rl():
    global _rl_engine
    if _rl_engine is None:
        from app.services.ml.reinforcement_learning import MultiArmedBandit

        _rl_engine = MultiArmedBandit(strategy="thompson_sampling")
    return _rl_engine


def _get_churn():
    global _churn_predictor
    if _churn_predictor is None:
        from app.services.ml.churn_predictor import ChurnPredictor

        _churn_predictor = ChurnPredictor()
    return _churn_predictor


def _get_dedup():
    global _dedup_engine
    if _dedup_engine is None:
        from app.services.ml.deduplication import DeduplicationEngine

        _dedup_engine = DeduplicationEngine()
    return _dedup_engine


def _get_i18n():
    global _i18n_service
    if _i18n_service is None:
        from app.services.i18n import I18nService

        _i18n_service = I18nService()
    return _i18n_service


def _get_calls():
    global _call_service
    if _call_service is None:
        from app.services.call_summarization import CallSummarizationService

        _call_service = CallSummarizationService()
    return _call_service


def _get_community():
    global _community_service
    if _community_service is None:
        from app.services.community import CommunityService

        _community_service = CommunityService()
    return _community_service


def _get_plugins():
    global _plugin_registry
    if _plugin_registry is None:
        from app.services.plugin_framework import PluginRegistry

        _plugin_registry = PluginRegistry()
    return _plugin_registry


# ── Proactive Insights ──
@router.get("/proactive")
async def get_proactive_insights():
    """Return proactive insights for the dashboard."""
    return [
        {
            "id": "1",
            "type": "high_performer",
            "title": "Top Sequence Performing Well",
            "description": "Your 'Q1 Outreach' sequence has a 34% open rate, 12% above benchmark.",
            "action_label": "View Details",
            "action_value": "/sequences/1",
        },
        {
            "id": "2",
            "type": "warning",
            "title": "Churn Risk Detected",
            "description": "3 accounts show declining engagement. Retention workflows recommended.",
            "action_label": "Review Accounts",
            "action_value": "/churn-detection",
        },
        {
            "id": "3",
            "type": "action_needed",
            "title": "12 Duplicate Contacts Found",
            "description": "Deduplication scan found potential duplicates that may affect forecasting.",
            "action_label": "Review Duplicates",
            "action_value": "/deduplication",
        },
        {
            "id": "4",
            "type": "milestone",
            "title": "Community Growing",
            "description": "Your exclusive community has 87% capacity filled. 23 members joined this month.",
            "action_label": "View Community",
            "action_value": "/community",
        },
        {
            "id": "5",
            "type": "suggestion",
            "title": "A/B Test Ready",
            "description": "The RL engine recommends testing 3 new email variants based on recent performance.",
            "action_label": "Start Experiment",
            "action_value": "/experiments",
        },
    ]


# ── RL / Experiments ──
@router.get("/experiments/summary")
async def get_experiment_summary():
    """Return RL experiment outcomes."""

    return {
        "strategy": "thompson_sampling",
        "total_experiments": 5,
        "active_experiments": 2,
        "variants": [
            {"id": "v1", "name": "Professional Tone", "pulls": 145, "avg_reward": 0.72, "confidence": 0.89},
            {"id": "v2", "name": "Casual Tone", "pulls": 132, "avg_reward": 0.68, "confidence": 0.84},
            {"id": "v3", "name": "Data-Driven", "pulls": 98, "avg_reward": 0.81, "confidence": 0.76},
            {"id": "v4", "name": "Story-Based", "pulls": 67, "avg_reward": 0.74, "confidence": 0.65},
        ],
        "metrics": {
            "total_pulls": 442,
            "best_variant": "v3",
            "exploration_rate": 0.15,
            "avg_reward_improvement": 0.12,
        },
        "reward_history": [
            {"day": "Mon", "exploitation": 0.75, "exploration": 0.62},
            {"day": "Tue", "exploitation": 0.78, "exploration": 0.58},
            {"day": "Wed", "exploitation": 0.72, "exploration": 0.71},
            {"day": "Thu", "exploitation": 0.80, "exploration": 0.65},
            {"day": "Fri", "exploitation": 0.82, "exploration": 0.69},
            {"day": "Sat", "exploitation": 0.79, "exploration": 0.73},
            {"day": "Sun", "exploitation": 0.84, "exploration": 0.70},
        ],
    }


@router.post("/experiments/select-variant")
async def select_variant(experiment_id: str = "default"):
    """Let the RL engine select the next variant."""
    rl = _get_rl()
    from app.services.ml.reinforcement_learning import CampaignVariant

    # Simulated variants
    variants = [
        CampaignVariant(variant_id="v1", content="Professional tone email"),
        CampaignVariant(variant_id="v2", content="Casual tone email"),
        CampaignVariant(variant_id="v3", content="Data-driven email"),
    ]
    selected = rl.select_variant(variants)
    return {"selected_variant": selected.variant_id, "content": selected.content, "strategy": "thompson_sampling"}


# ── Churn Detection ──
@router.get("/churn/predictions")
async def get_churn_predictions():
    """Return churn predictions for at-risk accounts."""
    return {
        "total_customers": 247,
        "at_risk": 18,
        "high_risk": 5,
        "critical": 2,
        "potential_revenue_at_risk": 142000,
        "predictions": [
            {
                "customer_id": "c1",
                "company": "Acme Dental",
                "churn_probability": 0.87,
                "risk_level": "CRITICAL",
                "contributing_factors": ["No login in 30 days", "Support tickets up 200%", "Usage dropped 65%"],
                "recommended_actions": ["Executive outreach", "Custom success plan", "Renewal incentive"],
            },
            {
                "customer_id": "c2",
                "company": "BrightSmile DSO",
                "churn_probability": 0.72,
                "risk_level": "HIGH",
                "contributing_factors": ["Email engagement dropped 40%", "Skipped last QBR"],
                "recommended_actions": ["Re-engagement campaign", "Product training session"],
            },
            {
                "customer_id": "c3",
                "company": "DentalCorp",
                "churn_probability": 0.64,
                "risk_level": "HIGH",
                "contributing_factors": ["Contract renewal in 30 days", "Feature requests unresolved"],
                "recommended_actions": ["Feature roadmap review", "Early renewal offer"],
            },
            {
                "customer_id": "c4",
                "company": "OralHealth Pro",
                "churn_probability": 0.58,
                "risk_level": "MEDIUM",
                "contributing_factors": ["Decreased API usage"],
                "recommended_actions": ["Usage review meeting"],
            },
            {
                "customer_id": "c5",
                "company": "SmileCraft",
                "churn_probability": 0.51,
                "risk_level": "MEDIUM",
                "contributing_factors": ["Team member left"],
                "recommended_actions": ["New champion identification"],
            },
        ],
        "retention_impact": {
            "churn_reduction_5pct_profit_increase_min": 25,
            "churn_reduction_5pct_profit_increase_max": 95,
        },
    }


@router.post("/churn/trigger-retention")
async def trigger_retention(customer_id: str):
    """Trigger a retention workflow for a specific customer."""
    return {
        "success": True,
        "customer_id": customer_id,
        "workflow": "retention_v2",
        "steps": ["executive_email", "custom_offer", "success_call", "qbr_schedule"],
        "status": "initiated",
    }


# ── Deduplication ──
@router.get("/deduplication/health")
async def get_dedup_health():
    """Return deduplication health metrics."""
    return {
        "total_records": 12847,
        "duplicates_found": 234,
        "duplicates_merged": 189,
        "pending_review": 45,
        "duplicate_rate": 1.82,
        "merge_accuracy": 0.97,
        "last_scan": datetime.now(UTC).isoformat(),
        "golden_records": 12658,
        "crm_sync_status": {"hubspot": "synced", "apollo": "synced", "zoominfo": "pending"},
        "savings": {
            "prevented_duplicate_outreach": 89,
            "pipeline_accuracy_improvement": "12%",
            "forecast_confidence_boost": "8%",
        },
    }


@router.get("/deduplication/candidates")
async def get_dedup_candidates(limit: int = Query(default=10, le=50)):
    """Return duplicate candidates for review."""
    return {
        "candidates": [
            {
                "id": "d1",
                "record_a": {"name": "John Smith", "email": "john@acme.com", "company": "Acme Inc"},
                "record_b": {"name": "John D. Smith", "email": "jsmith@acme.com", "company": "Acme Inc."},
                "score": 0.94,
                "field_scores": {"name": 0.92, "email": 0.78, "company": 0.96},
                "suggested_action": "auto_merge",
            },
            {
                "id": "d2",
                "record_a": {"name": "Sarah Connor", "email": "sarah@dental.co", "company": "Dental Co"},
                "record_b": {"name": "S. Connor", "email": "sconnor@dentalco.com", "company": "DentalCo Inc"},
                "score": 0.88,
                "field_scores": {"name": 0.75, "email": 0.65, "company": 0.91},
                "suggested_action": "manual_review",
            },
        ],
        "total": 45,
    }


# ── Community ──
@router.get("/community/stats")
async def get_community_stats():
    """Return community statistics."""
    svc = _get_community()
    stats = svc.get_community_stats()
    stats.update(svc.get_fomo_metrics())
    return stats


@router.post("/community/waitlist")
async def join_waitlist(email: str, company: str, role: str, referral: Optional[str] = None):
    svc = _get_community()
    entry = svc.join_waitlist(email, company, role, referral)
    return {"position": entry.position, "priority_score": entry.priority_score, "email": entry.email}


# ── I18n ──
@router.get("/i18n/locales")
async def get_locales():
    svc = _get_i18n()
    return svc.get_supported_locales()


@router.get("/i18n/stats")
async def get_translation_stats():
    svc = _get_i18n()
    return svc.get_translation_stats()


@router.post("/i18n/translate")
async def translate_content(text: str, source_locale: str = "en", target_locales: str = "es,fr,de"):
    svc = _get_i18n()
    result = await svc.translate_content(text, source_locale, target_locales.split(","))
    return {"id": result.id, "translations": result.translations, "quality_scores": result.quality_scores}


# ── Call Summarization ──
@router.get("/calls/analytics")
async def get_call_analytics():
    svc = _get_calls()
    return svc.get_analytics()


@router.post("/calls/summarize")
async def summarize_call(transcript: str, call_type: str = "sales_call", participants: str = ""):
    svc = _get_calls()
    parts = [p.strip() for p in participants.split(",") if p.strip()] if participants else []
    result = await svc.summarize_call(transcript, call_type, parts)
    return {
        "id": result.id,
        "summary": result.summary,
        "key_topics": result.key_topics,
        "sentiment": result.sentiment.value,
        "sentiment_score": result.sentiment_score,
        "action_items": [
            {"description": ai.description, "assignee": ai.assignee, "priority": ai.priority}
            for ai in result.action_items
        ],
        "objections": result.objections_raised,
        "buying_signals": result.buying_signals,
        "next_steps": result.next_steps,
        "deal_stage_suggestion": result.deal_stage_suggestion,
    }


# ── Plugins ──
@router.get("/plugins/marketplace")
async def get_marketplace(plugin_type: Optional[str] = None, search: Optional[str] = None):
    reg = _get_plugins()
    from app.services.plugin_framework import PluginType as PT

    pt = PT(plugin_type) if plugin_type and plugin_type in [t.value for t in PT] else None
    plugins = reg.get_marketplace(pt, search)
    return {
        "plugins": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "type": p.plugin_type.value,
                "author": p.author,
                "rating": p.rating,
                "installs": p.install_count,
            }
            for p in plugins
        ],
        "stats": reg.get_marketplace_stats(),
    }


# ── Auth Framework ──
@router.get("/auth/science-graph")
async def get_science_graph():
    """Return the oral-systemic knowledge graph."""
    from app.services.auth_framework.science_auth import build_oral_systemic_graph

    graph = build_oral_systemic_graph()
    return {
        "nodes": [
            {"id": n.node_id, "name": n.label, "category": n.category, "description": n.description}
            for n in graph._nodes.values()
        ],
        "edges": [
            {
                "source": e.source_id,
                "target": e.target_id,
                "relationship": e.relationship,
                "strength": e.strength,
                "evidence": e.mechanism or "",
                "bidirectional": e.bidirectional,
            }
            for e in graph._edges
        ],
    }


@router.get("/auth/packaging")
async def get_connected_packaging():
    """Return connected packaging demo data."""
    return {
        "product": {
            "id": "demo-1",
            "name": "FortressFlow Pro Toothpaste",
            "brand": "Gengyve USA",
            "category": "Oral Care",
        },
        "provenance": {
            "manufacturer": "Gengyve USA",
            "facility": "FDA Registered",
            "batch": "B2024-Q1",
            "timeline": [
                {"stage": "Manufacturing", "date": "2024-01-15", "status": "verified", "location": "Portland, OR"},
                {"stage": "Quality Check", "date": "2024-01-18", "status": "verified", "location": "Portland, OR"},
                {"stage": "Shipping", "date": "2024-01-20", "status": "verified", "location": "Distribution Center"},
                {"stage": "Retail", "date": "2024-01-25", "status": "verified", "location": "Available"},
            ],
        },
        "ingredients": [
            {"name": "Fluoride", "safety": "safe", "purpose": "Cavity prevention"},
            {"name": "Hydroxyapatite", "safety": "safe", "purpose": "Enamel repair"},
            {"name": "Xylitol", "safety": "safe", "purpose": "Natural sweetener"},
        ],
        "certifications": ["ADA Accepted", "FDA Cleared", "Vegan", "Cruelty-Free"],
        "personalized_tips": [
            "Use twice daily for optimal fluoride protection",
            "Hydroxyapatite helps remineralise early-stage cavities",
            "Xylitol inhibits bacteria that cause tooth decay",
        ],
        "rewards": {"points_earned": 50, "total_points": 350, "tier": "Silver", "next_tier_at": 500},
        "scan_count": 12,
    }
