# Trado

A voice-only AI buddy for Windows that teaches trading and investing, with an
India focus. You hold a hotkey and speak; Trado listens, (eventually) looks at your
screen, answers out loud, and points at things with a glowing cursor.

Trado is an **educator and guide, never an advisor.** See [PRODUCT_RULES.md](PRODUCT_RULES.md).

Inspired by [farzaa/clicky](https://github.com/farzaa/clicky) (MIT). The code here is original.

## Status
Early development (Round 1, "basic Trado"). Hold a hotkey, speak, release: Trado transcribes
your words, looks at your screen, and answers in text and out loud. Press the hotkey again to
interrupt. Not built yet: conversation memory, the glowing pointing cursor, the trading knowledge
base, a tray icon and a first-run setup screen.

## Limits and privacy
- **Not financial advice.** Trado explains concepts. It will not tell you what to buy or
  sell, give price targets or predictions, or plan your money. For personal decisions,
  talk to a SEBI-registered investment adviser.
- **It can be wrong.** Speech recognition and (later) AI answers make mistakes. Check
  facts with official sources (SEBI, NSE, BSE, RBI, your broker).
- **Your voice leaves your computer.** Audio is sent to Groq for transcription. It is
  kept only in memory and **not saved to disk**, but Groq's own policies apply. Don't
  speak PAN, Aadhaar, passwords, OTPs or bank details.
- **Later slices will send screenshots** to an AI service. Keep sensitive pages closed.
- **Free-tier limits.** Free APIs have rate limits; Trado will tell you when you hit one.
- **Keys stay local** in a gitignored `.env` file.
- **Trado never acts for you:** no clicking, submitting or typing into forms.

## Setup (Windows, PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then open .env and paste your GROQ_API_KEY
python -m trado
```
Other handy commands: `python -m trado --mics` (list microphones), `python -m trado --voices` (list voices).

## Tests
```powershell
python -m unittest discover tests
python -m tools.run_guardrails
```
The second command asks the AI the questions in `tests/guardrail_questions.md` and reports any
answer that breaks the product rules (needs your Groq key; takes a few minutes on the free plan).
