"""Ask Trado's AI every question in tests/guardrail_questions.md (no voice needed) and report rule breaks.

Run from the project folder:
    python -m tools.run_guardrails                 all questions (takes about 4 minutes on the free plan)
    python -m tools.run_guardrails --only A,D      only some groups (A to G)
    python -m tools.run_guardrails --limit 5       only the first 5 questions
    python -m tools.run_guardrails --numbers 8,26  only questions number 8 and 26
    python -m tools.run_guardrails --save report.md   also write a report file (not committed to git)

Each question is sent as text only (no screenshot). It uses the same system prompt as the real app.
"""

import argparse
import sys
import time
from pathlib import Path

from trado.config import PROJECT_ROOT, load_settings
from trado.guardrails import check_answer, parse_questions, verdict
from trado.llm import LlmError, LlmRateLimitError, create_llm_provider
from trado.llm.groq_vision import describe_cost
from trado.pointing import strip_point_tags

QUESTIONS_FILE = PROJECT_ROOT / "tests" / "guardrail_questions.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Trado's answers against the product rules.")
    parser.add_argument("--only", default="", help="comma list of groups, e.g. A,D")
    parser.add_argument("--numbers", default="", help="comma list of question numbers, e.g. 8,26")
    parser.add_argument("--limit", type=int, default=0, help="only run the first N questions")
    parser.add_argument("--delay", type=float, default=6.0, help="seconds to pause between questions (free-plan limit)")
    parser.add_argument("--save", default="", help="write a full report to this file")
    args = parser.parse_args()

    questions = parse_questions(QUESTIONS_FILE.read_text(encoding="utf-8"))
    groups = {g.strip().upper() for g in args.only.split(",") if g.strip()}
    if groups:
        questions = [q for q in questions if q.category in groups]
    wanted = {int(n) for n in args.numbers.split(",") if n.strip().isdigit()}
    if wanted:
        questions = [q for q in questions if q.number in wanted]
    if args.limit:
        questions = questions[: args.limit]
    if not questions:
        print("No questions matched.")
        return 1

    settings = load_settings()
    try:
        llm = create_llm_provider(settings)
    except LlmError as err:
        print(f"Setup problem: {err}")
        return 1

    print(f"Asking {len(questions)} questions with model {settings.llm_model} (text only, no screenshots)...")
    print(describe_cost(text_questions=len(questions)) + "\n")
    results = []
    for index, q in enumerate(questions):
        if index:
            time.sleep(args.delay)
        try:
            answer = strip_point_tags("".join(llm.stream_answer(q.text, None)))
            findings = check_answer(q, answer)
            outcome = verdict(findings)
        except LlmError as err:
            answer, findings, outcome = f"[no answer: {err}]", [], "ERROR"
            results.append((q, answer, findings, outcome))
            print(f"[{outcome:5}] Q{q.number} ({q.category}/{q.expected}) {q.text}")
            if isinstance(err, LlmRateLimitError) and "daily" in str(err).lower():
                print("\nSTOPPED: the free daily allowance is used up. Run the rest tomorrow, for example with --numbers.")
                break
            continue
        results.append((q, answer, findings, outcome))
        print(f"[{outcome:5}] Q{q.number} ({q.category}/{q.expected}) {q.text}")

    counts = {k: sum(1 for r in results if r[3] == k) for k in ("PASS", "WARN", "FAIL", "ERROR")}
    print("\n" + "=" * 70)
    print(f"PASS {counts['PASS']}   WARN {counts['WARN']}   FAIL {counts['FAIL']}   ERROR {counts['ERROR']}")

    problems = [r for r in results if r[3] in ("FAIL", "ERROR")]
    if problems:
        print("\n--- FAILURES (these broke a rule) ---")
        for q, answer, findings, outcome in problems:
            print(f"\nQ{q.number} [{q.category}] {q.text}")
            for f in findings:
                print(f"  {f.level}: {f.message}")
            print(f"  ANSWER: {answer}")
    warns = [r for r in results if r[3] == "WARN"]
    if warns:
        print("\n--- WARNINGS (read these, they may be fine) ---")
        for q, answer, findings, outcome in warns:
            print(f"\nQ{q.number} [{q.category}] {q.text}")
            for f in findings:
                print(f"  {f.level}: {f.message}")
            print(f"  ANSWER: {answer}")
    if not problems:
        print("\nNo rule breaks found by the automatic checks. Skim the answers anyway: the checks are simple patterns.")

    if args.save:
        lines = [f"# Guardrail report ({settings.llm_model})\n", f"PASS {counts['PASS']} / WARN {counts['WARN']} / FAIL {counts['FAIL']} / ERROR {counts['ERROR']}\n"]
        for q, answer, findings, outcome in results:
            lines.append(f"\n## Q{q.number} [{q.category}/{q.expected}] {outcome}: {q.text}\n")
            lines.extend(f"- {f.level}: {f.message}" for f in findings)
            lines.append(f"\n> {answer}\n")
        Path(args.save).write_text("\n".join(lines), encoding="utf-8")
        print(f"\nReport written to {args.save}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
