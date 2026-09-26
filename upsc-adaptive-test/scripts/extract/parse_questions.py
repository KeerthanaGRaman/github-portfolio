"""Parse a plain-text MCQ dump (produced by pdf_to_text.py) into structured
JSON records.

Assumes the common UPSC/coaching-compilation layout:
    - Section headers are standalone ALL-CAPS lines (e.g. "POLITY QUESTIONS")
    - Questions start with "<number>." at the start of a line
    - Options are "(a) ... (b) ... (c) ... (d) ..." somewhere after the
      question stem (may be split across lines)

This is a best-effort layout parser tuned to the sample files in
data/raw/unverified/. Re-check output by hand before trusting it, since
line-wrapping in source PDFs varies.

Usage:
    python parse_questions.py <input.txt> <output.json> \
        --source-id upsc_questions_compiled --confidence unverified
"""
import argparse
import json
import re
from pathlib import Path

SECTION_RE = re.compile(r"^([A-Z][A-Z /]{4,40})$")
QSTART_RE = re.compile(r"^(\d{1,4})\.\s*(.*)")
# Matches an option TAG only: "(a)".."(d)" preceded by whitespace/start so it
# doesn't fire on a stray "(a)" embedded mid-word. Option VALUES are allowed
# to contain their own parentheses (e.g. "Constitution (Ninetieth Amendment)
# Act") -- we split on tag positions rather than excluding "()" from values.
OPTION_TAG_RE = re.compile(r"(?:^|(?<=\s))\(([a-dA-D])\)\s*")


def split_options(text: str) -> list[tuple[str, str]]:
    """Split text on option tags, returning [(letter, value), ...] in order."""
    tags = list(OPTION_TAG_RE.finditer(text))
    options = []
    for i, m in enumerate(tags):
        start = m.end()
        end = tags[i + 1].start() if i + 1 < len(tags) else len(text)
        options.append((m.group(1).lower(), text[start:end].strip()))
    return options

# Map raw section header text -> taxonomy topic id (see config/syllabus_taxonomy.yaml)
SECTION_TO_TOPIC = {
    "POLITY QUESTIONS": "polity",
    "POLITY": "polity",
    "ECONOMY": "economy",
    "GEOGRAPHY": "geography",
    "ENVIRONMENT": "environment",
    "HISTORY": "history",
    "SCIENCE": "science_tech",
    "CURRENT AFFAIRS": "current_affairs",
}


def parse(text: str, source_id: str, confidence: str) -> list[dict]:
    lines = [l.rstrip() for l in text.splitlines() if not l.startswith("--- page")]

    records = []
    current_section = None
    buf = []
    q_num = None

    def flush():
        nonlocal buf, q_num
        if q_num is None or not buf:
            buf = []
            return
        block = " ".join(buf).strip()
        options = split_options(block)
        first_tag = OPTION_TAG_RE.search(block)
        stem = block[:first_tag.start()].strip() if first_tag else block.strip()

        records.append({
            "question_number": q_num,
            "topic": SECTION_TO_TOPIC.get(current_section, "unmapped"),
            "raw_section": current_section,
            "question": stem,
            "options": {letter: val for letter, val in options},
            "answer": None,  # filled in later by merge_answer_key.py
            "source_id": source_id,
            "confidence": confidence,
        })
        buf = []
        q_num = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        sec_match = SECTION_RE.match(stripped)
        if sec_match and sec_match.group(1) in SECTION_TO_TOPIC:
            flush()
            current_section = sec_match.group(1)
            continue

        q_match = QSTART_RE.match(stripped)
        if q_match:
            candidate_num = int(q_match.group(1))
            # Treat this as a new question boundary only if the number
            # increases AND the question being built already has its 4
            # options (i.e. it looks structurally complete). Otherwise
            # it's a numbered sub-item inside a "Consider the following
            # statements: 1. ... 2. ... 3. ..." block.
            #
            # We deliberately use "> q_num" rather than "== q_num + 1":
            # the strict +1 check can never recover once a single
            # transition is missed (e.g. an odd option-tag layout), since
            # q_num then stays frozen and no later number can ever equal
            # frozen+1 again. ">" self-heals after an occasional miss,
            # at the cost of only rejecting sub-items smaller than q_num
            # (fine in practice, since sub-item lists restart at 1/2/3).
            current_text = " ".join(buf)
            looks_complete = len(split_options(current_text)) >= 4
            is_new_question = q_num is None or (candidate_num > q_num and looks_complete)
            if is_new_question:
                flush()
                q_num = candidate_num
                buf = [q_match.group(2)]
            else:
                buf.append(stripped)
            continue

        if q_num is not None:
            buf.append(stripped)

    flush()
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_txt")
    ap.add_argument("output_json")
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--confidence", choices=["verified", "unverified"], required=True)
    args = ap.parse_args()

    text = Path(args.input_txt).read_text(encoding="utf-8")
    records = parse(text, args.source_id, args.confidence)

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Parsed {len(records)} questions -> {out_path}")


if __name__ == "__main__":
    main()
