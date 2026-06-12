"""Explainer module - Template-based NL generation per design doc §6.3."""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from codedna.harvester.features import VECTOR_DIMS

@dataclass
class Pattern:
    name: str
    description: str
    confidence: float

@dataclass
class Change:
    feature: str
    direction: str
    magnitude: float

@dataclass
class ExplanationResult:
    summary: str
    patterns: List[Pattern]
    changes: List[Change]
    dna_score: Optional[float] = None

class Explainer:
    SUMMARY_TEMPLATES = {
        "very_high": ["Highly consistent with your established coding patterns."],
        "high": ["Consistent with your established patterns."],
        "medium": ["Moderately consistent with your patterns."],
        "low": ["Some deviation from your typical patterns."],
        "very_low": ["Significant deviation from your established patterns."],
    }

    def explain(self, partial_vector: Optional[List[float]], baseline_vector: Optional[List[float]] = None,
                dna_score: Optional[float] = None, verbosity: str = "normal") -> Dict[str, Any]:
        patterns, changes = [], []
        if partial_vector and len(partial_vector) == VECTOR_DIMS:
            patterns = self._detect_patterns(partial_vector)
            if baseline_vector and len(baseline_vector) == VECTOR_DIMS:
                changes = self._detect_changes(partial_vector, baseline_vector)
        score = dna_score if dna_score is not None else self._estimate_score(partial_vector, baseline_vector)
        summary = self._generate_summary(score)
        if verbosity == "brief":
            patterns, changes = patterns[:2], changes[:2]
        elif verbosity == "normal":
            patterns, changes = patterns[:5], changes[:3]
        return {"summary": summary,
                "patterns": [{"name": p.name, "description": p.description, "confidence": p.confidence} for p in patterns],
                "changes": [{"feature": c.feature, "direction": c.direction, "magnitude": c.magnitude} for c in changes]}

    def _detect_patterns(self, vector: List[float]) -> List[Pattern]:
        patterns = []
        if vector[6] > 0.5: patterns.append(Pattern("Comprehension-heavy style", "Favors list/dict comprehensions", min(1.0, vector[6])))
        if vector[4] > 3.0: patterns.append(Pattern("Deeply nested code", "Uses deeply nested control structures", min(1.0, vector[4] / 5)))
        if vector[12] > 0.7: patterns.append(Pattern("Well-documented", "Includes comprehensive docstrings", vector[12]))
        if vector[21] > 0.5: patterns.append(Pattern("Type-annotated", "Uses type hints extensively", vector[21]))
        return patterns

    def _detect_changes(self, current: List[float], baseline: List[float]) -> List[Change]:
        changes = []
        names = ["snake_case naming", "single-char variables", "abbreviations", "function length", "nesting depth",
                 "class usage", "comprehension usage", "lambda usage", "decorator usage"]
        for i, (curr, base) in enumerate(zip(current, baseline)):
            diff = curr - base
            if abs(diff) > 0.15 and i < len(names):
                changes.append(Change(names[i], "increased" if diff > 0 else "decreased", abs(diff)))
        return changes

    def _estimate_score(self, partial: Optional[List[float]], baseline: Optional[List[float]]) -> Optional[float]:
        if partial is None:
            return None
        if baseline and len(partial) == len(baseline):
            import math
            dot = sum(a * b for a, b in zip(partial, baseline))
            mag1 = math.sqrt(sum(a * a for a in partial))
            mag2 = math.sqrt(sum(b * b for b in baseline))
            if mag1 > 0 and mag2 > 0:
                return round(dot / (mag1 * mag2), 2)
        return None

    def _generate_summary(self, score: Optional[float]) -> str:
        if score is None:
            return "Unable to generate summary without baseline comparison."
        category = "very_high" if score >= 0.9 else "high" if score >= 0.75 else "medium" if score >= 0.5 else "low" if score >= 0.3 else "very_low"
        import random
        return random.choice(self.SUMMARY_TEMPLATES[category])
