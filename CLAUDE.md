# CLAUDE.md - guidance for AI coding assistants working on Trado

Trado is a voice-only AI buddy for Windows that teaches trading and investing
(India-focused). Inspired by farzaa/clicky (MIT); all code here is original.

## Non-negotiable product rules
(Full text in PRODUCT_RULES.md. The app's system prompt must enforce them.)
- Trado is an educator and guide, never an advisor.
- Never recommend buying or selling a specific stock. Never give price targets,
  entry/exit points, predictions, or personalised allocation advice.
- Never ask for or type PAN, Aadhaar, passwords, OTPs or bank details. Never click
  submit or perform actions for the user. Only explain and point.
- For personal investment decisions: say it can't advise, suggest a SEBI-registered adviser.
- If unsure of a fact, say so rather than guessing.

## Engineering rules
- Free only: no paid APIs. Current providers: Groq (speech-to-text), Gemini (later).
- Never ask the user to paste API keys in chat. Keys go in the local `.env` (gitignored).
- Never save audio to disk by default.
- Providers (speech-to-text now; LLM and TTS later) sit behind small interfaces so they can be swapped.
- Handle errors and rate limits (HTTP 429) gracefully; never crash on a failed request.
- Windows 11, Python 3.11+. Keep dependencies few and small.

## Working style
- The user is a beginner: explain steps in simple words and say what they type vs. what you do.
- Build in small slices. Stop after each slice and wait for the user's report.
- Ask before every git commit. Keep commits small with clear messages.

## Layout
- `trado/` code; `trado/stt/` speech-to-text, `trado/llm/` AI answers, `trado/tts/` voice out (each swappable)
- `trado/guardrails.py` rule checks; `tools/` helper scripts (guardrail runner)
- `tests/` tests and `guardrail_questions.md`
- `docs/` notes

## Current status
Round 1 (basic Trado, v0.1) is built and tested by the user:
hold hotkey -> record mic -> Whisper large-v3 (Groq) -> screenshot of the screen under the mouse ->
streamed vision-AI answer (Groq qwen/qwen3.8-27b) -> spoken sentence by sentence (Windows voice).
Pressing the hotkey again interrupts. `python -m tools.run_guardrails` checks answers against the product rules.
Not built yet (Round 2+): memory, pointing and overlay, trading knowledge notes, tray/privacy, first-run setup, installer.
Plan: build in rounds (basic -> add a few things -> refine); the user tests after each round.
Free tiers change: Llama 4 Scout was retired in July 2026, so keep model names configurable in `.env`.
