# Trado

A voice-only AI buddy for Windows that **teaches trading and investing**, with an India focus.
Hold a hotkey, ask a question out loud, and Trado listens, looks at your screen, and answers
out loud in simple words.

> **Educational only. Not financial advice.** Trado is an educator and guide, never an adviser.
> It will not tell you what to buy or sell, give price targets or predictions, or plan your money.
> It is not a SEBI-registered investment adviser and is not affiliated with SEBI, NSE, BSE or any broker.
> For personal decisions, talk to a SEBI-registered investment adviser. Trado can be wrong, so check
> facts with official sources. See [PRODUCT_RULES.md](PRODUCT_RULES.md).

**Status: early preview (v0.2).** It works, but it is for people comfortable running a Python program.
Project page: <https://itsridhima.github.io/trado/>
There is no installer yet.

## What it does today
1. You hold a hotkey and speak (you hear a short beep when the mic is ready).
2. Trado turns your speech into text (Whisper large-v3 on Groq).
3. It captures the screen under your mouse (in memory only) and asks a vision AI about it.
4. It shows the answer and **speaks it sentence by sentence** with the built-in Windows voice.
5. Press the hotkey again at any time to interrupt it.

**Not built yet:** conversation memory, the glowing "pointing" cursor, a built-in trading knowledge
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
- **Your voice and a screenshot leave your computer.** They are sent to Groq to be transcribed and
  answered. Trado keeps audio and screenshots **in memory only and never saves them to disk**, but
  **Groq's free plan may store this data or use it to improve its services** (check Groq's current terms).
  Groq offers a "Zero Data Retention" data control in its console, which is worth switching on. Close anything
  private first, and never say or show PAN, Aadhaar, passwords, OTPs or bank details. Set
  `TRADO_SEND_SCREEN=false` to stop sending screenshots.
- **Trado never acts for you.** It will not click, type or submit anything.
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
- **Free-tier limits and changes.** Free AI models get retired and limits change. Model names are set in
  `.env` so you can update them. If something stops working, check `.env.example` and Groq's model list.
- **No telemetry.** Trado sends nothing anywhere except to Groq, using your own key.

## Tests
```powershell
python -m unittest discover tests
python -m tools.run_guardrails
```
The second command asks the AI the questions in `tests/guardrail_questions.md` and reports any answer
that breaks the product rules (it needs your Groq key and takes a few minutes on the free plan).

## Contributing and security
See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Changes are listed in
[CHANGELOG.md](CHANGELOG.md).

## Credits and licence
Trado is inspired by [Clicky](https://github.com/farzaa/clicky) by Farza (MIT). Trado is an independent
Windows project: it uses Clicky's general idea, not its code, and is not affiliated with Clicky or HeyClicky.
Trado is released under the [MIT License](LICENSE). Libraries it uses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
