# Third-party notices

Trado itself is MIT licensed. It installs and uses these open-source libraries (checked from the
installed package information; see each project for the full licence text). Trado does not copy or
bundle their code in this repository.

| Library | Used for | Licence |
|---|---|---|
| httpx | talking to the Groq API | BSD-3-Clause |
| python-dotenv | reading your local `.env` file | BSD-3-Clause |
| sounddevice | recording from the microphone | MIT |
| numpy | holding audio samples | BSD-3-Clause (with some bundled MIT/Zlib/0BSD parts) |
| pynput | global hold-to-talk hotkey | LGPL-3.0 |
| mss | screenshots | MIT |
| Pillow | shrinking screenshots | MIT-CMU |
| comtypes | the built-in Windows voice | MIT |
| PySide6 (Essentials) and shiboken6 | the top panel, settings window and cursor overlay (Qt) | LGPL-3.0 |

Notes:
- **pynput is LGPL-3.0.** Trado uses it unmodified through `pip`. If a future installer bundles it,
  that installer must follow the LGPL (for example, shipping it as a replaceable folder, not a single locked file).
- **PySide6/Qt is LGPL-3.0.** Same rule as pynput: used unmodified through `pip`; a future installer must ship it as replaceable files.
- Trado is inspired by [Clicky](https://github.com/farzaa/clicky) (MIT, by Farza). No Clicky code is included.
- AI models (Whisper large-v3 and Qwen) run on Groq's servers under Groq's terms and are not distributed with Trado.
