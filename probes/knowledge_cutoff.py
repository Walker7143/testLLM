from __future__ import annotations

import re

from probes.base import BaseProbe, ProbeResult, register_probe


@register_probe
class KnowledgeCutoffProbe(BaseProbe):
    name = "knowledge_cutoff"
    description = "Test knowledge cutoff date with boundary questions"
    default_weight = 0.25

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        questions = reference.get("knowledge_cutoff", {}).get("boundary_questions", [])
        if not questions:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["No boundary questions in reference data"],
            )

        correct = 0
        total = len(questions)
        evidence = []

        for q in questions:
            resp = await client.chat(
                messages=[
                    {"role": "system", "content": "Answer concisely with factual information only."},
                    {"role": "user", "content": q["question"]},
                ],
                max_tokens=200,
            )
            answer = resp.content.lower()
            expected = q["expected_contains"].lower()

            # Check with simple contains first, then regex
            if expected in answer:
                correct += 1
                evidence.append(f"[pass] {q['question'][:60]}...")
            else:
                try:
                    if re.search(expected, answer):
                        correct += 1
                        evidence.append(f"[pass] {q['question'][:60]}...")
                    else:
                        evidence.append(f"[fail] {q['question'][:60]}... (expected '{expected}')")
                except re.error:
                    evidence.append(f"[fail] {q['question'][:60]}... (expected '{expected}')")

        score = correct / total if total > 0 else 0.0
        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=0.8,
            evidence=[f"{correct}/{total} correct"] + evidence,
            raw_data={"correct": correct, "total": total},
        )
