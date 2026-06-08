from __future__ import annotations

from probes.base import ProbeResult

# Probes that can definitively prove model identity mismatch
IDENTITY_PROBES = {"system_prompt_leak"}


def aggregate(results: list[ProbeResult], weights: dict[str, float]) -> tuple[float, str | None]:
    """Returns (score, warning_or_None).

    If an identity probe finds a definitive mismatch (score=0, high confidence),
    it overrides the weighted average.
    """
    weighted_sum = 0.0
    total_weight = 0.0
    succeeded = 0
    failed = 0
    identity_mismatch: str | None = None

    for r in results:
        # Check for identity probe mismatch
        if r.probe_name in IDENTITY_PROBES and r.score == 0.0 and r.confidence >= 0.7:
            for e in r.evidence:
                if "MISMATCH" in e:
                    identity_mismatch = e
                    break

        w = weights.get(r.probe_name, 1.0) * r.confidence
        if r.confidence > 0:
            weighted_sum += r.score * w
            total_weight += w
            succeeded += 1
        else:
            failed += 1

    score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Identity mismatch is definitive - override score
    if identity_mismatch:
        score = min(score, 0.30)

    warning = None
    total = succeeded + failed
    if total > 0 and failed / total > 0.5:
        warning = (
            f"Only {succeeded}/{total} probes succeeded. "
            f"Result may be unreliable - check API connectivity."
        )

    return score, warning


def verdict(score: float) -> tuple[str, str]:
    if score >= 0.80:
        return "LIKELY CORRECT", "green"
    if score >= 0.50:
        return "UNCERTAIN", "yellow"
    return "HIGH RISK - Likely NOT serving claimed model", "red"
