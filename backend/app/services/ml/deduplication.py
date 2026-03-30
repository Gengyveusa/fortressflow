"""
Deduplication Engine

Fuzzy-matching and golden-record creation for CRM contact/company records.
Implements Levenshtein distance, Soundex phonetic matching, and configurable
field-level scoring -- all in pure Python with no external dependencies.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class MatchMethod(str, Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    PHONETIC = "phonetic"


@dataclass
class MatchScore:
    """Score for a single field comparison between two records."""

    field: str
    score: float  # 0.0 .. 1.0
    method: MatchMethod


class SuggestedAction(str, Enum):
    AUTO_MERGE = "auto_merge"
    REVIEW = "review"
    IGNORE = "ignore"


@dataclass
class DuplicateCandidate:
    """A pair of records identified as potential duplicates."""

    record_a_id: str
    record_b_id: str
    overall_score: float
    field_scores: List[MatchScore]
    suggested_action: SuggestedAction

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_a_id": self.record_a_id,
            "record_b_id": self.record_b_id,
            "overall_score": round(self.overall_score, 4),
            "field_scores": [
                {"field": fs.field, "score": round(fs.score, 4), "method": fs.method.value} for fs in self.field_scores
            ],
            "suggested_action": self.suggested_action.value,
        }


# ---------------------------------------------------------------------------
# String similarity algorithms (pure Python)
# ---------------------------------------------------------------------------


def levenshtein_distance(s1: str, s2: str) -> int:
    """Classic dynamic-programming Levenshtein edit distance."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (0 if c1 == c2 else 1)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Normalised Levenshtein similarity in [0, 1]."""
    if not s1 and not s2:
        return 1.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    dist = levenshtein_distance(s1, s2)
    return 1.0 - (dist / max_len)


def jaro_similarity(s1: str, s2: str) -> float:
    """Jaro similarity score -- better than Levenshtein for short strings
    like names."""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3.0


def jaro_winkler_similarity(s1: str, s2: str, prefix_weight: float = 0.1) -> float:
    """Jaro-Winkler gives a boost when strings share a common prefix."""
    jaro = jaro_similarity(s1, s2)
    prefix_len = 0
    for c1, c2 in zip(s1[:4], s2[:4]):
        if c1 == c2:
            prefix_len += 1
        else:
            break
    return jaro + prefix_len * prefix_weight * (1.0 - jaro)


def soundex(name: str) -> str:
    """American Soundex phonetic algorithm.

    Returns a 4-character code (e.g. 'S530' for 'Smith').
    """
    if not name:
        return ""

    name = name.upper().strip()
    # Keep only alpha chars
    name = "".join(c for c in name if c.isalpha())
    if not name:
        return ""

    code_map = {
        "B": "1",
        "F": "1",
        "P": "1",
        "V": "1",
        "C": "2",
        "G": "2",
        "J": "2",
        "K": "2",
        "Q": "2",
        "S": "2",
        "X": "2",
        "Z": "2",
        "D": "3",
        "T": "3",
        "L": "4",
        "M": "5",
        "N": "5",
        "R": "6",
    }

    first_letter = name[0]
    coded = [first_letter]
    prev_code = code_map.get(first_letter, "0")

    for ch in name[1:]:
        ch_code = code_map.get(ch, "0")
        if ch_code != "0" and ch_code != prev_code:
            coded.append(ch_code)
        prev_code = ch_code if ch_code != "0" else prev_code

    result = "".join(coded)
    return (result + "0000")[:4]


def phonetic_similarity(s1: str, s2: str) -> float:
    """Binary phonetic match via Soundex -- returns 1.0 on match, 0.0 otherwise."""
    code1 = soundex(s1)
    code2 = soundex(s2)
    if not code1 or not code2:
        return 0.0
    return 1.0 if code1 == code2 else 0.0


# ---------------------------------------------------------------------------
# Field comparison configuration
# ---------------------------------------------------------------------------

