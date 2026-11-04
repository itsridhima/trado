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
- `trado/` code, `trado/stt/` speech-to-text providers
- `tests/` tests and `guardrail_questions.md`
- `docs/` notes

## Current status
Slice 1 only: hold hotkey -> record mic -> release -> transcribe -> print text.
Not built yet: screen capture, AI answers, voice output, overlay, pointing.
