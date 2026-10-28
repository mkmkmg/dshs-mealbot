#!/usr/bin/env python3
"""Publish readable, static Korean meal pages for link-preview and chat bots.

Reads the verified snapshot produced by scripts/collect.py. It does not contact
other services or require credentials. HTML escapes all external menu text.
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'docs' / 'data' / 'meals.json'
DOCS = ROOT / 'docs'
KST = ZoneInfo('Asia/Seoul')


def format_day(day: date) -> str:
    return f'{day.year}년 {day.month}월 {day.day}일 ({"월화수목금토일"[day.weekday()]})'


def get_meal(day: date, records: dict[str, dict]) -> tuple[list[str] | None, str]:
    item = records.get(day.isoformat())
    if item is None or not isinstance(item.get('dinner'), list) or not item['dinner']:
        return None, '석식 정보가 아직 확인되지 않았습니다. 급식 미운영으로 확정된 것은 아닙니다.'
    return [str(v) for v in item['dinner']], ''


def make_text(day: date, records: dict[str, dict], verified_at: str) -> str:
    menus, absent = get_meal(day, records)
    lines = [f'대전대신고 석식 — {format_day(day)}', '']
    if menus:
        lines.extend('- ' + name for name in menus)
    else:
        lines.append(absent)
    lines += ['', f'데이터 확인 시각(UTC): {verified_at or "미확인"}', '출처: 오량인 공개 급식 데이터',
              '메뉴는 변경될 수 있으므로 학교 공지도 확인하세요.']
    return '\n'.join(lines) + '\n'


def make_html(day: date, records: dict[str, dict], verified_at: str, descriptor: str) -> str:
    menus, absent = get_meal(day, records)
    title = f'{format_day(day)} 대전대신고 {descriptor} 석식'
    title_esc = html.escape(title, quote=True)
    plain = make_text(day, records, verified_at).strip()
    desc = html.escape(' | '.join(menus) if menus else absent, quote=True)
    if menus:
        meal_html = '<ul>' + '\n'.join('<li>' + html.escape(menu) + '</li>' for menu in menus) + '</ul>'
    else:
        meal_html = '<p class="missing">' + html.escape(absent) + '</p>'
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="index,follow">
<meta name="description" content="{desc}">
<meta http-equiv="cache-control" content="no-cache">
<title>{title_esc}</title>
<style>
body {{font-family:system-ui,-apple-system,sans-serif;background:#f6f8fc;color:#172238;margin:0;padding:24px}}
main {{max-width:640px;margin:20px auto;background:#fff;border:1px solid #e1e7f0;border-radius:18px;padding:26px;line-height:1.85}}
h1 {{font-size:1.42rem;line-height:1.4}} li {{margin:6px 0}} .muted {{color:#58677a;font-size:.9rem}} .missing {{background:#fff6e6;padding:12px;border-radius:10px}}
a {{color:#2059bd}}
</style>
</head>
<body><main>
<p class="muted">DAESHIN DINNER · 자동 갱신 급식 조회</p>
<h1>{title_esc}</h1>
{meal_html}
<p class="muted">데이터 확인 시각(UTC): {html.escape(verified_at or '미확인')}</p>
<p class="muted">출처: 오량인 공개 급식 데이터 · 메뉴는 변경될 수 있습니다.</p>
<p><a href="./">전체 급식 조회 페이지</a></p>
<!-- Bot-readable text (the visible HTML above is the authoritative content):
{html.escape(plain)}
-->
</main></body></html>
'''


def publish(today: date | None = None, docs: Path = DOCS, data_file: Path = DATA_PATH):
    today = today or datetime.now(KST).date()
    data = json.loads(data_file.read_text(encoding='utf-8'))
    records = {r['date']: r for r in data.get('days', []) if isinstance(r, dict) and isinstance(r.get('date'), str)}
    updated = data.get('updatedAt') or ''
    for suffix, day, descriptor in [('today', today, '오늘'), ('tomorrow', today + timedelta(days=1), '내일')]:
        (docs / f'kakao-{suffix}.html').write_text(make_html(day, records, updated, descriptor), encoding='utf-8')
        (docs / f'kakao-{suffix}.txt').write_text(make_text(day, records, updated), encoding='utf-8')
    week_start = today - timedelta(days=today.weekday())
    sections = [make_text(week_start + timedelta(days=i), records, updated) for i in range(5)]
    week_text = '\n'.join(sections)
    (docs / 'kakao-week.txt').write_text(week_text, encoding='utf-8')
    week_html = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>대신고 이번 주 석식</title>' + \
      '<body style="font-family:system-ui;line-height:1.7;max-width:740px;margin:40px auto;padding:12px">' + \
      '<h1>대전대신고 이번 주 석식</h1><pre style="white-space:pre-wrap;font:inherit">' + \
      html.escape(week_text) + '</pre><p><a href="./">급식 조회</a></p></body></html>'
    (docs / 'kakao-week.html').write_text(week_html, encoding='utf-8')
    print('Published static pages: today, tomorrow, week | date:', today.isoformat())


if __name__ == '__main__':
    publish()
