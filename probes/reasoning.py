from __future__ import annotations

import re

from probes.base import BaseProbe, ProbeResult, register_probe


@register_probe
class ReasoningProbe(BaseProbe):
    name = "reasoning"
    description = "Test math, logic, and coding capabilities"
    default_weight = 0.25

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        reasoning = reference.get("reasoning", {})
        tasks: list[tuple[str, str]] = []  # (prompt, expected_pattern)

        for item in reasoning.get("math", []):
            tasks.append((item["prompt"], item.get("expected", item.get("expected_contains", ""))))
        for item in reasoning.get("logic", []):
            tasks.append((item["prompt"], item.get("expected_contains", item.get("expected", ""))))
        for item in reasoning.get("coding", []):
            tasks.append((item["prompt"], item.get("expected_contains", item.get("expected", ""))))

        if not tasks:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["No reasoning tasks in reference data"],
            )

        correct = 0
        total = len(tasks)
        evidence = []

        for prompt, expected in tasks:
            resp = await client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            answer = resp.content

            # Try exact match first, then regex
            if expected in answer:
                correct += 1
                evidence.append(f"[pass] {prompt[:50]}...")
            else:
                try:
                    if re.search(expected, answer, re.IGNORECASE):
                        correct += 1
                        evidence.append(f"[pass] {prompt[:50]}... (regex match)")
                    else:
                        evidence.append(f"[fail] {prompt[:50]}... (expected '{expected[:30]}')")
                except re.error:
                    # Invalid regex - just use substring match
                    if expected.lower() in answer.lower():
                        correct += 1
                        evidence.append(f"[pass] {prompt[:50]}... (substring fallback)")
                    else:
                        evidence.append(f"[fail] {prompt[:50]}... (expected '{expected[:30]}')")

        score = correct / total if total > 0 else 0.0
        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=0.85,
            evidence=[f"{correct}/{total} correct"] + evidence,
            raw_data={"correct": correct, "total": total},
        )
