from __future__ import annotations

from probes.base import BaseProbe, ProbeResult, register_probe


@register_probe
class ApiModelsProbe(BaseProbe):
    name = "api_models"
    description = "Check what models the API actually lists"
    default_weight = 0.15

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        import httpx

        try:
            # Call /models endpoint directly
            url = f"{client.base_url}/models"
            resp = await client._client.get("/models")
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return ProbeResult(
                    probe_name=self.name,
                    score=0.0,
                    confidence=0.0,
                    evidence=["Models endpoint returned non-JSON response"],
                )

            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            evidence = [f"API lists {len(models)} models: {', '.join(sorted(models))}"]

            # Check if claimed model appears in the list
            if claimed_model in models:
                score = 1.0
                evidence.append(f"'{claimed_model}' found in model list")
            elif any(claimed_model in m for m in models):
                match = next(m for m in models if claimed_model in m)
                score = 0.8
                evidence.append(f"Partial match: '{match}' found")
            else:
                score = 0.0
                evidence.append(f"'{claimed_model}' NOT found in model list")

            return ProbeResult(
                probe_name=self.name,
                score=score,
                confidence=0.7,
                evidence=evidence,
                raw_data={"models": models},
            )

        except Exception as e:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=[f"Error listing models: {type(e).__name__}: {e}"],
            )
