from __future__ import annotations

from probes.base import BaseProbe, ProbeResult, register_probe


SENTINEL = "Remember this secret code: PURPLE-ELEPHANT-42"
QUESTION = "What was the secret code I asked you to remember? Answer with only the code."


@register_probe
class ContextWindowProbe(BaseProbe):
    name = "context_window"
    description = "Estimate context window size via binary search"
    default_weight = 0.20
    expensive = True

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        expected_tokens = reference.get("context_window", {}).get("max_tokens", 128000)
        if not expected_tokens:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["No context_window in reference data"],
            )

        # Binary search for approximate context window
        # Use word count as proxy (roughly 1.3 tokens per word for English)
        low, high = 500, int(expected_tokens * 1.5 / 1.3)
        evidence = []

        while high - low > 500:
            mid = (low + high) // 2
            padding = "The quick brown fox jumps over the lazy dog. " * (mid // 10)

            messages = [
                {
                    "role": "user",
                    "content": f"{SENTINEL}\n\n{padding}\n\n{QUESTION}",
                }
            ]

            try:
                resp = await client.chat(messages=messages, max_tokens=50)
                if "PURPLE-ELEPHANT-42" in resp.content or "purple-elephant-42" in resp.content.lower():
                    low = mid
                else:
                    high = mid
            except Exception as e:
                # API error likely means input too long
                high = mid
                evidence.append(f"API error at ~{mid} words: {type(e).__name__}")

        estimated_words = low
        estimated_tokens = int(estimated_words * 1.3)
        evidence.append(f"Estimated context: ~{estimated_tokens:,} tokens (~{estimated_words:,} words)")
        evidence.append(f"Expected: {expected_tokens:,} tokens")

        ratio = estimated_tokens / expected_tokens if expected_tokens > 0 else 0
        if ratio >= 0.9:
            score = 1.0
        elif ratio >= 0.5:
            score = 0.5 + (ratio - 0.5) * 1.0  # linear scale 0.5->0.5, 0.9->1.0
        else:
            score = max(0.0, ratio)

        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=0.7,
            evidence=evidence,
            raw_data={
                "estimated_tokens": estimated_tokens,
                "expected_tokens": expected_tokens,
                "ratio": ratio,
            },
        )
