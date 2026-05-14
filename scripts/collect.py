"""지난 7일치 디자인 뉴스를 8개 매체에서 수집."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
from dateutil import parser as date_parser

from feeds import FEEDS

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def parse_date(entry):
    """RSS 항목에서 발행일을 추출. 매체마다 필드명이 다름."""
    for key in ("published", "updated", "created"):
        if key in entry:
            try:
                return date_parser.parse(entry[key])
            except (ValueError, TypeError):
                continue
    return None


def clean_summary(text, max_len=400):
    """HTML 태그 거칠게 제거 + 길이 제한."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def extract_image(entry):
    """RSS 항목에서 대표 이미지 URL 추출 시도."""
    if "media_content" in entry and entry.media_content:
        return entry.media_content[0].get("url")
    if "media_thumbnail" in entry and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    if "enclosures" in entry and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href") or enc.get("url")
    summary = entry.get("summary", "") or entry.get("description", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)', summary)
    if match:
        return match.group(1)
    return None


def collect_feed(feed_info, days=7):
    """단일 피드에서 지난 N일치 항목 수집."""
    print(f"  📡 {feed_info['name']:25s} … ", end="", flush=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = []

    try:
        parsed = feedparser.parse(feed_info["url"], agent=USER_AGENT)
        if parsed.bozo and not parsed.entries:
            print(f"❌ 파싱 실패: {parsed.bozo_exception}")
            return items

        for entry in parsed.entries:
            pub_date = parse_date(entry)
            if pub_date is None:
                continue
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            if pub_date < cutoff:
                continue

            items.append({
                "source": feed_info["name"],
                "category_hint": feed_info["category_hint"],
                "title": entry.get("title", "").strip(),
                "url": entry.get("link", ""),
                "summary": clean_summary(
                    entry.get("summary", "") or entry.get("description", "")
                ),
                "image": extract_image(entry),
                "published": pub_date.isoformat(),
            })
        print(f"✓ {len(items)}건")
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")

    return items


def main():
    print("\n🔍 RSS 피드 수집 시작 (지난 7일치)\n")
    all_items = []
    for feed in FEEDS:
        all_items.extend(collect_feed(feed))

    print(f"\n📦 총 {len(all_items)}건 수집 완료")

    all_items.sort(key=lambda x: x["published"], reverse=True)

    out_path = Path(__file__).parent.parent / "data"
    out_path.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    out_file = out_path / f"raw-{timestamp}.json"
    out_file.write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"💾 저장: {out_file}\n")


if __name__ == "__main__":
    main()