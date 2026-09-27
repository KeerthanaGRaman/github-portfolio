"""Scrape PRS India's Bills Track listing (no RSS feed exists for it -
see config/rss_feeds.yaml) and append new/changed bills to
data/processed/current_affairs/prs_bills.jsonl (deduped + updated by link).

Respects prsindia.org/robots.txt: a single request per run to the
public /billtrack listing (not a disallowed path), honouring its
Crawl-delay of 10s in case a future version needs multiple requests
(pagination, per-bill detail pages). Only title/status/link are stored -
no full-text reproduction of PRS's own analysis (copyright).

Usage:
    python scrape_prs.py [--out ../../data/processed/current_affairs/prs_bills.jsonl]
"""
import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

URL = "https://prsindia.org/billtrack"
CRAWL_DELAY_SECONDS = 10  # per robots.txt
USER_AGENT = "Mozilla/5.0 (compatible; upsc-adaptive-test-bot/1.0; educational data collection)"

ROW_RE = re.compile(
    r'<div class="views-row">\s*'
    r'<div class="views-field views-field-title-field">.*?'
    r'href="(?P<link>[^"]+)">(?P<title>[^<]+)</a>.*?'
    r'<div class="views-field views-field-field-bill-status">\s*<span[^>]*>(?P<status>[^<]*)</span>',
    re.S,
)


def fetch_html(url: str) -> str | None:
    result = subprocess.run(
        ["curl", "-sSL", "--max-time", "30", "-A", USER_AGENT, url],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def parse_bills(html: str) -> list[dict]:
    bills = []
    for m in ROW_RE.finditer(html):
        link = m.group("link")
        if not link.startswith("http"):
            link = "https://prsindia.org" + link
        bills.append({
            "title": m.group("title").strip(),
            "status": m.group("status").strip(),
            "link": link,
        })
    return bills


def load_existing(out_path: Path) -> dict[str, dict]:
    if not out_path.exists():
        return {}
    existing = {}
    with out_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                existing[rec["link"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return existing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent.parent.parent / "data" / "processed" / "current_affairs" / "prs_bills.jsonl"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html = fetch_html(URL)
    if html is None:
        print(f"ERROR: could not fetch {URL}")
        return
    time.sleep(CRAWL_DELAY_SECONDS)  # only one request this run, but keep the
                                      # pause reflexive for when this script grows

    bills = parse_bills(html)
    if not bills:
        print("WARN: parsed 0 bills - page structure may have changed")
        return

    existing = load_existing(out_path)
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    updated_count = 0

    for bill in bills:
        prior = existing.get(bill["link"])
        if prior is None:
            new_count += 1
        elif prior["status"] != bill["status"]:
            updated_count += 1
        else:
            continue  # unchanged, skip

        existing[bill["link"]] = {
            "source_id": "prs_india",
            "topic": "governance",
            "title": bill["title"],
            "status": bill["status"],
            "link": bill["link"],
            "language": "english",
            "confidence": "verified",
            "fetched_at": now,
        }

    with out_path.open("w", encoding="utf-8") as f:
        for rec in existing.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Scraped {len(bills)} bills: {new_count} new, {updated_count} status-updated -> {out_path}")


if __name__ == "__main__":
    main()
