# Contributing to Trado

Thanks for helping! Trado is a small beginner-friendly project, so please keep changes small and clear.

## Before you start
- Open an issue to discuss bigger ideas first.
- Read [PRODUCT_RULES.md](PRODUCT_RULES.md). **These rules are not negotiable.** Trado is an educator,
  never an adviser: no stock picks, price targets, predictions or personal allocation advice; it never asks
  for or types PAN, Aadhaar, passwords, OTPs or bank details; and it never clicks or submits for the user.
  Pull requests that weaken them will not be merged.

## Running things
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover tests
```
If you change the system prompt or anything that affects answers, also run `python -m tools.run_guardrails`
(needs your own free Groq key) and make sure nothing FAILs.

## Guidelines
- Keep dependencies few and small, and free to use. Check that a new library's licence allows redistribution.
- Never save audio or screenshots to disk by default.
- Providers (speech, AI, voice) sit behind small interfaces so they can be swapped. Follow that pattern.
- Handle errors and rate limits in plain words; never crash on a failed request.
- Add or update tests for what you change. Don't copy code from other projects unless its licence allows it,
  and say where it came from.
- Never include API keys or personal data in code, tests, issues or screenshots.
