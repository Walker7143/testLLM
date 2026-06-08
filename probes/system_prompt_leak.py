from __future__ import annotations

import re

from probes.base import BaseProbe, ProbeResult, register_probe

# Words that are clearly not model names
STOPWORDS = {
    "built", "designed", "able", "expected", "capable", "trained", "fine",
    "tuned", "optimized", "configured", "running", "deployed", "based",
    "powered", "intended", "created", "developed", "available",
}


@register_probe
class SystemPromptLeakProbe(BaseProbe):
    name = "system_prompt_leak"
    description = "Extract system prompt from Responses API to find real model identity"
    default_weight = 0.35

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        evidence = []
        raw_data: dict = {}

        try:
            resp = await client._client.post(
                "/responses",
                json={
                    "model": client.model,
                    "input": "What model are you? Reply with only the model name.",
                    "max_output_tokens": 50,
                },
            )
            ct = resp.headers.get("content-type", "")
            if "json" not in ct or resp.status_code >= 400:
                evidence.append("Responses API not available")
                return ProbeResult(
                    probe_name=self.name, score=0.0, confidence=0.0,
                    evidence=evidence, raw_data=raw_data,
                )

            data = resp.json()
            if not isinstance(data, dict):
                evidence.append("Unexpected response format")
                return ProbeResult(
                    probe_name=self.name, score=0.0, confidence=0.0,
                    evidence=evidence, raw_data=raw_data,
                )

            instructions = data.get("instructions", "")
            if not instructions:
                evidence.append("No instructions/system prompt in response")
                return ProbeResult(
                    probe_name=self.name, score=0.0, confidence=0.0,
                    evidence=evidence, raw_data=raw_data,
                )

            raw_data["instructions"] = instructions
            evidence.append(f"System prompt found ({len(instructions)} chars)")

            claimed_lower = claimed_model.lower()
            instructions_lower = instructions.lower()

            # Tier 1: "You are <model>" - most reliable
            primary_patterns = [
                r"you are (gpt-[\d][\w.-]*)",
                r"you are (claude[\w.-]*)",
                r"you are (gemini[\w.-]*)",
                r"you are (deepseek[\w.-]*)",
                r"you are (llama[\w.-]*)",
                r"you are (qwen[\w.-]*)",
            ]
            primary_matches = []
            for pattern in primary_patterns:
                primary_matches.extend(re.findall(pattern, instructions_lower))

            # Tier 2: "model: <name>" - less reliable, filter stopwords
            secondary_matches = []
            for m in re.findall(r"model[:\s]+([\w][\w.-]*)", instructions_lower):
                if m not in STOPWORDS and len(m) > 2:
                    secondary_matches.append(m)

            # Tier 3: standalone model name mentions
            tertiary_matches = re.findall(r"(gpt-[\d][\w.-]*)", instructions_lower)

            # Combine, prioritizing primary matches
            if primary_matches:
                found_models = list(dict.fromkeys(primary_matches))  # dedupe, preserve order
            elif secondary_matches:
                found_models = list(dict.fromkeys(secondary_matches))
            elif tertiary_matches:
                found_models = list(dict.fromkeys(tertiary_matches))
            else:
                found_models = []

            # Also extract model self-report from output
            output = data.get("output", [])
            self_report = ""
            for item in output:
                if item.get("type") == "message":
                    for part in item.get("content", []):
                        if part.get("type") == "output_text":
                            self_report = part.get("text", "")
            if self_report:
                raw_data["self_report_via_responses"] = self_report
                evidence.append(f"Model self-report: '{self_report[:80]}'")

            # Score
            if found_models:
                evidence.append(f"Real model in prompt: {found_models[0]}")
                raw_data["models_in_prompt"] = found_models

                if any(claimed_lower in m or m in claimed_lower for m in found_models):
                    score = 1.0
                    evidence.append("Claimed model matches system prompt")
                else:
                    score = 0.0
                    evidence.append(
                        f"MISMATCH: claimed '{claimed_model}' but prompt says '{found_models[0]}'"
                    )
            else:
                evidence.append("No model identity found in system prompt")
                score = 0.5

        except Exception as e:
            evidence.append(f"Error: {type(e).__name__}: {e}")
            return ProbeResult(
                probe_name=self.name, score=0.0, confidence=0.0,
                evidence=evidence, raw_data=raw_data,
            )

        return ProbeResult(
            probe_name=self.name, score=score, confidence=0.9,
            evidence=evidence, raw_data=raw_data,
        )