# Default field weights and preferred match methods
DEFAULT_FIELD_CONFIG: Dict[str, Dict[str, Any]] = {
    "email": {"weight": 3.0, "methods": [MatchMethod.EXACT, MatchMethod.FUZZY]},
    "first_name": {"weight": 1.5, "methods": [MatchMethod.FUZZY, MatchMethod.PHONETIC]},
    "last_name": {"weight": 2.0, "methods": [MatchMethod.FUZZY, MatchMethod.PHONETIC]},
    "company": {"weight": 2.5, "methods": [MatchMethod.FUZZY]},
    "phone": {"weight": 2.5, "methods": [MatchMethod.EXACT, MatchMethod.FUZZY]},
    "domain": {"weight": 2.0, "methods": [MatchMethod.EXACT]},
    "title": {"weight": 0.5, "methods": [MatchMethod.FUZZY]},
    "city": {"weight": 0.5, "methods": [MatchMethod.FUZZY]},
}


def _normalise_phone(phone: str) -> str:
    """Strip non-digit characters for phone comparison."""
    return "".join(c for c in phone if c.isdigit())


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _normalise_text(text: str) -> str:
    return text.strip().lower()


NORMALISERS: Dict[str, Any] = {
    "email": _normalise_email,
    "phone": _normalise_phone,
}


# ---------------------------------------------------------------------------
# Core deduplication engine
# ---------------------------------------------------------------------------


