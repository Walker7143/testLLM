# testLLM

Detect whether an LLM API provider is actually serving the model it claims.

Some API proxies or resellers advertise access to expensive models (e.g. GPT-4o) while secretly routing requests to cheaper alternatives. **testLLM** runs a suite of probes against the target API — testing behavioral, metadata, and capability signals — then aggregates the results into a weighted verdict.

## How It Works

testLLM runs 11 detection probes, each producing a confidence score (0–1) that the claimed model is being served. Results are aggregated with configurable weights into a final verdict:

| Verdict | Meaning |
|---------|---------|
| LIKELY CORRECT | High confidence the claimed model is real |
| UNCERTAIN | Mixed signals, needs manual review |
| HIGH RISK | Strong evidence the provider is NOT serving the claimed model |

### Probes

| Probe | Weight | What It Tests |
|-------|--------|---------------|
| `system_prompt_leak` | 0.35 | Extracts real model identity from system prompt via Responses API |
| `logprobs` | 0.25 | Analyzes token probability distributions (model-specific) |
| `reasoning` | 0.20 | Tests math, logic, and coding against known answers |
| `context_window` | 0.20 | Binary search to estimate actual context window (expensive) |
| `knowledge_cutoff` | 0.15 | Boundary knowledge questions against reference data |
| `multimodal` | 0.10 | Vision/audio capability checks |
| `special_triggers` | 0.10 | Known model-specific behavioral triggers |
| `self_report` | 0.10 | Asks the model to identify itself (easily spoofed) |
| `api_metadata` | 0.05 | Checks `model` field in API responses |
| `api_models` | 0.05 | Queries `/models` endpoint |
| `style_fingerprint` | 0.05 | Analyzes output formatting patterns |

## Requirements

- Python 3.10+
- `httpx`
- `pyyaml`
- `rich`

## Install

```bash
pip install httpx pyyaml rich
```

## Usage

```bash
# Basic usage
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o

# Test a proxy
python detect.py --base-url https://proxy.example.com/v1 --api-key sk-xxx --model gpt-4o

# Run specific probes only
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o \
  --probes self_report,api_metadata,reasoning

# Skip expensive probes (e.g. context_window)
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o \
  --skip-expensive

# Force wire protocol (default: auto-detect)
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o \
  --wire-api chat_completions

# List available reference models
python detect.py --list-models
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--base-url` | API endpoint URL | (required) |
| `--api-key` | API key for authentication | (required) |
| `--model` | Claimed model name (e.g. `gpt-4o`) | (required) |
| `--probes` | Comma-separated probe names to run | all |
| `--skip-expensive` | Skip expensive probes like `context_window` | off |
| `--timeout` | API timeout in seconds | 60 |
| `--wire-api` | Force `chat_completions` or `responses` | auto-detect |
| `--list-models` | List reference models and exit | - |

## Project Structure

```
detect.py                    # CLI entry point
client.py                    # Async HTTP client (httpx)
config.py                    # Configuration & probe weights
scoring.py                   # Weighted aggregation & verdict logic
report.py                    # Rich terminal output
probes/
  base.py                    # BaseProbe abstract class & registry
  self_report.py             # Model self-identification
  api_metadata.py            # API response metadata check
  api_models.py              # /models endpoint probe
  system_prompt_leak.py      # System prompt extraction
  knowledge_cutoff.py        # Knowledge boundary questions
  reasoning.py               # Math/logic/coding tests
  style_fingerprint.py       # Output format analysis
  context_window.py          # Context window estimation
  logprobs.py                # Token probability analysis
  multimodal.py              # Vision/audio capability test
  special_triggers.py        # Model-specific triggers
reference/
  loader.py                  # YAML reference file loader
  models/
    gpt-4o.yaml              # GPT-4o reference profile
    gpt-5.5.yaml             # GPT-5.5 reference profile
```

## Adding Reference Models

Create a YAML file in `reference/models/` (e.g. `claude-3-opus.yaml`):

```yaml
knowledge_cutoff: "2024-04"
reasoning:
  - prompt: "What is 17 * 23?"
    expected: "391"
context_window:
  expected_tokens: 200000
style:
  code_fence: "```"
  uses_headers: true
multimodal:
  vision: true
  audio: false
```

## Adding Probes

1. Create a new file in `probes/` (e.g. `my_probe.py`).
2. Define a class extending `BaseProbe`, implement `async def run(self, client, config) -> ProbeResult`.
3. Decorate with `@register_probe`.
4. Add the import to `probes/__init__.py`.

## License

MIT
