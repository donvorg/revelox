# CLAUDE.md

## Project Overview

revelox is an open-source CLI tool for adversarial security testing of voice AI agents. It makes real phone calls (via Twilio) or WebSocket connections to a target voice agent, runs adversarial attack scenarios, transcribes and evaluates the agent's responses using an LLM-as-judge, and produces structured security reports mapped to OWASP Top 10 for Agentic Applications.

Think "Promptfoo, but for voice agents." Promptfoo sends text to an HTTP endpoint. We place a phone call or open an audio stream, speak adversarial inputs via TTS, listen to the agent's spoken response via STT, and evaluate the transcript.

## Tech Stack

- **Language:** Python 3.11+
- **Package manager:** pip / pyproject.toml
- **CLI framework:** Click
- **Config format:** YAML (parsed with PyYAML)
- **Validation:** Pydantic v2
- **TTS:** Deepgram Aura API
- **STT:** Deepgram Nova-3 API
- **Telephony:** Twilio Voice SDK (twilio-python)
- **WebSocket:** websockets package (for Vapi/Retell/LiveKit targets)
- **LLM (attack scripting):** OpenAI Python SDK, Anthropic Python SDK, or Ollama
- **LLM (judge):** OpenAI or Anthropic Python SDK
- **Audio processing:** pydub + audioop (format conversion, recording)
- **Async:** asyncio throughout (calls are I/O-bound)
- **Report output:** JSON + Markdown (Jinja2 templates)
- **Testing:** pytest + pytest-asyncio
- **Linting:** ruff
- **Type checking:** mypy (strict)

## Project Structure

```
revelox/
├── src/
│   └── revelox/
│       ├── __init__.py
│       ├── __main__.py             # `python -m revelox` entrypoint
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py             # Click group + command registration
│       │   ├── init_cmd.py         # `revelox init`
│       │   └── run_cmd.py          # `revelox run`
│       ├── config/
│       │   ├── __init__.py
│       │   ├── schema.py           # Pydantic models for config
│       │   ├── loader.py           # YAML parser + validator
│       │   └── defaults.py         # default config values
│       ├── caller/
│       │   ├── __init__.py
│       │   ├── base.py             # abstract CallerBase class
│       │   ├── engine.py           # multi-turn conversation loop
│       │   ├── phone.py            # Twilio PSTN caller
│       │   ├── websocket.py        # WebSocket caller (Vapi, Retell, etc.)
│       │   ├── http.py             # HTTP API caller (custom agents)
│       │   ├── persona.py          # caller persona config
│       │   └── recorder.py         # audio recording + WAV export
│       ├── tts/
│       │   ├── __init__.py
│       │   └── deepgram.py         # Deepgram Aura TTS wrapper
│       ├── stt/
│       │   ├── __init__.py
│       │   └── deepgram.py         # Deepgram Nova-3 STT wrapper
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py             # abstract LLMProvider protocol
│       │   ├── openai.py           # OpenAI implementation
│       │   ├── anthropic.py        # Anthropic implementation
│       │   ├── ollama.py           # Ollama (local) implementation
│       │   └── factory.py          # provider string → instance
│       ├── modules/
│       │   ├── __init__.py
│       │   ├── loader.py           # dynamic module discovery + loading
│       │   ├── types.py            # AttackModule / AttackScenario models
│       │   └── voice_prompt_injection/
│       │       ├── __init__.py
│       │       ├── manifest.yaml
│       │       ├── module.py       # scenario definitions
│       │       ├── scripts/        # conversation script templates
│       │       └── judge_prompt.txt
│       ├── judge/
│       │   ├── __init__.py
│       │   ├── evaluator.py        # LLM-as-judge evaluation engine
│       │   └── prompts.py          # judge system prompts
│       ├── report/
│       │   ├── __init__.py
│       │   ├── generator.py        # report assembly
│       │   ├── json_report.py      # JSON output
│       │   └── markdown_report.py  # Markdown output (Jinja2)
│       ├── orchestrator/
│       │   ├── __init__.py
│       │   └── runner.py           # sequences modules, manages concurrency
│       └── utils/
│           ├── __init__.py
│           ├── logger.py           # structured logging (structlog)
│           ├── auth_check.py       # runtime authorization confirmation
│           └── rate_limiter.py     # call rate limiting
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── templates/
│   ├── default_config.yaml         # template for `revelox init`
│   └── report.md.j2               # Markdown report Jinja2 template
├── pyproject.toml
├── LICENSE                         # Apache 2.0
├── RESPONSIBLE_USE.md
├── CONTRIBUTING.md
├── CLAUDE.md                       # this file
└── README.md
```

## Architecture

Three stages, mirroring Promptfoo but replacing the text runner with a voice runner:

