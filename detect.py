#!/usr/bin/env python3
"""testLLM - Detect if an LLM API provider serves the model it claims."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from client import LLMClient, WireAPI
from config import Config, ProbeWeight
from probes import get_all_probes
from probes.base import ProbeResult
from reference.loader import load_reference, list_available_models
from report import print_report
from scoring import aggregate


async def check_connectivity(client: LLMClient) -> bool:
    """Quick check if the API is reachable."""
    try:
        resp = await client._client.get("/models")
        ct = resp.headers.get("content-type", "")
        if "json" not in ct:
            print(f"[error] API at {client.base_url} returned non-JSON (content-type: {ct})")
            print("        The URL may be wrong. Try adding /v1 to your --base-url.")
            return False
        return True
    except Exception as e:
        print(f"[error] Cannot reach API at {client.base_url}: {type(e).__name__}: {e}")
        return False


async def run_detection(config: Config) -> tuple[list[ProbeResult], float, str | None]:
    wire_api = None
    if config.wire_api:
        wire_api = WireAPI(config.wire_api)

    client = LLMClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.claimed_model,
        timeout=config.timeout,
        wire_api=wire_api,
    )

    print(f"Resolved base URL: {client.base_url}")
    print(f"Wire API: {client._wire_api.value if client._wire_api else 'auto-detecting...'}")

    if not await check_connectivity(client):
        await client.close()
        return [], 0.0

    reference = load_reference(config.claimed_model, config.reference_dir)
    if not reference:
        print(f"[warn] No reference data for '{config.claimed_model}', probes needing reference data will be limited")

    all_probes = get_all_probes()
    enabled = [
        cls()
        for name, cls in all_probes.items()
        if config.is_probe_enabled(name)
    ]

    print(f"Running {len(enabled)} probes against {client.base_url} (model: {config.claimed_model})...")
    print()

    results: list[ProbeResult] = []
    for probe in enabled:
        print(f"  [{probe.name}] running...", end="", flush=True)
        try:
            result = await probe.run(client, config.claimed_model, reference)
            results.append(result)
            print(f" score={result.score:.2f}")
        except Exception as e:
            print(f" error: {type(e).__name__}: {e}")
            results.append(ProbeResult(
                probe_name=probe.name,
                score=0.0,
                confidence=0.0,
                evidence=[f"Error: {type(e).__name__}: {e}"],
            ))

    await client.close()

    weights = {name: config.get_weight(name) for name in all_probes}
    final_score, warning = aggregate(results, weights)

    return results, final_score, warning


def main():
    parser = argparse.ArgumentParser(
        description="Detect if an LLM API provider serves the model it claims.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", help="API endpoint URL (e.g. https://proxy.example.com/v1)")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--model", help="Claimed model name (e.g. gpt-4o)")
    parser.add_argument("--probes", default=None, help="Comma-separated probe names to run")
    parser.add_argument("--skip-expensive", action="store_true", help="Skip expensive probes (context_window)")
    parser.add_argument("--timeout", type=float, default=60.0, help="API timeout in seconds")
    parser.add_argument("--wire-api", choices=["chat_completions", "responses"], default=None,
                        help="API format: chat_completions (default OpenAI) or responses (newer). Auto-detects if not set.")
    parser.add_argument("--list-models", action="store_true", help="List available reference models and exit")

    args = parser.parse_args()

    if args.list_models:
        models = list_available_models()
        if models:
            print("Available reference models:")
            for m in models:
                print(f"  - {m}")
        else:
            print("No reference models found.")
        return

    if not args.base_url or not args.api_key or not args.model:
        parser.error("--base-url, --api-key, and --model are required for scanning")

    config = Config(
        base_url=args.base_url,
        api_key=args.api_key,
        claimed_model=args.model,
        wire_api=args.wire_api,
        skip_expensive=args.skip_expensive,
        probes_filter=args.probes.split(",") if args.probes else None,
        timeout=args.timeout,
    )

    results, final_score, warning = asyncio.run(run_detection(config))
    if results:
        print()
        print_report(config.base_url, config.claimed_model, results, final_score, warning)
    else:
        print("\nNo results - check your API connection.")


if __name__ == "__main__":
    main()
