# Changelog

## Unreleased: security hardening (see SECURITY.md)
- Key file now lives in a private local folder first (`python -m trado --setup`), with a warning if it is in a synced folder.
- Private-looking details (PAN, Aadhaar, card, phone, email/UPI, OTP, password) are hidden before the AI sees them and in its answers.
- A Yes/No box appears before a screenshot of a login, KYC, bank or broker page is sent.
- Stronger protection against instructions hidden in screenshots, plus `python -m tools.run_injection` to test it.
- Low security findings fixed: terminal control codes and key-like text are cleaned from untrusted messages, the settings
  object hides the key, the hotkey ignores unrelated keys, client-side rate limits and daily-limit warnings, pinned
  dependency versions, a commit-time secret check (`git config core.hooksPath .githooks`), a tighter `.gitignore`,
  and clearer privacy wording.
- New helper commands: `python -m trado --where` (which settings file is used) and `--set NAME=value` (change a setting safely).
- The default hotkey is now Ctrl + Left Alt (it was F9 in v0.1). Set `TRADO_HOTKEY=f9` to go back.

## v0.1 (2026-11-13): early preview, "basic Trado"
- Hold a global hotkey (default F9), speak, release.
- Speech to text with Whisper large-v3 on Groq (English by default), with a clear-speech check,
  a silence gate, a ready beep and volume feedback.
- Captures the screen under your mouse (in memory only) and streams an answer from a vision AI.
- Speaks the answer sentence by sentence with the built-in Windows voice; press the hotkey to interrupt.
- Product rules built into the system prompt, plus a rule checker and runner
  (`python -m tools.run_guardrails`) over 33 test questions.
- Plain-words handling of rate limits and errors.
- Not yet: memory, pointing cursor, knowledge base, tray icon, setup screen, installer.