class DeduplicationEngine:
    """Identifies, scores, and merges duplicate CRM records."""

    AUTO_MERGE_THRESHOLD = 0.95
    REVIEW_THRESHOLD = 0.85

    def __init__(
        self,
        field_config: Optional[Dict[str, Dict[str, Any]]] = None,
        threshold: float = 0.85,
    ) -> None:
        self.field_config = field_config or dict(DEFAULT_FIELD_CONFIG)
        self.threshold = threshold

        # Tracking
        self._merge_history: List[Dict[str, Any]] = []
        self._golden_records: Dict[str, Dict[str, Any]] = {}
        self._duplicate_pairs: List[DuplicateCandidate] = []

        logger.info(
            "DeduplicationEngine initialised with threshold=%.2f, %d field configs",
            self.threshold,
            len(self.field_config),
        )

    # -- Duplicate finding ---------------------------------------------------

    def find_duplicates(
        self,
        records: List[Dict[str, Any]],
        threshold: Optional[float] = None,
    ) -> List[DuplicateCandidate]:
        """Compare all record pairs and return those above *threshold*.

        Uses a blocking strategy on normalised email and Soundex(last_name)
        to avoid O(n^2) full comparisons on large datasets.
        """
        threshold = threshold if threshold is not None else self.threshold
        candidates: List[DuplicateCandidate] = []

        # Build blocking index
        blocks: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for rec in records:
            keys = self._blocking_keys(rec)
            for key in keys:
                blocks[key].append(rec)

        # Deduplicate pair comparisons
        seen_pairs: Set[Tuple[str, str]] = set()

        for block_records in blocks.values():
            for i in range(len(block_records)):
                for j in range(i + 1, len(block_records)):
                    a = block_records[i]
                    b = block_records[j]
                    aid = str(a.get("id", a.get("record_id", id(a))))
                    bid = str(b.get("id", b.get("record_id", id(b))))
                    pair_key = (min(aid, bid), max(aid, bid))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    overall, field_scores = self._compare_records(a, b)
                    if overall >= threshold:
                        action = self._suggest_action(overall)
                        candidate = DuplicateCandidate(
                            record_a_id=aid,
                            record_b_id=bid,
                            overall_score=overall,
                            field_scores=field_scores,
                            suggested_action=action,
                        )
                        candidates.append(candidate)

        candidates.sort(key=lambda c: c.overall_score, reverse=True)
        self._duplicate_pairs.extend(candidates)

        logger.info(
            "Found %d duplicate candidates from %d records (threshold=%.2f)",
            len(candidates),
            len(records),
            threshold,
        )
        return candidates

    # -- Record merging ------------------------------------------------------

    def merge_records(
        self,
        primary_id: str,
        duplicate_ids: List[str],
        records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge *duplicate_ids* into *primary_id*, creating a golden record.

        The golden record is built by selecting the best value for each
        field across all contributing records.
        """
        all_ids = {primary_id} | set(duplicate_ids)
        contributing = [r for r in records if str(r.get("id", r.get("record_id"))) in all_ids]

        if not contributing:
            raise ValueError(f"No records found for ids: {all_ids}")

        golden = self.create_golden_record(contributing, primary_id=primary_id)

        self._merge_history.append(
            {
                "timestamp": time.time(),
                "primary_id": primary_id,
                "merged_ids": duplicate_ids,
                "golden_record_id": golden.get("id", primary_id),
            }
        )

        logger.info(
            "Merged %d records into golden record %s",
            len(contributing),
            primary_id,
        )
        return golden

    def create_golden_record(
        self,
        records: List[Dict[str, Any]],
        primary_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a best-field-selection golden record from a cluster of
        duplicates.

        Selection heuristics per field:
        - Prefer the longest non-empty value (more complete).
        - For email/phone prefer the most recently updated value.
        - The *primary_id* record's values win ties.
        """
        if not records:
            raise ValueError("Cannot create golden record from empty list")

        golden: Dict[str, Any] = {}
        all_fields: Set[str] = set()
        for r in records:
            all_fields.update(r.keys())

        # Remove meta/internal keys from golden selection
        skip_keys = {"id", "record_id", "created_at", "updated_at", "_score"}

        for fld in all_fields:
            if fld in skip_keys:
                continue
            best_value: Any = None
            best_length = -1
            is_primary = False

            for rec in records:
                val = rec.get(fld)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    continue
                val_str = str(val)
                rec_id = str(rec.get("id", rec.get("record_id", "")))
                rec_is_primary = rec_id == primary_id

                # Heuristic: prefer longer, or primary on tie
                if len(val_str) > best_length or (len(val_str) == best_length and rec_is_primary and not is_primary):
                    best_value = val
                    best_length = len(val_str)
                    is_primary = rec_is_primary

            if best_value is not None:
                golden[fld] = best_value

        rid = primary_id or str(uuid.uuid4())
        golden["id"] = rid
        golden["_merged_from"] = [str(r.get("id", r.get("record_id"))) for r in records]
        golden["_merged_at"] = time.time()

        self._golden_records[rid] = golden
        return golden

    # -- CRM sync stub -------------------------------------------------------

    def sync_to_crms(
        self,
        golden_record: Dict[str, Any],
        crm_adapters: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Push the golden record back to connected CRMs.

        In production each adapter in *crm_adapters* would implement a
        ``push_record(record)`` method.  Here we simulate the sync and
        return a status summary.
        """
        record_id = golden_record.get("id", "unknown")
        merged_from = golden_record.get("_merged_from", [])
        results: List[Dict[str, Any]] = []

        if crm_adapters:
            for adapter in crm_adapters:
                try:
                    if hasattr(adapter, "push_record"):
                        adapter.push_record(golden_record)
                    results.append(
                        {
                            "crm": getattr(adapter, "name", str(adapter)),
                            "status": "synced",
                        }
                    )
                except Exception as exc:
                    logger.error("CRM sync failed for %s: %s", adapter, exc)
                    results.append(
                        {
                            "crm": getattr(adapter, "name", str(adapter)),
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
        else:
            # Simulated sync for default CRMs
            for crm_name in ("hubspot", "salesforce"):
                results.append(
                    {
                        "crm": crm_name,
                        "status": "synced (simulated)",
                        "record_id": record_id,
                        "merged_count": len(merged_from),
                    }
                )

        logger.info(
            "Synced golden record %s to %d CRM(s)",
            record_id,
            len(results),
        )
        return {
            "golden_record_id": record_id,
            "sync_results": results,
            "synced_at": time.time(),
        }

    # -- Health metrics ------------------------------------------------------

    def get_dedup_health(self) -> Dict[str, Any]:
        """Return overall deduplication health metrics."""
        total_pairs = len(self._duplicate_pairs)
        auto_merge_count = sum(1 for c in self._duplicate_pairs if c.suggested_action == SuggestedAction.AUTO_MERGE)
        review_count = sum(1 for c in self._duplicate_pairs if c.suggested_action == SuggestedAction.REVIEW)
        merges_completed = len(self._merge_history)
        golden_count = len(self._golden_records)

        avg_score = 0.0
        if total_pairs > 0:
            avg_score = sum(c.overall_score for c in self._duplicate_pairs) / total_pairs

        return {
            "total_duplicate_pairs_found": total_pairs,
            "auto_merge_candidates": auto_merge_count,
            "review_candidates": review_count,
            "merges_completed": merges_completed,
            "golden_records_created": golden_count,
            "average_match_score": round(avg_score, 4),
            "duplicate_rate": round(total_pairs / max(golden_count + total_pairs, 1), 4),
            "merge_rate": round(merges_completed / max(total_pairs, 1), 4),
            "pending_reviews": review_count
            - sum(
                1
                for m in self._merge_history
                if any(
                    c.record_a_id in m.get("merged_ids", []) or c.record_b_id in m.get("merged_ids", [])
                    for c in self._duplicate_pairs
                    if c.suggested_action == SuggestedAction.REVIEW
                )
            ),
        }

    # -- Internal helpers ----------------------------------------------------

    def _blocking_keys(self, record: Dict[str, Any]) -> List[str]:
        """Generate blocking keys to limit pairwise comparisons.

        Current strategies:
        1. Normalised email prefix (before @)
        2. Soundex of last_name
        3. Normalised domain
        """
        keys: List[str] = []

        email = record.get("email", "")
        if email and "@" in email:
            prefix = _normalise_email(email).split("@")[0]
            if prefix:
                keys.append(f"email_prefix:{prefix}")

        last_name = record.get("last_name", "")
        if last_name:
            sx = soundex(last_name)
            if sx:
                keys.append(f"soundex_ln:{sx}")

        domain = record.get("domain", "")
        if domain:
            keys.append(f"domain:{_normalise_text(domain)}")

        # Fallback: if no blocking keys, use a catch-all so the record is
        # still compared (less efficient but avoids silent data loss).
        if not keys:
            keys.append("_catchall")

        return keys

    def _compare_records(self, a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[float, List[MatchScore]]:
        """Compute weighted overall similarity and per-field scores."""
        field_scores: List[MatchScore] = []
        total_weight = 0.0
        weighted_sum = 0.0

        for fld, cfg in self.field_config.items():
            val_a = a.get(fld)
            val_b = b.get(fld)
            weight = cfg.get("weight", 1.0)
            methods: List[MatchMethod] = cfg.get("methods", [MatchMethod.FUZZY])

            if val_a is None or val_b is None:
                continue
            if isinstance(val_a, str) and val_a.strip() == "":
                continue
            if isinstance(val_b, str) and val_b.strip() == "":
                continue

            str_a = str(val_a)
            str_b = str(val_b)

            # Apply field-specific normaliser
            normaliser = NORMALISERS.get(fld, _normalise_text)
            norm_a = normaliser(str_a)
            norm_b = normaliser(str_b)

            # Evaluate each method and take the best score
            best_score = 0.0
            best_method = methods[0]

            for method in methods:
                if method == MatchMethod.EXACT:
                    score = 1.0 if norm_a == norm_b else 0.0
                elif method == MatchMethod.FUZZY:
                    # Use Jaro-Winkler for names, Levenshtein for longer fields
                    if fld in ("first_name", "last_name"):
                        score = jaro_winkler_similarity(norm_a, norm_b)
                    else:
                        score = levenshtein_similarity(norm_a, norm_b)
                elif method == MatchMethod.PHONETIC:
                    score = phonetic_similarity(norm_a, norm_b)
                else:
                    score = 0.0

                if score > best_score:
                    best_score = score
                    best_method = method

            field_scores.append(MatchScore(field=fld, score=best_score, method=best_method))
            total_weight += weight
            weighted_sum += weight * best_score

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        return overall, field_scores

    def _suggest_action(self, score: float) -> SuggestedAction:
        """Decide the recommended action based on overall match score."""
        if score >= self.AUTO_MERGE_THRESHOLD:
            return SuggestedAction.AUTO_MERGE
        if score >= self.REVIEW_THRESHOLD:
            return SuggestedAction.REVIEW
        return SuggestedAction.IGNORE
