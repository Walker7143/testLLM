from __future__ import annotations

from probes.base import BaseProbe, ProbeResult, register_probe


@register_probe
class ApiMetadataProbe(BaseProbe):
    name = "api_metadata"
    description = "Check if API response metadata leaks the real model name"
    default_weight = 0.2

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        resp = await client.chat(
            messages=[{"role": "user", "content": "Say hello."}],
            max_tokens=10,
        )
        returned_model = resp.model
        evidence = []
        score = 1.0

        if not returned_model:
            evidence.append("No 'model' field in API response")
            score = 0.5
        elif returned_model == claimed_model:
            evidence.append(f"Response model field matches: '{returned_model}'")
            score = 1.0
        else:
            evidence.append(
                f"Response model field says '{returned_model}', expected '{claimed_model}'"
            )
            # Partial match (e.g., gpt-4o vs gpt-4o-2024-08-06)
            if claimed_model in returned_model or returned_model in claimed_model:
                evidence.append("Partial match - likely a versioned variant")
                score = 0.7
            else:
                score = 0.0

        # Check for system_fingerprint
        fingerprint = resp.raw_response.get("system_fingerprint")
        if fingerprint:
            evidence.append(f"system_fingerprint: {fingerprint}")

        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=0.9,
            evidence=evidence,
            raw_data={"returned_model": returned_model, "raw": resp.raw_response},
        )
