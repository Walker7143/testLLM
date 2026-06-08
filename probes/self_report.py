from __future__ import annotations

import re

from probes.base import BaseProbe, ProbeResult, register_probe


@register_probe
class SelfReportProbe(BaseProbe):
    name = "self_report"
    description = "Ask the model to identify itself"
    default_weight = 0.1

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        resp = await client.chat(
            messages=[
                {"role": "user", "content": "What exact model are you? Answer with only the model name, nothing else."},
            ],
            max_tokens=50,
        )
        answer = resp.content.strip().lower()
        claimed = claimed_model.lower()
        evidence = []

        # Normalize for comparison
        def normalize(s: str) -> str:
            return re.sub(r"[^a-z0-9]", "", s)

        answer_norm = normalize(answer)
        claimed_norm = normalize(claimed)

        if claimed_norm in answer_norm or answer_norm in claimed_norm:
            score = 1.0
            evidence.append(f"Self-reported: '{resp.content.strip()}'")
        elif any(word in answer for word in claimed.split("-")):
            score = 0.5
            evidence.append(f"Partial match: '{resp.content.strip()}'")
        else:
            score = 0.0
            evidence.append(f"Self-reported: '{resp.content.strip()}' (does not match '{claimed_model}')")

        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=0.3,  # Low confidence - easily spoofable
            evidence=evidence,
            raw_data={"response": resp.content},
        )
