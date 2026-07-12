#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""県間比較ビュー（hikaku.html）を公開_制度.json から生成。
発見済みの構造（基準額は全国共通テンプレ・県差は上限総額と独自加算）を1画面で比較できるようにする。
単一系列の水平バー（上限金額）＋テーブル。値は全行に直接ラベル表示（コントラストWARNの救済要件を満たす）。"""
import os, json, datetime

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "hikaku.html")
TODAY = datetime.date.today()

S = json.load(open(os.path.join(DATA, "公開_制度.json"), encoding="utf-8"))
prefs = [r for r in S if r["実施主体レベル"] == "都道府県"]
max_cap = max((r["補助上限"].get("金額_円") or 0) for r in prefs) or 1

def esc(x):
    return (str(x) if x is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

rows = []
for r in prefs:
    cap = r["補助上限"].get("金額_円")
    dl = None
    if r["締切"]:
        try:
            dl = (datetime.date.fromisoformat(r["締切"]) - TODAY).days
        except ValueError:
            pass
    rows.append({
        "code": r["自治体コード"], "name": r["自治体名"], "status": r["受付状況"],
        "deadline": r["締切"], "days": dl,
        "rate": r["補助率"].get("表示"), "capYen": cap, "capText": r["補助上限"].get("表示"),
        "conf": r["確度"], "url": r["出典"]["公式URL"],
    })

DATA_JSON = json.dumps(rows, ensure_ascii=False)

HTML = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ケアシル｜47都道府県 補助上限・締切 比較（令和8年度 介護テクノロジー導入支援）</title>
<style>
  :root{{--navy:#0F2540;--navy2:#153154;--ink:#1b2a3a;--teal:#12B3AE;--teal-d:#0E9490;--teal-soft:#E6F7F6;
    --line:#E4E9F0;--bg:#F5F8FB;--card:#fff;--muted:#6B7A8D;--ok:#1E9E6A;--ok-soft:#E7F5EE;
    --warn:#E8873B;--warn-soft:#FDF1E6;--grey-soft:#EEF1F5;--shadow:0 1px 2px rgba(15,37,64,.06),0 8px 24px rgba(15,37,64,.06)}}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP",system-ui,sans-serif;background:var(--bg);color:var(--ink)}}
  a{{color:inherit;text-decoration:none}}
  header{{background:linear-gradient(120deg,var(--navy),var(--navy2));color:#fff;padding:13px 24px;position:sticky;top:0;z-index:10}}
  .bar{{max-width:1180px;margin:0 auto;display:flex;align-items:center;gap:12px}}
  .logo{{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px;white-space:nowrap}}
  .logo .mk{{width:29px;height:29px;border-radius:8px;background:var(--teal);display:grid;place-items:center;font-size:16px}}
  .bar small{{color:#9fb4cc;font-size:12px}}
  .back{{margin-left:auto;font-size:12.5px;font-weight:700;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.16);padding:7px 13px;border-radius:999px}}
  .wrap{{max-width:1180px;margin:18px auto 60px;padding:0 24px}}
  h1{{font-size:19px;color:var(--navy);margin:6px 0 4px}}
  .sub{{color:var(--muted);font-size:13px;margin-bottom:14px}}
  .tpl{{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:13px 16px;margin-bottom:16px;font-size:13px}}
  .tpl b{{color:var(--navy)}}
  .tpl .chips{{margin-top:8px;display:flex;gap:8px;flex-wrap:wrap}}
  .tpl .chips span{{background:var(--grey-soft);border-radius:7px;padding:5px 10px;font-size:12px;color:#516481;font-weight:600}}
  .tpl .note{{margin-top:8px;font-size:11.5px;color:var(--muted)}}
  .toolbar{{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}}
  .toolbar label{{font-size:13px;font-weight:700;color:var(--navy);display:inline-flex;gap:6px;align-items:center;cursor:pointer}}
  .toolbar select{{font-size:12.5px;padding:8px;border-radius:8px;border:1px solid var(--line);background:#fff}}
  .cnt{{margin-left:auto;font-size:12.5px;color:var(--muted)}}
  .twrap{{overflow-x:auto;border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);background:var(--card)}}
  table{{width:100%;min-width:760px;border-collapse:collapse;background:var(--card)}}
  thead th{{text-align:left;font-size:11px;letter-spacing:.05em;color:var(--muted);background:#FAFCFE;border-bottom:1px solid var(--line);padding:10px 12px;white-space:nowrap}}
  tbody td{{padding:10px 12px;border-bottom:1px solid var(--line);font-size:13px;vertical-align:middle}}
  tbody tr:hover{{background:#F7FBFB}}
  tbody tr:last-child td{{border-bottom:0}}
  .pn{{font-weight:800;color:var(--navy);white-space:nowrap}}
  .st{{font-size:11px;font-weight:800;padding:4px 9px;border-radius:999px;white-space:nowrap}}
  .st-open{{background:var(--ok-soft);color:var(--ok)}} .st-pre{{background:#EAF0FB;color:#3a63b0}}
  .st-closed{{background:var(--grey-soft);color:var(--muted)}} .st-none{{background:var(--grey-soft);color:var(--muted)}}
  .dl{{white-space:nowrap}} .dl .cd{{color:var(--warn);font-weight:800;font-size:11.5px}}
  .rate{{font-weight:800;color:var(--navy);white-space:nowrap}}
  .capcell{{min-width:300px}}
  .meter{{display:flex;align-items:center;gap:8px}}
  .track{{flex:1;height:12px;background:var(--grey-soft);border-radius:4px;position:relative}}
  .fill{{position:absolute;left:0;top:0;bottom:0;background:var(--teal);border-radius:4px 4px 4px 4px;min-width:4px}}
  .val{{font-size:12px;font-weight:800;color:var(--navy);white-space:nowrap;width:70px;text-align:right}}
  .captext{{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.5}}
  .na{{font-size:11.5px;color:var(--muted);font-weight:600}}
  .conf{{font-size:11px;font-weight:800;padding:3px 9px;border-radius:999px;white-space:nowrap}}
  .c-high{{background:var(--teal-soft);color:var(--teal-d)}} .c-mid{{background:var(--grey-soft);color:#516481}}
  .src a{{color:var(--teal-d);font-weight:700;font-size:12px}}
  footer{{max-width:1180px;margin:0 auto;padding:14px 24px 30px;color:var(--muted);font-size:11.5px;line-height:1.7}}
  @media(max-width:820px){{.capcell{{min-width:190px}} thead th:nth-child(4),tbody td:nth-child(4){{display:none}}}}
</style>
<header><div class="bar">
  <div class="logo"><span class="mk">🩺</span>ケアシル</div>
  <small>47都道府県 比較ビュー — 介護テクノロジー導入支援（令和8年度）</small>
  <a class="back" href="kaigo-hojokin-portal.html">← ポータルへ戻る</a>
</div></header>
<div class="wrap">
  <h1>補助上限・締切・受付状況の県間比較</h1>
  <div class="sub">一次確認済み（確度「確認済」）の県は数値バーで比較。数値が要綱内で未確認の県は「要綱確認」と表示します。データ基準日 {TODAY.isoformat()}。</div>

  <div class="tpl">
    <b>📐 基準額は全国共通テンプレ</b>（国の実施要綱由来・一次確認{sum(1 for r in rows if r['conf']=='高')}県で一致）：
    <div class="chips">
      <span>補助率 4/5</span><span>機器 100万/台</span><span>介護ソフト 100〜250万（職員数区分）</span>
      <span>パッケージ 1,000万</span><span>業務改善 48万</span>
    </div>
    <div class="note">県の違いは「<b>上限総額（400万〜1,700万）</b>」と「<b>独自加算</b>（協働化・経営改善・付帯経費・台数制限など）」に出ます。下の表はそこを比較するものです。</div>
  </div>

  <div class="toolbar">
    <label><input type="checkbox" id="openOnly" checked onchange="render()">受付中のみ</label>
    <select id="sort" onchange="render()">
      <option value="cap">上限が高い順</option>
      <option value="deadline">締切が近い順</option>
      <option value="code">都道府県コード順</option>
    </select>
    <span class="cnt" id="cnt"></span>
  </div>

  <div class="twrap">
  <table>
    <thead><tr>
      <th>都道府県</th><th>受付状況</th><th>締切</th><th>補助率</th>
      <th>補助上限（パッケージ/事業所ベースの代表額）</th><th>確度</th><th>出典</th>
    </tr></thead>
    <tbody id="tb"></tbody>
  </table>
  </div>
</div>
<footer>
  ※ バーの長さは正規化済みの代表額（各県の最大上限・円換算）。内訳・要件は必ず出典（公式ページ・要綱）を確認してください。<br>
  ※ 「確認済」＝一次情報で数値まで確認。「概要確認」＝制度・URLは確実、数値は要綱PDF内など未確認。締切・受付状況は日次収集で更新される想定です。
</footer>
<script>
const ROWS = {DATA_JSON};
const MAX = {max_cap};
const stCls = s => s==='受付中'?'st-open':s==='受付前'?'st-pre':s==='終了'?'st-closed':'st-none';
const yen = v => (v/10000).toLocaleString() + '万';
function render(){{
  const openOnly = document.getElementById('openOnly').checked;
  const sort = document.getElementById('sort').value;
  let rows = ROWS.filter(r => !openOnly || r.status==='受付中');
  rows.sort((a,b)=>{{
    if(sort==='cap') return (b.capYen||0)-(a.capYen||0) || a.code.localeCompare(b.code);
    if(sort==='deadline'){{
      const ax=a.deadline||'9999', bx=b.deadline||'9999';
      return ax.localeCompare(bx) || a.code.localeCompare(b.code);
    }}
    return a.code.localeCompare(b.code);
  }});
  document.getElementById('cnt').textContent = `表示 ${{rows.length}} / 47県`;
  document.getElementById('tb').innerHTML = rows.map(r=>{{
    const dl = r.deadline
      ? `${{r.deadline}}${{(r.days!=null&&r.days>=0&&r.status==='受付中')?` <span class="cd">あと${{r.days}}日</span>`:''}}`
      : '<span class="na">未定</span>';
    const meter = r.capYen
      ? `<div class="meter"><div class="track"><div class="fill" style="width:${{Math.max(3,Math.round(r.capYen/MAX*100))}}%"></div></div><span class="val">${{yen(r.capYen)}}</span></div>
         <div class="captext">${{r.capText||''}}</div>`
      : `<span class="na">要綱確認${{r.capText&&r.capText!=='要確認'?'（'+r.capText+'）':''}}</span>`;
    const conf = r.conf==='高' ? '<span class="conf c-high">確認済</span>' : '<span class="conf c-mid">概要確認</span>';
    return `<tr title="${{(r.capText||'').replace(/"/g,'')}}">
      <td class="pn">${{r.name}}</td>
      <td><span class="st ${{stCls(r.status)}}">${{r.status}}</span></td>
      <td class="dl">${{dl}}</td>
      <td class="rate">${{r.rate&&!r.rate.startsWith('要確認')?r.rate:'<span class=na>—</span>'}}</td>
      <td class="capcell">${{meter}}</td>
      <td>${{conf}}</td>
      <td class="src"><a href="${{r.url}}" target="_blank" rel="noopener">公式 🔗</a></td>
    </tr>`;
  }}).join('');
}}
render();
</script>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
high = sum(1 for r in rows if r["conf"] == "高")
print(f"生成: hikaku.html（47県・確認済{high}県・最大上限 {max_cap:,}円）")
