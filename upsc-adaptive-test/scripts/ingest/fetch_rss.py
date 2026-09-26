"""Pull entries from configured RSS feeds and append new ones to
data/processed/current_affairs/feed_items.jsonl (deduped by link).

Usage:
    python fetch_rss.py [--config ../../config/rss_feeds.yaml] [--out ../../data/processed/current_affairs/feed_items.jsonl]

Intended to run on a schedule (daily) via cron / GitHub Actions.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import yaml


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
        parsed = feedparser.parse(feed_cfg["url"])
        if parsed.bozo:
            print(f"WARN: could not parse feed {feed_cfg['id']} ({feed_cfg['url']}): {parsed.bozo_exception}")
            continue

        for entry in parsed.entries:
            link = entry.get("link")
            if not link or link in seen:
                continue
            new_items.append({
                "feed_id": feed_cfg["id"],
                "topic": feed_cfg.get("default_topic", "current_affairs"),
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": link,
                "published": entry.get("published", ""),
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
