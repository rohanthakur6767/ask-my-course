"""Phase 4 evaluation runner for Ask My Course.

What it does, end to end:
  1. Rebuilds a clean evaluation course and ingests the demo PDF
     (environmental-science-course.pdf), split into its five units.
  2. Sends every question in eval_set.json through the REAL answer pipeline
     (answer_question), exactly as the app does.
  3. Scores three things and prints a summary:
       - Retrieval@k : did a chunk from the correct page come back in the top k?
       - Answer correctness : did the answer contain the key facts?
       - Guardrail accuracy : answered the real questions, refused the rest?
  4. Writes the full per-question breakdown to eval/eval_results.json.

Run it from the backend folder with the venv active:
    python eval/run_eval.py
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# --- Django bootstrap (so we can import the app and hit the real DB) ---
BACKEND = Path(__file__).resolve().parents[1]        # .../ask-my-course/backend
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from courses.models import Course  # noqa: E402
from courses.services.ingest import ingest_structured  # noqa: E402
from courses.services.ask import answer_question, SMALLTALK_MESSAGE  # noqa: E402

# --- Config ---
PDF = "D:/humanoid/environmental-science-course.pdf"
COURSE_NAME = "Eval - Environmental Science"
EVAL_FILE = BACKEND / "eval" / "eval_set.json"
RESULTS_FILE = BACKEND / "eval" / "eval_results.json"
TOP_K = 5
PASS_RATIO = 0.5        # an answer "passes" if it contains >= half the key terms
SLEEP = 1.5             # pause between questions, gentle on the Gemini free tier

# The real page ranges of each unit in the PDF (read straight from the document).
OUTLINE = [
    {"unit": "Course Information", "lesson": "Overview", "page_start": 1, "page_end": 2},
    {"unit": "Unit 1 - Introduction", "lesson": "Introduction to Environmental Science", "page_start": 3, "page_end": 5},
    {"unit": "Unit 2 - Ecosystems and Biodiversity", "lesson": "Ecosystems and Biodiversity", "page_start": 6, "page_end": 8},
    {"unit": "Unit 3 - Natural Resources", "lesson": "Natural Resources", "page_start": 9, "page_end": 11},
    {"unit": "Unit 4 - Pollution and Waste", "lesson": "Pollution and Waste Management", "page_start": 12, "page_end": 14},
    {"unit": "Unit 5 - Climate and Sustainability", "lesson": "Climate Change and Sustainability", "page_start": 15, "page_end": 17},
    {"unit": "Reference", "lesson": "Glossary and Practice", "page_start": 18, "page_end": 19},
]


def build_course():
    """Delete any previous eval course and ingest the PDF fresh (repeatable)."""
    Course.objects.filter(name=COURSE_NAME, tenant_id=settings.DEMO_TENANT_ID).delete()
    course = Course.objects.create(
        name=COURSE_NAME,
        description="Rebuilt automatically by run_eval.py.",
        tenant_id=settings.DEMO_TENANT_ID,
    )
    print(f"Created course {course.id}")
    print("Ingesting the PDF (extract -> chunk -> embed -> store)...")
    summary = ingest_structured(
        str(course.id), PDF, OUTLINE,
        file_name="environmental-science-course.pdf", file_type="pdf",
    )
    print(f"  units built: {summary['materials_created']} | "
          f"chunks: {summary['chunks_created']} | pages: {summary['pages_processed']}")
    return course, summary


def ask_with_retry(course_id, question):
    """Call the real pipeline, retrying a couple of times on transient errors."""
    for attempt in range(3):
        try:
            return answer_question(course_id=course_id, question=question, top_k=TOP_K)
        except Exception as error:  # e.g. a rate-limit blip from the free tier
            if attempt == 2:
                raise
            print(f"    (retry after: {str(error)[:70]})")
            time.sleep(5 * (attempt + 1))


def key_term_hits(answer, keys):
    """How many expected key terms appear in the answer (case-insensitive).

    We strip markdown first, so a bolded first letter like **H**abitat still
    matches the key term 'habitat'.
    """
    low = re.sub(r"[*_`#>]", "", answer.lower())
    return [k for k in keys if k.lower() in low]


# The model, following its grounding prompt, sometimes refuses in words even when
# the hard score threshold let the chunks through. We count that as a refusal too,
# because to the student it IS a refusal (no made-up answer).
_REFUSAL_HINTS = (
    "cannot find", "could not find", "can only answer", "not in the provided",
    "do not have", "not explain", "not contain", "no information",
)


def looks_like_refusal(answer):
    low = answer.lower()
    return any(hint in low for hint in _REFUSAL_HINTS)


def main():
    course, ingest_summary = build_course()

    with open(EVAL_FILE, encoding="utf-8") as f:
        eval_data = json.load(f)
    questions = eval_data["questions"]

    print(f"\nRunning {len(questions)} questions through /ask ...\n")
    rows = []
    for i, q in enumerate(questions, start=1):
        res = ask_with_retry(str(course.id), q["question"])
        answer = res.get("answer", "")
        sources = res.get("sources", []) or []
        pages = [s.get("page") for s in sources]
        refused = bool(res.get("guardrail_triggered"))
        cat = q["category"]

        # --- retrieval (answerable only) ---
        retrieval_hit = None
        if cat == "answerable":
            expected = set(q.get("expected_pages", []))
            retrieval_hit = bool(expected & set(pages))

        # --- answer correctness (answerable, only if it actually answered) ---
        corr_ratio, corr_pass = None, None
        if cat == "answerable":
            keys = q.get("answer_key", [])
            if refused or not keys:
                corr_ratio, corr_pass = 0.0, False
            else:
                found = key_term_hits(answer, keys)
                corr_ratio = len(found) / len(keys)
                corr_pass = corr_ratio >= PASS_RATIO

        # --- guardrail decision correctness ---
        if cat == "answerable":
            guard_ok = not refused
        elif cat == "out_of_scope":
            guard_ok = refused
        else:  # smalltalk
            guard_ok = (not refused) and (answer.strip() == SMALLTALK_MESSAGE.strip())

        rows.append({
            "id": q["id"], "category": cat, "question": q["question"],
            "expected_pages": q.get("expected_pages", []), "retrieved_pages": pages,
            "retrieval_hit": retrieval_hit,
            "confidence": res.get("confidence"), "refused": refused,
            "effective_refused": refused or looks_like_refusal(answer),
            "correctness_ratio": corr_ratio, "correct": corr_pass,
            "guardrail_ok": guard_ok, "answer": answer,
        })

        mark = "HIT " if retrieval_hit else ("MISS" if retrieval_hit is False else "  - ")
        gflag = "OK" if guard_ok else "XX"
        cstr = f"{corr_ratio:.0%}" if corr_ratio is not None else "  -"
        print(f"[{i:2}/{len(questions)}] {q['id']:7} {cat:12} "
              f"exp={str(q.get('expected_pages', [])):10} got={str(pages):16} "
              f"{mark} corr={cstr:>4} guard={gflag} conf={(res.get('confidence') or 0):.2f}")
        time.sleep(SLEEP)

    # --- aggregate metrics ---
    answerable = [r for r in rows if r["category"] == "answerable"]
    oos = [r for r in rows if r["category"] == "out_of_scope"]
    smalltalk = [r for r in rows if r["category"] == "smalltalk"]

    n_ans = len(answerable)
    retr_hits = sum(1 for r in answerable if r["retrieval_hit"])
    corr_hits = sum(1 for r in answerable if r["correct"])
    ans_answered = sum(1 for r in answerable if not r["refused"])
    oos_refused = sum(1 for r in oos if r["refused"])
    oos_refused_eff = sum(1 for r in oos if r["effective_refused"])
    st_ok = sum(1 for r in smalltalk if r["guardrail_ok"])
    guard_correct = ans_answered + oos_refused
    guard_total = n_ans + len(oos)

    def pct(a, b):
        return f"{(100.0 * a / b):.1f}%" if b else "n/a"

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "course_id": str(course.id),
        "top_k": TOP_K, "pass_ratio": PASS_RATIO,
        "counts": {"answerable": n_ans, "out_of_scope": len(oos), "smalltalk": len(smalltalk)},
        "retrieval_at_k": {"hits": retr_hits, "total": n_ans, "pct": pct(retr_hits, n_ans)},
        "answer_correctness": {"passed": corr_hits, "total": n_ans, "pct": pct(corr_hits, n_ans)},
        "guardrail": {
            "answerable_answered": f"{ans_answered}/{n_ans}",
            "out_of_scope_refused_hard_flag": f"{oos_refused}/{len(oos)}",
            "out_of_scope_refused_effective": f"{oos_refused_eff}/{len(oos)}",
            "no_hallucination_pct": pct(oos_refused_eff, len(oos)),
            "overall": {"correct": guard_correct, "total": guard_total, "pct": pct(guard_correct, guard_total)},
            "smalltalk_handled": f"{st_ok}/{len(smalltalk)}",
        },
        "ingest": ingest_summary,
    }

    print("\n" + "=" * 62)
    print("  ASK MY COURSE - EVALUATION SUMMARY")
    print("=" * 62)
    print(f"  Retrieval@{TOP_K}         : {retr_hits}/{n_ans}  ({pct(retr_hits, n_ans)})")
    print(f"  Answer correctness  : {corr_hits}/{n_ans}  ({pct(corr_hits, n_ans)})")
    print(f"  Guardrail accuracy  : {guard_correct}/{guard_total}  ({pct(guard_correct, guard_total)})")
    print(f"     - answered real questions   : {ans_answered}/{n_ans}")
    print(f"     - refused out-of-scope ones : {oos_refused}/{len(oos)} (hard flag)")
    print(f"  No hallucination     : {oos_refused_eff}/{len(oos)}  ({pct(oos_refused_eff, len(oos))})")
    print(f"  Greeting handling   : {st_ok}/{len(smalltalk)}")
    print("=" * 62)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "questions": rows}, f, indent=2, ensure_ascii=False)
    print(f"\nFull breakdown written to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
