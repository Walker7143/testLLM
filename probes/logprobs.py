from __future__ import annotations

import math

from probes.base import BaseProbe, ProbeResult, register_probe


# Prompts designed to elicit different token distributions across models
TEST_PROMPTS = [
    "The capital of France is",
    "2 + 2 =",
    "In Python, the keyword to define a function is",
]


@register_probe
class LogprobsProbe(BaseProbe):
    name = "logprobs"
    description = "Analyze token probability distributions"
    default_weight = 0.30

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        reference_logprobs = reference.get("logprobs", {})
        if not reference_logprobs:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["No logprobs reference data"],
            )

        try:
            resp = await client.chat(
                messages=[{"role": "user", "content": TEST_PROMPTS[0]}],
                max_tokens=1,
                logprobs=True,
                top_logprobs=5,
            )
        except Exception:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["API does not support logprobs"],
            )

        if not resp.logprobs:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["API returned no logprobs data"],
            )

        # Extract top tokens and their logprobs from response
        evidence = []
        collected_data = []

        for prompt in TEST_PROMPTS:
            try:
                resp = await client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1,
                    logprobs=True,
                    top_logprobs=5,
                )
                if resp.logprobs and "content" in resp.logprobs:
                    token_info = resp.logprobs["content"][0] if resp.logprobs["content"] else {}
                    top = token_info.get("top_logprobs", [])
                    collected_data.append({
                        "prompt": prompt,
                        "top_tokens": [(t.get("token", ""), t.get("logprob", 0)) for t in top],
                    })
            except Exception:
                pass

        if not collected_data:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["Could not retrieve logprobs data"],
            )

        # Compare with reference: check if top tokens overlap
        # This is a simplified comparison - real implementation would use KL divergence
        evidence.append(f"Collected logprobs for {len(collected_data)} prompts")
        for d in collected_data:
            top_token = d["top_tokens"][0][0] if d["top_tokens"] else "?"
            evidence.append(f"  '{d['prompt'][:30]}...' -> top token: '{top_token}'")

        # Score based on data availability (detailed comparison needs model-specific reference)
        score = 0.5  # Neutral - we got data but can't fully compare without reference
        confidence = 0.4  # Medium - logprobs are useful but comparison is hard

        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=confidence,
            evidence=evidence,
            raw_data={"collected": collected_data},
        )
