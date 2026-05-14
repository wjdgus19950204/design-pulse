"""수집한 디자인 뉴스를 Claude에게 보내 카테고리별로 정리."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 불러오기
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

CATEGORIES = [
    "UX/UI",
    "그래픽",
    "브랜딩",
    "타이포그래피",
    "제품",
    "모션/3D",
    "AI 도구",
]


SYSTEM_PROMPT = """너는 한국어 디자인 매거진 'Pulse'의 편집장이다.

전 세계 디자인 매체에서 수집한 한 주치 영문 기사 리스트를 받는다.
이걸 읽고 매주 월요일에 발행하는 매거진 한 호를 큐레이션해서 만든다.

작업 규칙:
1. 아래 7개 카테고리 각각에서 가장 의미 있는 기사 1편씩만 고른다.
   - UX/UI, 그래픽, 브랜딩, 타이포그래피, 제품, 모션/3D, AI 도구
2. 그중 한 주를 대표할 만한 가장 강력한 1편을 'cover'로 승격한다.
   (cover로 뽑힌 기사는 dispatches에서는 빠진다)
3. 모든 텍스트는 한국어로 새로 작성한다. 직역체가 아닌 매거진 톤으로.
   - 헤드라인: 짧고 단정하게. "에어비앤비, 12년 만의 첫 리브랜드. 반응은 갈렸다." 식.
   - 요약: 2-3문장. 핵심 사실 + 의미.
   - 커버 리드문: 한 문장. 매거진 표지 카피처럼.
4. 같은 주의 디자인 이벤트/컨퍼런스 언급이 있으면 events에 정리.
5. 출력은 반드시 아래 JSON 스키마를 따른다. 다른 설명, 마크다운, 코드블록 일절 금지.

출력 JSON 스키마:
{
  "issue_date": "YYYY-MM-DD",
  "cover": {
    "category": "카테고리명",
    "headline": "한국어 헤드라인",
    "lead": "리드문 한 줄",
    "summary": "2-3문장 요약",
    "source_url": "원문 URL",
    "source_name": "매체명",
    "image": "이미지 URL 또는 null"
  },
  "dispatches": [
    {
      "category": "카테고리명",
      "headline": "한국어 헤드라인",
      "summary": "2-3문장 요약",
      "source_url": "원문 URL",
      "source_name": "매체명",
      "image": "이미지 URL 또는 null"
    }
  ],
  "events": [
    {
      "date": "YYYY-MM-DD",
      "name": "이벤트명",
      "location": "도시명",
      "kind": "컨퍼런스|박람회|페스티벌|기타"
    }
  ],
  "weekly_summary": "한 주를 한 단락으로 요약 (3-4문장)."
}
"""


def load_latest_data():
    """가장 최근 raw-*.json 파일을 불러옴."""
    data_dir = ROOT / "data"
    files = sorted(data_dir.glob("raw-*.json"), reverse=True)
    if not files:
        print("❌ 수집된 데이터가 없습니다. 먼저 collect.py를 실행하세요.")
        sys.exit(1)
    latest = files[0]
    print(f"📂 데이터 파일: {latest.name}")
    return latest, json.loads(latest.read_text(encoding="utf-8"))


def trim_items_for_prompt(items, max_items=80):
    """Claude에게 보내기 위해 항목을 정리하고 갯수 제한."""
    trimmed = []
    for it in items[:max_items]:
        trimmed.append({
            "source": it["source"],
            "category_hint": it["category_hint"],
            "title": it["title"],
            "url": it["url"],
            "summary": it["summary"][:300],
            "image": it["image"],
            "published": it["published"][:10],
        })
    return trimmed


def call_claude(items):
    """Claude API 호출."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY가 .env에 없습니다.")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    today = datetime.now().strftime("%Y-%m-%d")
    
    user_message = f"""오늘은 {today}. 지난 7일치 디자인 뉴스 {len(items)}건이다.

```json
{json.dumps(items, ensure_ascii=False, indent=2)}
```

위 데이터를 읽고 매거진 한 호를 큐레이션해서 JSON으로만 응답해라.
issue_date는 {today}로 한다."""

    print(f"🤖 Claude 호출 중 (입력 {len(items)}건)…")
    
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    
    text = response.content[0].text.strip()
    # 혹시 코드블록으로 감싸져 있으면 벗기기
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    
    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"❌ Claude 응답이 JSON이 아님: {e}")
        print("응답 원문:")
        print(text[:1000])
        sys.exit(1)
    
    print(f"✅ 큐레이션 완료 (cover 1 + dispatches {len(result.get('dispatches', []))}개)")
    return result


def main():
    print("\n📰 매거진 큐레이션 시작\n")
    
    _, raw_items = load_latest_data()
    print(f"📦 수집된 기사: {len(raw_items)}건")
    
    items = trim_items_for_prompt(raw_items)
    issue = call_claude(items)
    
    out_dir = ROOT / "data"
    timestamp = datetime.now().strftime("%Y-%m-%d")
    out_file = out_dir / f"issue-{timestamp}.json"
    out_file.write_text(
        json.dumps(issue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"💾 저장: {out_file}\n")
    
    # 미리보기
    print("─" * 60)
    print(f"📰 커버: {issue['cover']['headline']}")
    print(f"   ({issue['cover']['category']} · {issue['cover']['source_name']})")
    print("─" * 60)
    for d in issue.get("dispatches", []):
        print(f"  · [{d['category']}] {d['headline']}")
    print()


if __name__ == "__main__":
    main()