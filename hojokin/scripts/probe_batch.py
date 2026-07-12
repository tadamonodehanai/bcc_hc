#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF内数値の県を一括抽出。ページ→要綱/手引きPDF特定→pypdf→補助率/上限スニペット表示。"""
import os, re, time, importlib.util

BASE = os.path.dirname(os.path.dirname(__file__))
def _load(mod, path):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(BASE, "scripts", path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
CR = _load("crawler", "crawler.py")

TARGETS = [
 ("P-32 島根", "https://www.pref.shimane.lg.jp/medical/fukushi/kourei/kaigo_hoken/hojokin/kaigo-tech.html"),
 ("P-10 群馬", "https://www.pref.gunma.jp/site/kaigojinzai/2301.html"),
 ("P-30 和歌山", "https://www.pref.wakayama.lg.jp/prefg/040300/d00201773.html"),
 ("P-42 長崎", "https://www.pref.nagasaki.jp/doc/48428.html"),
 ("P-09 栃木", "https://www.pref.tochigi.lg.jp/e03/r8kaigotechnologyhojokin.html"),
 ("P-33 岡山", "https://www.pref.okayama.jp/page/1041750.html"),
 ("P-43 熊本", "https://www.pref.kumamoto.jp/soshiki/32/269614.html"),
 ("P-13 東京", "https://www.fukushizaidan.jp/206genbakaikaku/jisedai/"),
]
SNIP = re.compile(r".{0,30}(補助率|基準額|上限|分の\s?\d|[0-9,，]+万円|[0-9,，]+千円).{0,45}")
NOISE = re.compile(r"消費税|端数|振込|口座|様式第|証拠書類")

for name, url in TARGETS:
    print(f"\n━━ {name}")
    html, err = CR.fetch(url)
    if not html:
        print("   取得失敗:", err); continue
    links = CR.find_pdf_links(html, url)
    youkou = CR.pick_youkou(links)
    if not youkou:
        print("   PDFリンクなし"); continue
    print("   要綱候補:", youkou.split("/")[-1][:60])
    txt = CR.pdf_text(youkou, max_pages=10)
    txt = re.sub(r"\s+", " ", txt)
    if not txt:
        print("   PDF抽出失敗(画像PDF等)"); continue
    seen = set()
    hits = 0
    for m in SNIP.finditer(txt):
        s = m.group(0).strip()
        if s in seen or NOISE.search(s): continue
        seen.add(s); hits += 1
        print("    …", s[:105])
        if hits >= 8: break
    if hits == 0:
        print("   数値スニペットなし")
    time.sleep(1.0)
