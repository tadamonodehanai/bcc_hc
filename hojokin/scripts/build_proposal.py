#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""支援者が施設に渡す「補助金 活用提案書」を生成（印刷/PDF保存用の1枚）。
公開_制度.json から、選んだ制度IDと施設情報で teian.html を生成する。
  python3 scripts/build_proposal.py --facility "○○特養" --pref 東京都 --ids G-01,G-02,P-13,M-01
ブラウザで開き「印刷→PDFに保存」で配布用PDFになる。"""
import os, re, json, argparse, datetime

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "teian.html")
TODAY = datetime.date.today()
LVCLS = {"国": "国", "都道府県": "都道府県", "市区町村": "市区町村"}

def esc(s): return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def days_left(d):
    if not d: return None
    try: return (datetime.date.fromisoformat(d) - TODAY).days
    except ValueError: return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facility", default="サンプル介護施設")
    ap.add_argument("--pref", default="東京都")
    ap.add_argument("--support", default="ただものコンサルティング／田中")
    ap.add_argument("--ids", default="G-01,G-02,P-13,M-01")
    args = ap.parse_args()

    S = {r["id"]: r for r in json.load(open(os.path.join(DATA, "公開_制度.json"), encoding="utf-8"))}
    ids = [i for i in args.ids.split(",") if i]
    items = [S[i] for i in ids if i in S]
    # 実施主体レベル順に並べる
    order = {"国": 0, "都道府県": 1, "市区町村": 2}
    items.sort(key=lambda r: order.get(r["実施主体レベル"], 9))

    total = sum((r["補助上限"].get("金額_円") or 0) for r in items)
    has_null = any((r["補助上限"].get("金額_円") is None) for r in items)
    from collections import Counter
    lv = Counter(r["実施主体レベル"] for r in items)

    cards = []
    for r in items:
        dl = days_left(r["締切"])
        dl_s = f"（あと{dl}日）" if dl is not None and dl >= 0 else ""
        conf = {"高": "確認済", "中": "概要確認", "要確認": "詳細確認中"}.get(r["確度"], r["確度"])
        eqs = "・".join(  # 機器名は表示簡略化（IDのまま）
            r["対象機器タグ"][:6]) + (" ほか" if len(r["対象機器タグ"]) > 6 else "")
        cards.append(f"""
      <div class="pc">
        <div class="pc-h">
          <span class="lv lv-{LVCLS[r['実施主体レベル']]}">{esc(r['実施主体レベル'])}</span>
          <span class="gov">{esc(r['自治体名'])}</span>
          <span class="ttl">{esc(r['制度名'])}</span>
          <span class="st st-{'open' if r['受付状況']=='受付中' else 'oth'}">{esc(r['受付状況'])}</span>
        </div>
        <div class="pc-g">
          <div><label>補助率</label><b>{esc(r['補助率'].get('表示') or '—')}</b></div>
          <div><label>補助上限</label><b>{esc(r['補助上限'].get('表示') or '—')}</b></div>
          <div><label>締切</label><b>{esc(r['締切'] or '未定')} <span class="cd">{dl_s}</span></b></div>
          <div><label>対象施設</label><b>{esc('・'.join(r['対象施設']))}</b></div>
        </div>
        <div class="pc-f">
          <span class="conf">{esc(conf)}</span>
          <span class="eq">対象機器: {esc(eqs or '—')}</span>
          <a href="{esc(r['出典']['公式URL'])}">出典（公式ページ）</a>
        </div>
      </div>""")

    parts = "＋".join(f"{k}{lv[k]}" for k in ["国", "都道府県", "市区町村"] if lv[k])
    total_s = f"{total:,}円" + ("〜（数値確定分の合計。—は要綱で要確認）" if has_null else "")
    html = f"""<meta charset="utf-8">
