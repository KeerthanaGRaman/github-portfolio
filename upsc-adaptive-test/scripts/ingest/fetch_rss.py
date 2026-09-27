"""Pull entries from configured RSS feeds and append new ones to
data/processed/current_affairs/feed_items.jsonl (deduped by link).

Usage:
    python fetch_rss.py [--config ../../config/rss_feeds.yaml] [--out ../../data/processed/current_affairs/feed_items.jsonl]

Intended to run on a schedule (daily) via cron / GitHub Actions.
"""
import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import yaml

# Some govt feeds (PIB in particular) reset the TLS connection roughly
# 1 in 3 attempts, server-side. Fetch raw bytes via curl with retries
# rather than relying on feedparser's own (retry-less) HTTP client.
MAX_RETRIES = 4
RETRY_DELAY_SECONDS = 3


def fetch_bytes(url: str) -> bytes | None:
    for attempt in range(1, MAX_RETRIES + 1):
        result = subprocess.run(
            ["curl", "-sSL", "--max-time", "20", url],
            capture_output=True,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)
    return None


def detect_script(text: str) -> str:
    """Rough language-script tag: most govt feeds mix Hindi/English
    items regardless of any Lang param, so we tag per-item rather than
    trusting the feed's declared language."""
    devanagari = len(re.findall(r"[ऀ-ॿ]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if devanagari > latin:
        return "hindi"
    if latin > 0:
        return "english"
    return "unknown"


def load_seen_links(out_path: Path) -> set[str]:
    if not out_path.exists():
        return set()
    seen = set()
    with out_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                seen.add(json.loads(line)["link"])
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


def fetch(config_path: str, out_path: str):
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = load_seen_links(out_path)

    new_items = []
    for feed_cfg in config["feeds"]:
        raw = fetch_bytes(feed_cfg["url"])
        if raw is None:
            print(f"WARN: could not reach feed {feed_cfg['id']} ({feed_cfg['url']}) after {MAX_RETRIES} attempts")
            continue

        parsed = feedparser.parse(raw)
        if parsed.bozo and not parsed.entries:
            print(f"WARN: could not parse feed {feed_cfg['id']} ({feed_cfg['url']}): {parsed.bozo_exception}")
            continue

        for entry in parsed.entries:
            link = entry.get("link")
            if not link or link in seen:
                continue
            title = entry.get("title", "")
            new_items.append({
                "feed_id": feed_cfg["id"],
                "topic": feed_cfg.get("default_topic", "current_affairs"),
                "title": title,
                "summary": entry.get("summary", ""),
                "link": link,
                "published": entry.get("published", ""),
                "language": detect_script(title),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "confidence": "verified",
            })
            seen.add(link)

    if new_items:
        with out_path.open("a", encoding="utf-8") as f:
            for item in new_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Fetched {len(new_items)} new items -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(Path(__file__).parent.parent.parent / "config" / "rss_feeds.yaml"))
    ap.add_argument("--out", default=str(Path(__file__).parent.parent.parent / "data" / "processed" / "current_affairs" / "feed_items.jsonl"))
    args = ap.parse_args()
    fetch(args.config, args.out)
