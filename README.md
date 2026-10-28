# DUPIN WEBINT — Website Intelligence CLI tool, powered by an autonomous AI agent

One target in, a full investigation out: findings, entities and a written report.
No server, no API: just a command-line tool.

[![License: DUPIN Source-Available](https://img.shields.io/badge/license-DUPIN%20Source--Available-blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/)
[![Made by DUPIN](https://img.shields.io/badge/by-DUPIN%20Ciberseguridad-0b1f3a)](https://dupin.com.ar)

> DUPIN WEBINT is released to the community as a gift by [DUPIN Ciberseguridad](https://dupin.com.ar) — the cybersecurity firm (pentesting, red/purple team, incident response). This repo is only the WEBINT CLI tool.
> Source-available: you can read, run and install it, but not modify it. See [LICENSE](LICENSE).

---

## What is DUPIN WEBINT?

DUPIN WEBINT is a website OSINT investigation engine built by DUPIN Ciberseguridad.
Give it a domain, an IP or a `host:port` and it runs a complete, autonomous
investigation:

1. **Deterministic pre-recon (batch):** DNS, certificate transparency, email
   security (SPF/DKIM/DMARC), RDAP, subdomain discovery, Shodan, Wayback, web
   probing, Swagger/GraphQL discovery, JavaScript mining, vendor fingerprinting,
   Docker/Kubernetes exposure, `ffuf` and `nuclei` — all in parallel.
2. **Autonomous AI agent:** your own AI agent (any OpenAI-compatible provider
   and model you configure) receives the pre-recon digest and decides by itself
   what to investigate next, step by step, within a step and time budget. It is
   not a fixed checklist.
3. **Entity harvester:** emails, people and companies are automatically
   extracted from every output and correlated into a graph.
4. **Auto-enrichment:** harvested entities are enriched without the model
   having to ask.
5. **Report:** `findings.jsonl` + `entities.json` + a written `report.md`.

> Results vary between runs: the agent decides its own path, and
> certificate-transparency/Wayback lookups are cached for 24 hours per target.

## Features

- **Autonomous, not scripted** — the AI chooses its own path within budget.
- **Bring your own AI** — any OpenAI-compatible provider works (OpenAI,
  DeepSeek, Groq, Mistral, xAI, OpenRouter, Ollama, vLLM...). The first run
  asks for your key and stores it **locally, outside this repository**.
- **Parallel pre-recon** — dozens of probes batched with rate limiting.
- **60+ secret patterns** — `.env`, keys, tokens and connection strings, with
  automatic redaction before anything reaches the model.
- **Entity graph** — emails, people and companies linked to their sources.
- **Resilient** — checkpoint/resume, cache with TTL, anti-loop and time budgets.
- **Direct connection** — no VPN or network namespace required.

## Requirements

- Python **3.10+**
- Python packages: `requests`, `urllib3`, `pyyaml` (`pip install -r requirements.txt`)
- Optional external tools (used when present): `subfinder`, `nuclei`, `ffuf`,
  `curl`, `dig`, `whois`
- An **AI API key** from any OpenAI-compatible provider
- Optional: a **Shodan API key** and **Hunter.io keys** for extra sources

## Quickstart

```bash
git clone https://github.com/dupinciber/webint.git
cd webint
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 dupin.py example.com --perfil rapido
```

The first time it needs AI, the CLI asks for your key **without echoing it**
and saves it locally in:

```
~/.config/dupinciber/webint.env   (0600, outside the repository)
```

You can also provide it yourself with `DUPIN_AI_API_KEY` in your environment or
in a local `.env` (never committed). To use another provider, set its base URL
and model names (see [`.env.example`](.env.example)):

```bash
export DUPIN_AI_BASE_URL=https://openrouter.ai/api/v1
export DUPIN_AI_MODEL_FLASH=openai/gpt-4o-mini
export DUPIN_AI_MODEL_PRO=anthropic/claude-3.5-sonnet
```

Profiles: `rapido` (~3–5 min), `medio` (~6–9 min), `profundo` (~8–18 min).

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example)):

| Variable | Default | Description |
|---|---|---|
| `DUPIN_AI_API_KEY` | — | AI key (alternate: environment or first-run prompt) |
| `DUPIN_AI_BASE_URL` | `https://api.deepseek.com` | Any OpenAI-compatible base URL |
| `DUPIN_AI_MODEL_FLASH` | `deepseek-v4-flash` | Executor model (agent loop) |
| `DUPIN_AI_MODEL_PRO` | `deepseek-v4-pro` | Analyst/report model |
| `DUPIN_AI_REASONING_EFFORT` | auto | Reasoning effort (DeepSeek `high`; others opt-in) |
| `DUPIN_INSECURE_TLS` | `0` | Disable TLS verification (local/self-signed providers only) |
| `DUPIN_RPS` | profile | Global requests per second |
| `SHODAN_API_KEY` | — | Optional Shodan key |
| `HUNTER_API_KEY_1..N` | — | Optional Hunter.io keys (round-robin) |
| `DUPIN_AUTONOMO` | `1` | Fully autonomous agent mode |
| `DUPIN_ANTILOOP` | `8` | Repeated tool-call threshold |
| `DUPIN_FORCE_CLOSE` | `0` | Enable no-progress close gate |

## Output

Each investigation creates `reports/<target>_<timestamp>/`:

```
report.md          # written report (executive summary + findings)
findings.jsonl     # one JSON finding per line (severity, evidence, module)
entities.json      # emails, people, companies + sources
entities.csv       # same, spreadsheet-friendly
assets.json        # discovered assets
run-log.jsonl      # every agent step and tool call
evidence/          # raw evidence snapshots
```

## Responsible use

DUPIN WEBINT performs active reconnaissance. **Only use it against systems,
domains and assets you own or have explicit written authorization to test.**
Using it against third parties without permission may be illegal in your
jurisdiction. You are solely responsible for your use.

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## License

**DUPIN Source-Available License (No-Derivatives).** You may read, run and
install DUPIN WEBINT free of charge. You may **not** modify it or redistribute
modified versions. Commercial use requires written permission from DUPIN.

© 2026 [DUPIN Ciberseguridad](https://dupin.com.ar) — Buenos Aires, Argentina.

---

🇦🇷 [Leer en español](README.es.md)
