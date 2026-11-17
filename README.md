# Trado

A voice-only AI buddy for Windows that **teaches trading and investing**, with an India focus.
Hold a hotkey, ask a question out loud, and Trado listens, looks at your screen, and answers
out loud in simple words.

> **Educational only. Not financial advice.** Trado is an educator and guide, never an adviser.
> It will not tell you what to buy or sell, give price targets or predictions, or plan your money.
> It is not a SEBI-registered investment adviser and is not affiliated with SEBI, NSE, BSE or any broker.
> For personal decisions, talk to a SEBI-registered investment adviser. Trado can be wrong, so check
> facts with official sources. See [PRODUCT_RULES.md](PRODUCT_RULES.md).

**Status: early preview (v0.3).** It works, but it is for people comfortable running a Python program.
Project page: <https://itsridhima.github.io/trado/>
There is no installer yet.

## What it does today
1. You hold a hotkey and speak (you hear a short beep when the mic is ready).
2. Trado turns your speech into text (Whisper large-v3 on Groq).
3. It captures the screen under your mouse (in memory only) and asks a vision AI about it.
4. It shows the answer and **speaks it sentence by sentence** with the built-in Windows voice.
5. Press the hotkey again at any time to interrupt it.
6. It remembers your last few questions, so follow-ups like "and what does that mean?" work. Say "forget that" to clear it.
7. *Early test:* when your question is about one thing on the screen, Trado prints where it would point (a position on
   your screen). The glowing cursor that actually flies there is the next step and is not built yet. The free AI model
   needs a small, measured correction to its pointer numbers; Trado applies it automatically for the default model.

**Not built yet:** the glowing "pointing" cursor, a built-in trading knowledge
base, a tray icon, a first-run setup screen and an installer. Only English is supported for now.