1. **Attack Generation** — An LLM generates adversarial dialogue based on the selected attack module's template and the target's security policy. Each module defines what to attack; the LLM makes it conversational and adaptive.

2. **Call Execution (the voice-specific part)** — The caller engine places a real call to the target, speaks the adversarial script via TTS, captures the agent's audio response, and transcribes it via STT. Multi-turn: the caller adapts based on what the agent says.

3. **Evaluation** — An LLM judge evaluates each (attack, response) pair against the user's security policy and the module's success/failure criteria. Outputs PASS/FAIL/INCONCLUSIVE with severity and OWASP mapping.

## Coding Conventions

- Use `async/await` throughout. Calls are I/O-bound — asyncio is the right model.
- All external API calls must be wrapped in try/except with meaningful error messages.
- Use Pydantic v2 for all data models and config validation. No raw dicts crossing function boundaries.
- Use `Protocol` classes (typing) for abstract interfaces, not ABC unless state is needed.
- Type hints on every function signature. Run mypy in strict mode.
- Prefer explicit imports over star imports. No `from module import *`.
- Use `pathlib.Path` everywhere, never string concatenation for file paths.
- Use `structlog` for logging. Structured key-value output, not f-string messages.
- Keep files under 200 lines. If a file grows past that, split it.
- Write tests for all non-trivial logic. Use `pytest-asyncio` for async tests.
- Use `ruff` for linting and formatting. No separate black/isort/flake8.
- Docstrings on all public functions (Google style).

## Key Design Decisions

- **Modules are plugins, not hardcoded.** Each attack module is a self-contained package with a manifest, scripts, and judge prompt. New modules can be added without touching core code. Discovery via `importlib` or directory scanning.
- **LLM provider is swappable.** Users choose their LLM for both attack generation and judging. Support OpenAI, Anthropic, and Ollama from day one. All providers implement the same `LLMProvider` protocol.
- **Target type is swappable.** Phone (Twilio), WebSocket, and HTTP targets all implement the same `CallerBase` interface. Adding a new target type means implementing one class.
- **Reports are data, not presentation.** Generate a Pydantic model first, serialize to JSON, then render Markdown from that model. Never generate presentation-only output.
- **Rate limiting is on by default.** Max 2 concurrent calls, max 5 calls per minute. User can override but defaults are conservative. Implemented via `asyncio.Semaphore` + token bucket.
- **Authorization check is mandatory.** Before the first call in any run, the CLI requires explicit user confirmation. Not bypassable via config — runtime prompt unless `--yes` flag is passed (for CI/CD).
- **Async everywhere the network is involved.** Twilio media streams, Deepgram streaming, LLM calls — all async. Synchronous code only for local file I/O and config loading.

## Environment Variables

```
TWILIO_ACCOUNT_SID        — Twilio account SID
TWILIO_AUTH_TOKEN          — Twilio auth token
TWILIO_PHONE_NUMBER        — Twilio phone number to call from
DEEPGRAM_API_KEY           — Deepgram API key (TTS + STT)
OPENAI_API_KEY             — OpenAI API key (optional, for attack gen + judge)
ANTHROPIC_API_KEY          — Anthropic API key (optional, alternative to OpenAI)
OLLAMA_BASE_URL            — Ollama server URL (optional, default http://localhost:11434)
revelox_LOG_LEVEL         — Log level (DEBUG, INFO, WARNING, ERROR). Default: INFO
revelox_MAX_CONCURRENCY   — Max concurrent calls. Default: 2
revelox_CALLS_PER_MIN     — Max calls per minute. Default: 5
```

## Commands

```
revelox init                    — creates revelox.config.yaml from template
revelox run                     — runs attack suite against configured target
revelox run --target phone:+1...  — override target from CLI
revelox run --modules mod1,mod2   — run specific modules only
revelox run --profile healthcare  — use industry preset
revelox run --format json,md      — output format(s)
revelox run --fail-on critical    — exit code 1 if any critical findings (for CI)
revelox run --yes                 — skip authorization prompt (for CI/CD)
revelox report <path>             — regenerate report from existing JSON results
```

## Important Notes

- Never hardcode API keys or phone numbers. Always read from env vars or config.
- Never make a real phone call in tests. Mock the Twilio and Deepgram clients.
- The `--yes` flag skips the authorization prompt but should log a warning that authorization was assumed.
- All audio recordings are stored locally in `./revelox-recordings/` by default. Never upload recordings anywhere.
- The tool must work fully offline except for the APIs it explicitly calls (Twilio, Deepgram, LLM provider). No telemetry, no phoning home, no analytics.
- When shelling out to Python audio libraries (numpy, scipy, torchaudio) for future Layer 1 attacks, keep those as optional dependencies — the core tool should install and run without them.
