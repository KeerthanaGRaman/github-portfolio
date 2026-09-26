"""Merge a bare answer-key text file ("1.B 2.B 3.D ...") into a
parsed questions JSON file, matched by question_number within a section.

Only use this once you've confirmed which question set an answer key
actually belongs to (see config/sources.yaml notes on orphaned keys).

Usage:
    python merge_answer_key.py <questions.json> <answer_key.txt> \
        --section polity --output <merged.json>
"""
import argparse
import json
import re
from pathlib import Path

ANSWER_RE = re.compile(r"(\d{1,4})\.\s*([A-Da-d])")


def load_answer_key(path: str) -> dict[int, str]:
    text = Path(path).read_text(encoding="utf-8")
    return {int(num): letter.lower() for num, letter in ANSWER_RE.findall(text)}


def merge(questions_path: str, answers: dict[int, str], section: str | None, output: str):
    records = json.loads(Path(questions_path).read_text(encoding="utf-8"))
    matched = 0
    for r in records:
        if section and r.get("raw_section") and r["raw_section"].lower() != section.lower():
            continue
        ans = answers.get(r["question_number"])
        if ans:
            r["answer"] = ans
            matched += 1

    Path(output).write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Matched {matched}/{len(records)} questions with answers -> {output}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("questions_json")
    ap.add_argument("answer_key_txt")
    ap.add_argument("--section", help="Only apply to questions from this raw_section")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    answers = load_answer_key(args.answer_key_txt)
    merge(args.questions_json, answers, args.section, args.output)


if __name__ == "__main__":
    main()