## What you need
- Windows 10 or 11, a microphone, and an internet connection
- [Python 3.11 or newer](https://www.python.org/downloads/) (tick "Add python.exe to PATH" when installing)
- A **free Groq API key** (see below). Groq's free plan allows only a few questions per minute.

## Set up (Windows PowerShell)
```powershell
git clone https://github.com/itsridhima/trado.git
cd trado
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Then get your key:
1. Make a free account at <https://console.groq.com> and create a key at <https://console.groq.com/keys>.
2. Save it privately by running `python -m trado --setup`. You paste the key with the screen hidden, and Trado
   stores it in a private folder on your PC that cloud sync (such as OneDrive) does not copy.
   **Never share the key or post it anywhere.** (Advanced: copy `.env.example` to `.env` and paste the key
   after `GROQ_API_KEY=`, but don't keep that file inside a OneDrive or Dropbox folder.)
3. In the Groq console, look for its data-control settings and consider switching on
   **Zero Data Retention**, since your questions and screenshots are sent there.

Run it:
```powershell
python -m trado
```
Hold **Ctrl + Left Alt** (change it with `TRADO_HOTKEY` in your key file, e.g. `ctrl+alt` for either Alt key, or `f9`),
wait for the beep, speak, release.
If you pick a function key such as `f9`, many laptops need you to hold **Fn** as well. Press **Ctrl+C** to quit.

Handy extras: `python -m trado --mics` lists microphones, `python -m trado --voices` lists voices,
`python -m trado --where` shows which settings file Trado is using (nothing secret), and
`python -m trado --set TRADO_HOTKEY=ctrl+alt_l` changes an ordinary setting without editing any file.
Every setting is explained in `.env.example`.

## Limits and privacy
- **Your voice, and a screenshot when your question is about the screen, leave your computer.** They are sent to Groq to be transcribed and
  answered. Trado keeps audio and screenshots **in memory only and never saves them to disk**, but
  **Groq's free plan may store this data or use it to improve its services** (check Groq's current terms).
  Groq offers a "Zero Data Retention" data control in its console, which is worth switching on. Close anything
  private first, and never say or show PAN, Aadhaar, passwords, OTPs or bank details. Set
  `TRADO_SEND_SCREEN=false` to stop sending screenshots.
- **Trado never acts for you.** It will not click, type or submit anything.
- **Screenshots are shrunk before they are sent** to about 1008 pixels on the longest side (`TRADO_SCREEN_MAX_SIDE`, up to
  1568). At that size the AI's pointer positions were measured to be accurate; very small text on screen can be harder to
  read, so raise it if that matters more to you than pointing.
- **Screenshots only when they help.** Trado sends a screenshot only when your question looks like it is about the screen
  (for example "what am I looking at?" or "what does this chart mean?"). General questions like "What is a SIP?" go
  without one, which also saves your free limit. When it is unsure, it sends one. Say "look at my screen" to be sure,
  or set `TRADO_SCREEN_MODE=always` to send one every time. This is a pattern-based guess, so it can be wrong.
- **Short memory.** Trado remembers your last 5 questions and its answers, as text, while it is open, so follow-ups like
  "and what does that mean?" work. That text is sent to Groq with each new question. It is never saved to disk, never
  includes screenshots, and is cleared when you quit or say "forget that". Private-looking details are hidden before they
  are remembered. Set `TRADO_MEMORY=0` to turn it off.
- **Private pages.** If the window in front looks like a login, KYC, bank or broker page, Trado shows a
  Yes/No box before sending a screenshot (default answer: No). It only reads the front window's title, so it
  can miss things, and it can't see other windows or notifications on your screen.
- **Private details are hidden before the AI sees them.** Things that look like a PAN, Aadhaar or card number,
  phone number, email or UPI ID, OTP or password are replaced with "[hidden ...]" in your question and in the
  AI's answer. Your voice clip is uploaded before this happens, so still don't say private details aloud.
- **What stays on your screen.** Your questions and Trado's answers are printed in the terminal window. Trado doesn't
  save them, but your terminal's scroll-back (or PowerShell transcription, if you turned it on) may keep them.
  Close the window when you are done with a private session.
- **Keys are protected.** Your key is never printed. Messages that come from outside (AI answers, server errors) are
  cleaned of terminal control codes and anything that looks like a key before they are shown.
- **It can be wrong.** Speech recognition and AI answers make mistakes, and Trado has no live market data.
- **Trado can see its own window.** If the terminal where Trado prints is visible, it is part of the screenshot, so the AI
  can read your recent questions there even after you say "forget that". Move or minimise that window when you want a
  clean slate.
- **Waits are normal.** The free plan allows only about two screenshot questions a minute. Trado waits (up to a minute) and
  says so; press the hotkey again to cancel the wait and nothing is sent.
- **A daily allowance too.** Groq's free plan allows about 200,000 tokens a day for the AI, which is roughly 50 questions
  with a screenshot or 140 without. Trado warns you when you are close, and says plainly when it has run out (it
  resets within a day). The test tools use the same allowance and tell you their cost first: `run_guardrails` about 49
  thousand, `run_injection` and `run_pointing_test` about 21 thousand each.
- **Free-tier limits and changes.** Free AI models get retired and limits change. Model names are set in
  `.env` so you can update them. If something stops working, check `.env.example` and Groq's model list.
- **No telemetry.** Trado sends nothing anywhere except to Groq, using your own key.

## Tests
```powershell
python -m unittest discover tests
python -m tools.run_guardrails
python -m tools.run_injection
python -m tools.run_pointing_test
```
The first command checks the code offline. The others need your Groq key and take a few minutes on the free plan:
`run_guardrails` asks the AI the questions in `tests/guardrail_questions.md` and reports any answer that breaks the
product rules; `run_injection` shows it fake pages with hostile instructions; `run_pointing_test` draws a fake broker
page and measures how accurately the AI points at things whose position is known (add `--max-side 1008` to test a smaller picture).

## Contributing and security
See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Changes are listed in
[CHANGELOG.md](CHANGELOG.md).

## Credits and licence
Trado is inspired by [Clicky](https://github.com/farzaa/clicky) by Farza (MIT). Trado is an independent
Windows project: it uses Clicky's general idea, not its code, and is not affiliated with Clicky or HeyClicky.
Trado is released under the [MIT License](LICENSE). Libraries it uses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