<title>補助金 活用提案書｜{esc(args.facility)}</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  :root{{--navy:#0F2540;--teal:#12B3AE;--teal-d:#0E9490;--teal-soft:#E6F7F6;--line:#D9E1EA;--muted:#6B7A8D;--ok:#1E9E6A;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:#eef2f6;color:#1b2a3a;font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP",system-ui,sans-serif;}}
  .sheet{{max-width:794px;margin:16px auto;background:#fff;padding:26px 30px;box-shadow:0 6px 24px rgba(15,37,64,.12);}}
  .print{{max-width:794px;margin:0 auto;text-align:right}}
  .print button{{border:0;background:var(--teal);color:#fff;font-weight:800;padding:9px 16px;border-radius:9px;cursor:pointer}}
  .h{{display:flex;align-items:flex-end;gap:12px;border-bottom:3px solid var(--navy);padding-bottom:10px}}
  .h .mk{{width:32px;height:32px;border-radius:8px;background:var(--teal);display:grid;place-items:center;font-size:17px}}
  .h h1{{font-size:19px;margin:0;color:var(--navy)}} .h small{{color:var(--muted);font-size:11px;letter-spacing:.1em}}
  .meta{{margin-left:auto;text-align:right;font-size:12px;color:var(--muted);line-height:1.7}}
  .meta b{{color:var(--navy)}}
  .lead{{margin:14px 0;font-size:13px;color:#2b3a4a}}
  .sum{{display:flex;gap:14px;background:var(--teal-soft);border:1px solid #cdeae8;border-radius:12px;padding:12px 16px;margin-bottom:16px}}
  .sum .b{{flex:1}} .sum label{{display:block;font-size:11px;color:var(--muted)}} .sum b{{font-size:17px;color:var(--navy)}}
  .pc{{border:1px solid var(--line);border-radius:11px;padding:12px 14px;margin-bottom:11px;break-inside:avoid}}
  .pc-h{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
  .lv{{font-size:10.5px;font-weight:800;padding:3px 8px;border-radius:6px}}
  .lv-国{{background:#EAF0FB;color:#274b8f}} .lv-都道府県{{background:#EEF1F5;color:#516481}} .lv-市区町村{{background:var(--teal-soft);color:var(--teal-d)}}
  .gov{{font-size:11px;font-weight:700;color:var(--navy);background:#F1F4F8;padding:3px 8px;border-radius:6px}}
  .ttl{{font-weight:800;color:var(--navy);font-size:14px}}
  .st{{margin-left:auto;font-size:11px;font-weight:800;padding:3px 9px;border-radius:999px}}
  .st-open{{background:#E7F5EE;color:var(--ok)}} .st-oth{{background:#EEF1F5;color:var(--muted)}}
  .pc-g{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0;padding:9px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
  .pc-g label{{display:block;font-size:10px;color:var(--muted)}} .pc-g b{{font-size:13px;color:var(--navy)}} .cd{{color:#E8873B;font-weight:800}}
  .pc-f{{display:flex;gap:10px;align-items:center;font-size:11px;color:var(--muted)}}
  .conf{{font-weight:800;color:var(--teal-d);background:var(--teal-soft);padding:2px 8px;border-radius:6px}}
  .pc-f .eq{{flex:1}} .pc-f a{{color:var(--teal-d);font-weight:700;text-decoration:none}}
  .note{{margin-top:16px;font-size:10.5px;color:var(--muted);line-height:1.7;border-top:1px solid var(--line);padding-top:10px}}
  @media print {{ body{{background:#fff}} .print{{display:none}} .sheet{{box-shadow:none;margin:0;max-width:none;padding:0}} }}
</style>
<div class="print"><button onclick="window.print()">🖨 印刷 / PDFに保存</button></div>
<div class="sheet">
  <div class="h">
    <span class="mk">🩺</span>
    <div><h1>補助金 活用提案書</h1><small>KAIGO SUBSIDY PROPOSAL — ケアシル</small></div>
    <div class="meta"><b>{esc(args.facility)}</b> 御中<br>所在地：{esc(args.pref)}<br>作成日：{TODAY.isoformat()}／担当：{esc(args.support)}</div>
  </div>
  <div class="lead">貴施設の所在地・条件に該当し、<b>いま活用できる補助金</b>を {len(items)} 件ご提案します（{esc(parts)}）。国・都道府県・市区町村は<b>併用できる場合</b>があり、合算で自己負担を圧縮できます。</div>
  <div class="sum">
    <div class="b"><label>該当制度</label><b>{len(items)} 件</b></div>
    <div class="b"><label>実施主体の内訳</label><b>{esc(parts)}</b></div>
    <div class="b"><label>補助上限の合計（目安）</label><b>{esc(total_s)}</b></div>
  </div>
  {''.join(cards)}
  <div class="note">
    ※ 本提案書はケアシルの収集データに基づく参考情報です。金額は代表額（内訳・要件は各制度の要綱をご確認ください）。<br>
    ※ 国・都道府県・市区町村の制度は<b>併用可否が制度により異なります</b>。実際の併用・申請可否は各窓口・要綱でご確認ください。<br>
    ※ 「確認済」は一次情報で数値まで確認した制度、「概要確認」は存在・URLは確実だが数値は要綱内などの制度です。締切・受付状況は変動します。
  </div>
</div>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"生成: {os.path.relpath(OUT, BASE)}（提案 {len(items)}件：{parts}／上限合計目安 {total:,}円{'〜' if has_null else ''}）")

if __name__ == "__main__":
    main()
