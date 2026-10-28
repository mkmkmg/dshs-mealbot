#!/usr/bin/env python3
"""Daejeon Daeshin dinner feed: polite read-only cached fetch from Orya.ng.

Uses no logins, cookies, or hidden credentials. Requires public endpoint access.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API = 'https://orya.ng/api/meals'
DATA_FILE = Path(__file__).resolve().parents[1] / 'docs' / 'data' / 'meals.json'
KST = ZoneInfo('Asia/Seoul')
MAX_SINGLE_REQUESTS = 10
REQUEST_SPACING_SEC = 0.8


def fetch_json(params: dict[str, str] | None = None):
    url = API + ('?' + urlencode(params) if params else '')
    req = Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'DshsDinnerBot/2.0 (public meal lookup; no credentials)',
    })
    with urlopen(req, timeout=12) as res:
        if res.status != 200:
            raise ValueError(f'HTTP {res.status}')
        content_type = res.headers.get('Content-Type', '')
        if 'json' not in content_type:
            raise ValueError(f'Expected JSON, got {content_type}')
        payload = res.read(200_000)
    return json.loads(payload)


def normalize(obj: object, expected: date | None = None):
    """Reject malformed data, wrong-year results, and unnaturally large data."""
    if not isinstance(obj, dict):
        return None
    raw_date = obj.get('isoDate')
    if not isinstance(raw_date, str):
        return None
    try:
        parsed = date.fromisoformat(raw_date)
    except ValueError:
        return None
    if parsed.isoformat() != raw_date:
        return None
    if expected is not None and parsed != expected:
        return None

    def clean_menu(field):
        if field not in obj:
            return None
        value = obj[field]
        if not isinstance(value, list) or len(value) > 30:
            return None
        if not all(isinstance(x, str) and 0 < len(x.strip()) <= 160 for x in value):
            return None
        return [x.strip() for x in value]

    lunch = clean_menu('lunch')
    dinner = clean_menu('dinner')
    src = obj.get('dinnerSource')
    if not isinstance(src, str) or len(src) > 40:
        src = None
    return {
        'date': raw_date,
        'weekday': '월화수목금토일'[parsed.weekday()],
        'lunch': lunch,
        'dinner': dinner,
        'dinnerSource': src,
        # None means unknown, NOT "no dinner served"
        'dinnerStatus': 'listed' if dinner else 'not_provided',
    }


def collect(fetcher=fetch_json, today: date | None = None, sleep=time.sleep):
    today = today or datetime.now(KST).date()
    accepted: dict[str, dict] = {}
    errors: list[str] = []
    succeeded = 0

    # First query: the displayed weekly feed (often five school days).
    try:
        payload = fetcher()
        if not isinstance(payload, list):
            raise ValueError('Weekly endpoint did not return a list')
        succeeded += 1
        for item in payload:
            row = normalize(item)
            if row and today - timedelta(days=3) <= date.fromisoformat(row['date']) <= today + timedelta(days=12):
                accepted[row['date']] = row
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
        errors.append(f'Weekly endpoint error: {type(exc).__name__} (details withheld)')

    # Fill gaps near today and across the next month boundary; do not flood API.
    desired = [today + timedelta(days=i) for i in range(0, 11)]
    desired += [today - timedelta(days=i) for i in range(1, 3)]
    queried = 0
    for day in desired:
        if day.isoformat() in accepted or queried >= MAX_SINGLE_REQUESTS:
            continue
        # Avoid unnecessary weekend requests; service info may legitimately be absent.
        if day.weekday() >= 5:
            continue
        sleep(REQUEST_SPACING_SEC)
        queried += 1
        try:
            item = fetcher({'date': f'{day.month}/{day.day}'})
            succeeded += 1
            row = normalize(item, expected=day)
            if row:
                accepted[row['date']] = row
            else:
                errors.append(f'{day.isoformat()}: empty/invalid/other-year response')
        except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
            errors.append(f'{day.isoformat()}: {type(exc).__name__} (details withheld)')
            if isinstance(exc, HTTPError) and exc.code in (401, 403, 429):
                errors.append('Stopping further requests after authorization/rate-limit response')
                break

    if not accepted:
        raise RuntimeError('No verified date rows; refusing to publish an empty or misleading feed')

    updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    data = {
        'updatedAt': updated_at,
        'source': API,
        'timeZone': 'Asia/Seoul',
        'count': len(accepted),
        'days': sorted(accepted.values(), key=lambda x: x['date']),
        'partial': bool(errors),
        'notes': ['Unlisted dinner does not imply no dinner is served.'],
    }
    return data, errors, succeeded, queried


def main():
    try:
        data, errors, succeeded, queried = collect()
    except Exception as exc:
        print(f'ERROR: collection failed ({type(exc).__name__}); existing published data not modified', file=sys.stderr)
        return 1
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DATA_FILE.with_suffix('.tmp')
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp_path, DATA_FILE)
    print(f'Validated {len(data["days"])} dates; {succeeded} successful endpoint calls; {queried} per-date calls')
    if errors:
        for message in errors[:8]:
            print('WARNING:', message)
        if len(errors) > 8:
            print('WARNING: more errors omitted')
    print(f'Wrote {DATA_FILE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
