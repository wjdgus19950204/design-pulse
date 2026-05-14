"""issue-*.json 데이터를 HTML 매거진으로 렌더링."""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent.parent


def load_latest_issue():
    data_dir = ROOT / "data"
    files = sorted(data_dir.glob("issue-*.json"), reverse=True)
    if not files:
        print("❌ 큐레이션된 데이터가 없습니다. 먼저 curate.py를 실행하세요.")
        sys.exit(1)
    latest = files[0]
    print(f"📂 데이터: {latest.name}")
    return latest, json.loads(latest.read_text(encoding="utf-8"))


def main():
    print("\n🎨 매거진 렌더링 시작\n")
    
    src, issue = load_latest_issue()
    
    # Jinja2 환경 세팅
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=True,
    )
    template = env.get_template("issue.html")
    
    html = template.render(issue=issue)
    
    # 1) docs/index.html (최신호로 항상 갱신)
    docs_dir = ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    index_file = docs_dir / "index.html"
    index_file.write_text(html, encoding="utf-8")
    print(f"✅ 최신호: {index_file.relative_to(ROOT)}")
    
    # 2) docs/issues/YYYY-MM-DD.html (아카이브용 영구 링크)
    issues_dir = docs_dir / "issues"
    issues_dir.mkdir(exist_ok=True)
    issue_file = issues_dir / f"{issue['issue_date']}.html"
    issue_file.write_text(html, encoding="utf-8")
    print(f"✅ 아카이브: {issue_file.relative_to(ROOT)}")
    
    print(f"\n🌐 브라우저에서 확인:")
    print(f"   open {index_file}\n")


if __name__ == "__main__":
    main()