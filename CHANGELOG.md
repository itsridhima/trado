# Changelog

## Unreleased
### Round 2, step 3 (first half): pointing, printed targets only
- The AI now ends screen answers with a hidden tag like `[POINT:784,490:Quantity box]`. Trado hides the tag from the screen, the
  voice and the memory, checks it (whole numbers only, clamped to the screen, label cleaned, anything odd is ignored), turns it
  into a real screen position (including shrunk screenshots and multi-monitor setups) and prints where it would point.
  There is no glowing cursor yet. `TRADO_POINTING=off` hides the printed lines.
- New `python -m tools.run_pointing_test`: draws a fake broker page with known positions and measures how accurately the AI
  points, including whether it uses real pixels or a 0-1000 scale.
- Screen capture now reports its size and monitor position; the AI is told the screenshot's size.
- First real calibration: the free AI model's positions were about 62% of the true height (consistently) and partly off
  sideways, so pointing is not yet reliable. A smaller picture (1008 wide) fixed the sideways error. Re-scoring both real runs
  shows the AI's up-and-down number is too small by height/width; multiplying it by width/height puts all 12 answers inside the
  right boxes. A third run on a 16:9 page confirmed it (6 of 6, typical miss 16 pixels; the AI's height numbers were 0.56 of the
  truth, exactly 567/1008), ruling out a constant factor.
- The daily-usage warning now counts estimated TOKENS (about 200,000 a day on the free plan) instead of requests, so it warns in time.
  The test tools say what a run will cost and stop at once when the daily allowance is gone; the pointing test now reports
  INCOMPLETE (not a false verdict) when some questions failed.
- Trado now sends screenshots 1008 pixels wide (`TRADO_SCREEN_MAX_SIDE`) and corrects the AI's up-and-down pointer number by
  width/height for models known to need it (`TRADO_POINT_FIX=auto|aspect|none`; auto = the default model). The calibration tool
  now also scores answers through Trado's own pointing code.
- Rule checker fixes (two false alarms), a new check that fails any reply telling you to tap/click/press a buy or confirm
  button, and two new guardrail questions about buttons. The prompt now says plainly never to tell you to press a button.
### Round 2, step 1: short memory
- Trado remembers your last 5 questions and answers (text only, in memory only) so follow-ups like "and what does that mean?"
  work. Say "forget that" to clear it; `TRADO_MEMORY=0` turns it off. See the privacy notes in README.md and SECURITY.md.
- New end-to-end tests that run the real app flow with a fake microphone, AI and voice.
- When the free limit is full, Trado now waits up to a minute and says so, instead of refusing; pressing the hotkey cancels
  the wait and nothing is sent.
- "I didn't catch that" replies are no longer remembered, and asking about a cleared conversation now gets a clear answer.
- Screenshots are now sent only when your question looks like it is about the screen ("What is a SIP?" goes without one; "what am I
  looking at?" sends one; when unsure it sends one). `TRADO_SCREEN_MODE=always` restores the old behaviour. About three times as many
  questions fit in the free per-minute limit, and less of your screen is sent to Groq.
- Waits shorter than 2 seconds are silent (no more "waiting about 0 seconds").

### Security hardening (see SECURITY.md)
- Key file now lives in a private local folder first (`python -m trado --setup`), with a warning if it is in a synced folder.
- Private-looking details (PAN, Aadhaar, card, phone, email/UPI, OTP, password) are hidden before the AI sees them and in its answers.
- A Yes/No box appears before a screenshot of a login, KYC, bank or broker page is sent.
- Stronger protection against instructions hidden in screenshots, plus `python -m tools.run_injection` to test it.
- Low security findings fixed: terminal control codes and key-like text are cleaned from untrusted messages, the settings
  object hides the key, the hotkey ignores unrelated keys, client-side rate limits and daily-limit warnings, pinned
  dependency versions, a commit-time secret check (`git config core.hooksPath .githooks`), a tighter `.gitignore`,
  and clearer privacy wording.
- Libraries scanned with `pip-audit` on 2026-11-13: no known vulnerabilities (after upgrading pip to 26.3). See SECURITY.md.
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
