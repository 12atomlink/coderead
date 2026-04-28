# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**coderead** (Project Analyzer v1) is a CLI tool that produces a structured "cognitive document" from any code repository. It runs a multi-agent LLM pipeline over the repo's file tree and contents, producing a JSON + Markdown analysis covering structure, behavior, design intent, trade-offs, and a final review pass.

## Commands

```bash
# Install dependencies
uv sync

# Run an analysis
uv run python main.py ./path/to/repo --provider deepseek --api-key sk-xxx

# Use a config file instead of CLI flags
uv run python main.py ./path/to/repo --config llm-config.json

# Resume an interrupted run (skips already-completed steps)
uv run python main.py ./path/to/repo --provider deepseek --resume

# Start from a specific pipeline step
uv run python main.py ./path/to/repo --provider deepseek --from-step behavior

# List available providers and their default models
uv run python main.py --list-providers

# Re-render a Markdown report from an existing JSON result
uv run python core/report.py output/analysis.json output/analysis.md
```

Output defaults to `output/analysis.json` and `output/analysis.md`. Intermediate per-step results go to `output/intermediate/`. Previous runs are automatically backed up to `output/backup/<timestamp>/`.

## Architecture

### Pipeline flow

`main.py` → `Pipeline` → `RepoLoader` → 5 sequential agents → `SharedDocument` → JSON + Markdown output

### Core modules (`core/`)

| File | Role |
|---|---|
| `pipeline.py` | Orchestrates agent execution, handles resume/skip logic, backup of prior runs |
| `llm.py` | OpenAI-compatible client; falls back to streaming when non-stream fails; retries JSON parse up to 2× on a fallback model |
| `providers.py` | Named provider presets (deepseek, qwen, moonshot, siliconflow, modelscope, ollama, …); `resolve_config()` merges CLI flags → config file → env vars |
| `loader.py` | Walks a repo directory, skips binaries/large files (>100 KB), returns file tree + contents |
| `context.py` | `SharedDocument` — the shared data structure passed through the pipeline; each agent writes one section |
| `report.py` | Renders `SharedDocument` to Markdown; also usable standalone |

### Agent pipeline (`agents/`)

Agents run in strict order; each reads `SharedDocument` from prior steps and writes one section:

1. **structure** — modules, dependencies, entry points
2. **behavior** — execution flows, data flow, control flow
3. **intent** — design goals, architectural patterns, assumptions
4. **tradeoff** — pros, cons, alternatives, risks
5. **reviewer** — cross-checks all sections for issues and inconsistencies

`BaseAgent` in `agents/base.py` handles: loading the prompt from `prompts/<agent>.md`, calling `llm.chat_json()`, saving raw LLM response to `output/debug/` on failure.

### LLM configuration

Priority order (highest wins): CLI flag → config file (`--config`) → environment variable → provider default.

Env vars recognized: `LLM_API_KEY`, `OPENAI_API_KEY`, `LLM_BASE_URL`, `OPENAI_BASE_URL`, `LLM_MODEL`.

Config file format: see `llm-config.example.json`.

The `modelscope` provider has a predefined `fallback_models` list; other providers only fall back if the non-stream response fails (then streaming is tried). If a user-specified `--model` is provided, fallback is disabled entirely.

### Adding a new agent

1. Create `agents/<name>_agent.py` subclassing `BaseAgent`; set `agent_name`, `prompt_file`, `output_section`; implement `build_user_prompt()`
2. Add a corresponding prompt in `prompts/<name>.md`
3. Add the agent to `AGENT_NAMES` and the `agents` list in `Pipeline.__init__()` in `core/pipeline.py`
4. Add a section schema to `create_empty_document()` in `core/context.py`
5. Add a renderer to `core/report.py`
