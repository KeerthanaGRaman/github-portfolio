"""Merge a bare answer-key text file ("1.B 2.B 3.D ...") into a parsed
questions JSON file.

Answers are matched by POSITION in the key (1st printed answer = Q1,
2nd = Q2, ...), not by trusting the printed number label. PDF text
extraction can drop a digit (we found "143.B" rendered as "13.B" in
the GIAS answer key) - position is more robust than the label to that
kind of one-off OCR/extraction glitch, as long as the key is otherwise
strictly sequential (this script checks that and warns if it isn't).

Only use this once you've confirmed which question set an answer key
actually belongs to (see config/sources.yaml notes on orphaned keys).
For the GIAS set specifically: the key has exactly 250 answers, and
the parsed questions independently span a single continuous 1-250
numbering across all 5 topics (polity 1-50, economy 51-100, geography
101-140, environment 141-200, history 201-250) - that structural match
is what makes this key trustworthy for this question set.

Usage:
    python merge_answer_key.py <questions.json> <answer_key.txt> \
        --output <merged.json>
"""
import argparse
import json
import re
from pathlib import Path

ANSWER_RE = re.compile(r"(\d{1,4})\.\s*([A-Da-d])")


def load_answer_key(path: str) -> dict[int, str]:
    """Return {position: answer_letter}, position being 1-indexed order
    of appearance in the key - NOT the printed number label."""
    text = Path(path).read_text(encoding="utf-8")
    matches = ANSWER_RE.findall(text)

    answers = {}
    for position, (label, letter) in enumerate(matches, start=1):
        if int(label) != position:
            print(f"NOTE: position {position} printed as '{label}.{letter}' "
                  f"(label != position) - trusting position, not the label")
        answers[position] = letter.lower()
    return answers


def merge(questions_path: str, answers: dict[int, str], output: str):
    records = json.loads(Path(questions_path).read_text(encoding="utf-8"))
    matched = 0
    for r in records:
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
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    answers = load_answer_key(args.answer_key_txt)
    merge(args.questions_json, answers, args.output)


if __name__ == "__main__":
    main()
