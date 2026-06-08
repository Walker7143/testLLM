from __future__ import annotations

import re

from probes.base import BaseProbe, ProbeResult, register_probe


PROMPTS = [
    "Explain how a transformer neural network works in 3 paragraphs.",
    "Write a Python function to sort a list using merge sort.",
    "What are the key differences between TCP and UDP?",
]


@register_probe
class StyleFingerprintProbe(BaseProbe):
    name = "style_fingerprint"
    description = "Analyze output style: formatting, length, verbosity"
    default_weight = 0.10

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        style_ref = reference.get("style", {})
        if not style_ref:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["No style reference data"],
            )

        features: list[float] = []
        evidence = []

        for prompt in PROMPTS:
            resp = await client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            text = resp.content

            # Feature 1: uses markdown headers?
            has_headers = bool(re.search(r"^#{1,3}\s", text, re.MULTILINE))
            # Feature 2: uses code fences?
            has_code_fence = "```" in text
            # Feature 3: uses numbered lists?
            has_numbered = bool(re.search(r"^\d+\.", text, re.MULTILINE))
            # Feature 4: average line length
            lines = [l for l in text.split("\n") if l.strip()]
            avg_line_len = sum(len(l) for l in lines) / max(len(lines), 1)
            # Feature 5: total length
            total_len = len(text)

            features.extend([
                float(has_headers),
                float(has_code_fence),
                float(has_numbered),
                min(avg_line_len / 100.0, 1.0),
                min(total_len / 2000.0, 1.0),
            ])

        # Compare with reference
        expected_headers = style_ref.get("uses_headers", True)
        expected_code = style_ref.get("code_block_fence", "```") == "```"
        expected_lists = style_ref.get("numbered_lists", True)

        # Simple matching: check if formatting patterns match
        matches = 0
        checks = 0
        if expected_headers:
            checks += 1
            if any(f > 0 for f in features[::5]):  # header features
                matches += 1
        if expected_code:
            checks += 1
            if any(f > 0 for f in features[1::5]):  # code fence features
                matches += 1
        if expected_lists:
            checks += 1
            if any(f > 0 for f in features[2::5]):  # numbered list features
                matches += 1

        score = matches / max(checks, 1)

        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=0.5,
            evidence=evidence or [f"Style match: {matches}/{checks} features"],
            raw_data={"features": features, "matches": matches, "checks": checks},
        )
