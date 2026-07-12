#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""要綱PDFを特定して本文抽出できるか実地検証。ページ→PDFリンク(アンカー文言つき)→要綱らしいPDFを抽出。"""
import sys, re, io, urllib.request, urllib.parse
import pypdf

UA = "CaresilBot/0.1 (+contact)"
KEY = re.compile(r"要綱|要領|募集|交付|チラシ|概要|手引|一覧|Q&A|ちらし")
SNIP = re.compile(r".{0,30}(補助率|補助基準額|上限|分の\d|[0-9,]+万円|締切|期限|必着|申請期間).{0,40}")

def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read() if binary else r.read()

def pdf_links(page_url):
    html = get(page_url).decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        anchor = re.sub(r"<[^>]+>", "", m.group(2)).strip()[:40]
        out.append((urllib.parse.urljoin(page_url, m.group(1)), anchor))
    return out

def pdf_text(url):
    data = get(url, binary=True)
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:8])

def main():
    page = sys.argv[1]
    links = pdf_links(page)
    print(f"PDF {len(links)}本検出:")
    for u, a in links[:12]:
        mark = "★要綱候補" if KEY.search(a) or KEY.search(u) else ""
        print(f"  {mark:8} {a or '(無題)':20} {u.split('/')[-1]}")
    target = next((u for u, a in links if KEY.search(a) or KEY.search(u)), links[0][0] if links else None)
    if not target:
        print("PDFなし"); return
    print(f"\n▼抽出対象: {target}")
    try:
        txt = re.sub(r"\s+", " ", pdf_text(target))
    except Exception as e:
        print("抽出失敗:", type(e).__name__, e); return
    print(f"本文 {len(txt)} 文字。関連スニペット:")
    seen = set()
    for m in SNIP.finditer(txt):
        s = m.group(0).strip()
        if s not in seen:
            seen.add(s); print("   …", s)
        if len(seen) >= 12: break

if __name__ == "__main__":
    main()
