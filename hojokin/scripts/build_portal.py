#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公開JSON(統合版)＋機器マスタから 単一HTMLプロトタイプ を生成する。
国→都道府県→市区町村の重層を、実施主体レベルバッジと所在地連動フィルタで表現。
データ埋め込みで file:// でも fetch 不要（CORS回避）。UIは公開データの写像。
"""
import csv, json, os, datetime
from collections import Counter

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "kaigo-hojokin-portal.html")

with open(os.path.join(DATA, "公開_制度.json"), encoding="utf-8") as f:
    SEIDO = json.load(f)

TODAY = datetime.date.today().isoformat()
LAST_FETCH = max((r["出典"]["取得日時"][:10] for r in SEIDO), default=TODAY)

# 新着情報（changelog.jsonl の直近14日・最大15件）
NEWS = []
clpath = os.path.join(DATA, "changelog.jsonl")
if os.path.exists(clpath):
    cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    for line in open(clpath, encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("日付", "") >= cutoff:
            NEWS.append(e)
    NEWS = NEWS[-15:][::-1]  # 新しい順
NEW_IDS = sorted({e["id"] for e in NEWS if e.get("日付", "") >= (datetime.date.today() - datetime.timedelta(days=7)).isoformat()})

KIKI, KIKI_ORDER = {}, []
with open(os.path.join(DATA, "機器マスタ.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        KIKI[r["機器ID"]] = {"名": r["機器名(正規)"], "大": r["大分類"]}
        KIKI_ORDER.append(r["機器ID"])

present = set()
for s in SEIDO:
    present.update(s["対象機器タグ"])

groups = {}
for kid in KIKI_ORDER:
    if kid in present:
        groups.setdefault(KIKI[kid]["大"], []).append(kid)

def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

GICON = {"介護ロボット": "🤖", "ICT": "💻", "介護福祉機器": "🦽"}
chip_html = []
for g, ids in groups.items():
    chip_html.append(f'<div class="subh">{GICON.get(g,"")} {esc(g)}</div>')
    for kid in ids:
        chip_html.append(f'<span class="chip eq" data-eq="{kid}" onclick="toggleEq(this)">{esc(KIKI[kid]["名"])}</span>')
chip_html = "\n        ".join(chip_html)

prefs = [s["自治体名"] for s in SEIDO if s["実施主体レベル"] == "都道府県"]
PREFCODE = {s["自治体名"]: s["自治体コード"] for s in SEIDO if s["実施主体レベル"] == "都道府県"}
opt_html = '<option value="">指定なし（全国）</option>\n          ' + "\n          ".join(
    f'<option value="{esc(p)}">{esc(p)}</option>' for p in prefs)

lv = Counter(s["実施主体レベル"] for s in SEIDO)
DATA_JSON = json.dumps(SEIDO, ensure_ascii=False)
KIKI_JSON = json.dumps({k: v["名"] for k, v in KIKI.items()}, ensure_ascii=False)
PREFCODE_JSON = json.dumps(PREFCODE, ensure_ascii=False)
NEWS_JSON = json.dumps(NEWS, ensure_ascii=False)
NEWIDS_JSON = json.dumps(NEW_IDS, ensure_ascii=False)

HTML = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ケアシル｜介護 補助金・助成金ポータル（重層・実データ版）</title>
<style>
  :root{{
    --navy:#0F2540; --navy-2:#153154; --ink:#1b2a3a;
    --teal:#12B3AE; --teal-d:#0E9490; --teal-soft:#E6F7F6;
    --amber:#C98A2B; --amber-soft:#FBF1DE;
    --line:#E4E9F0; --bg:#F5F8FB; --card:#FFFFFF; --muted:#6B7A8D;
    --warn:#E8873B; --warn-soft:#FDF1E6; --ok:#1E9E6A; --ok-soft:#E7F5EE; --grey-soft:#EEF1F5;
    --radius:14px; --shadow:0 1px 2px rgba(15,37,64,.06),0 8px 24px rgba(15,37,64,.06);
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP",system-ui,sans-serif;
    background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;padding-bottom:70px}}
  a{{color:inherit;text-decoration:none}}
  body[data-mode="support"]{{--accent:var(--amber);--accent-soft:var(--amber-soft)}}
  body[data-mode="facility"]{{--accent:var(--teal-d);--accent-soft:var(--teal-soft)}}
  header{{background:linear-gradient(120deg,var(--navy),var(--navy-2));color:#fff;padding:12px 24px;
    position:sticky;top:0;z-index:30;box-shadow:0 4px 18px rgba(15,37,64,.18)}}
  .bar{{max-width:1280px;margin:0 auto;display:flex;align-items:center;gap:14px;flex-wrap:wrap}}
  .logo{{display:flex;align-items:center;gap:10px;font-weight:800;font-size:19px;white-space:nowrap}}
  .logo .mk{{width:30px;height:30px;border-radius:9px;background:var(--teal);display:grid;place-items:center;font-size:17px}}
  .logo small{{display:block;font-weight:500;font-size:11px;color:#9fb4cc;letter-spacing:.14em}}
  .modesw{{display:flex;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.14);border-radius:999px;padding:3px}}
  .modesw button{{border:0;background:transparent;color:#cfe0f0;font-weight:700;font-size:13px;padding:7px 15px;border-radius:999px;cursor:pointer}}
  .modesw button.on{{background:#fff;color:var(--navy)}}
  .crawl{{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12.5px;color:#cfe0f0;
    background:rgba(255,255,255,.08);padding:7px 13px;border-radius:999px;border:1px solid rgba(255,255,255,.12)}}
  .dot{{width:8px;height:8px;border-radius:50%;background:#3ce0a0;box-shadow:0 0 0 4px rgba(60,224,160,.2)}}
  /* 新着情報 */
  .news{{max-width:1280px;margin:14px auto 0;padding:0 24px}}
  .newsbox{{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}}
  .newshead{{display:flex;align-items:center;gap:9px;padding:11px 16px;cursor:pointer;user-select:none}}
  .newshead b{{color:var(--navy);font-size:13.5px}}
  .newshead .n{{background:var(--teal);color:#fff;font-size:11px;font-weight:800;padding:2px 9px;border-radius:999px}}
  .newshead .tgl{{margin-left:auto;color:var(--muted);font-size:12px}}
  .newslist{{border-top:1px solid var(--line);max-height:220px;overflow-y:auto;display:none}}
  .newslist.open{{display:block}}
  .newsitem{{display:flex;gap:10px;align-items:baseline;padding:8px 16px;border-bottom:1px solid #F1F4F8;font-size:12.5px;cursor:pointer}}
  .newsitem:hover{{background:#F7FBFB}} .newsitem:last-child{{border-bottom:0}}
  .newsitem .d{{color:var(--muted);font-size:11px;white-space:nowrap}}
  .newsitem .k{{font-size:10.5px;font-weight:800;padding:2px 7px;border-radius:5px;white-space:nowrap}}
  .k-new{{background:var(--teal-soft);color:var(--teal-d)}} .k-up{{background:#EAF0FB;color:#3a63b0}} .k-end{{background:var(--grey-soft);color:var(--muted)}}
  .newsitem .who{{font-weight:800;color:var(--navy);white-space:nowrap}}
  .newsitem .what{{color:#3c4c5e;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .newbadge{{font-size:10px;font-weight:800;background:var(--teal);color:#fff;padding:3px 7px;border-radius:5px}}
  .banner{{max-width:1280px;margin:16px auto 0;padding:0 24px}}
  .binner{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;display:flex;align-items:center;gap:12px;box-shadow:var(--shadow)}}
  .binner .ic{{font-size:22px}} .binner b{{color:var(--navy)}} .binner span{{color:var(--muted);font-size:13px}}
  .wrap{{max-width:1280px;margin:16px auto 40px;padding:0 24px;display:grid;grid-template-columns:300px 1fr;gap:22px}}
  .panel{{position:sticky;top:78px;align-self:start;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    box-shadow:var(--shadow);overflow:hidden;max-height:calc(100vh - 96px);display:flex;flex-direction:column}}
  .panel .ph{{background:var(--accent-soft);padding:13px 16px;border-bottom:1px solid var(--line)}}
  .panel .ph b{{color:var(--navy);font-size:14.5px}} .panel .ph small{{display:block;color:var(--muted);font-size:11.5px;margin-top:2px}}
  .pbody{{padding:14px 16px 16px;overflow-y:auto}}
  .fg{{margin-bottom:15px}} .fg:last-child{{margin-bottom:0}}
  .fg h4{{margin:0 0 8px;font-size:11.5px;letter-spacing:.06em;color:var(--muted)}}
  select{{width:100%;font-size:13.5px;padding:9px 10px;border-radius:9px;border:1px solid var(--line);background:#fff;color:var(--ink);outline:none}}
  select:focus{{border-color:var(--accent)}}
  .chip{{display:inline-flex;align-items:center;gap:5px;font-size:12.5px;padding:6px 11px;margin:0 6px 6px 0;
    border-radius:999px;border:1px solid var(--line);background:#fff;cursor:pointer;color:var(--ink);transition:.12s;user-select:none}}
  .chip:hover{{border-color:var(--accent)}}
  .chip.on{{background:var(--accent-soft);border-color:var(--accent);color:var(--navy);font-weight:700}}
  .equip .subh{{font-size:11.5px;font-weight:800;color:var(--navy);margin:4px 0 7px}}
  .equip .subh:not(:first-of-type){{margin-top:11px;padding-top:11px;border-top:1px dashed var(--line)}}
  .reset{{width:100%;margin-top:6px;background:none;border:0;color:var(--muted);font-size:12px;cursor:pointer;text-decoration:underline}}
  .toolbar{{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}}
  .search{{display:flex;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:11px;padding:7px;flex:1;min-width:220px}}
  .search input{{flex:1;border:0;font-size:14px;padding:6px 8px;outline:none;background:transparent}}
  .sort select{{width:auto;font-size:12.5px;padding:8px}}
  .res{{color:var(--muted);font-size:13px;margin-bottom:8px}} .res b{{color:var(--navy);font-size:15px}}
  .hint{{background:#FFF9EC;border:1px solid #EBD9AE;color:#8a6d2f;font-size:12.5px;font-weight:600;
    padding:10px 13px;border-radius:10px;margin-bottom:14px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:15px 17px;margin-bottom:14px;box-shadow:var(--shadow);transition:.14s}}
  .card:hover{{border-color:#c9d6e6;transform:translateY(-1px)}}
  .crow{{display:flex;align-items:center;gap:9px;flex-wrap:wrap}}
  .lvb{{font-size:10.5px;font-weight:800;padding:4px 8px;border-radius:6px;white-space:nowrap}}
  .lv-国{{background:#EAF0FB;color:#274b8f}} .lv-都道府県{{background:#EEF1F5;color:#516481}} .lv-市区町村{{background:var(--teal-soft);color:var(--teal-d)}}
  .gov{{font-size:11.5px;font-weight:700;color:var(--navy);background:var(--grey-soft);padding:4px 10px;border-radius:7px;white-space:nowrap}}
  .ttl{{font-size:16px;font-weight:800;color:var(--navy);line-height:1.4}}
  .badges{{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}}
  .status,.conf{{font-size:11.5px;font-weight:800;padding:5px 11px;border-radius:999px;white-space:nowrap}}
  .s-open{{background:var(--ok-soft);color:var(--ok)}} .s-pre{{background:#EAF0FB;color:#3a63b0}} .s-closed{{background:var(--grey-soft);color:var(--muted)}} .s-none{{background:var(--grey-soft);color:var(--muted)}}
  .s-soon{{background:var(--warn-soft);color:#c06a1f}}
  .c-high{{background:var(--teal-soft);color:var(--teal-d)}} .c-mid{{background:#F1F4F8;color:#516481}} .c-low{{background:#FBECEC;color:#b5524a}}
  .match{{display:flex;align-items:center;gap:10px;margin:11px 0 0;padding:9px 11px;border-radius:10px;background:var(--teal-soft)}}
  .mscore{{font-size:12px;font-weight:800;color:var(--teal-d);white-space:nowrap;display:flex;align-items:center;gap:6px}}
  .mscore .bars{{display:flex;gap:2px}} .mscore .bars i{{width:5px;height:13px;border-radius:2px;background:var(--teal)}} .mscore .bars i.off{{background:#c7e6e5}}
  .mreasons{{display:flex;flex-wrap:wrap;gap:5px}}
  .mr{{font-size:11px;color:#2f6f6d;background:#fff;border:1px solid #c7e6e5;padding:3px 8px;border-radius:6px}}
  .mr::before{{content:"✓ ";color:var(--ok);font-weight:800}}
  .equiprow{{margin:10px 0 0;display:flex;gap:7px;align-items:baseline;flex-wrap:wrap;padding:9px 11px;background:#FAFCFE;border:1px solid var(--line);border-radius:10px}}
  .equiprow .k{{font-weight:800;color:var(--muted);font-size:10.5px;white-space:nowrap}}
  .equiprow .e{{font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;background:#F1F4F8;color:#516481;border:1px solid var(--line)}}
  .equiprow .e.hit{{background:var(--amber-soft);color:var(--amber);border-color:#e6cfa0;font-weight:800}} .equiprow .e.hit::before{{content:"◎ "}}
  .meta{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:12px 0;margin-top:11px;border-top:1px solid var(--line)}}
  .m label{{display:block;font-size:11px;color:var(--muted);margin-bottom:3px}} .m b{{font-size:13.5px}}
  .m .big{{font-size:14px;color:var(--navy);font-weight:800}} .m .cd{{color:var(--warn);font-weight:800}}
  .actions{{display:flex;align-items:center;gap:9px;padding-top:12px;border-top:1px solid var(--line);flex-wrap:wrap}}
  .ev{{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--teal-d);font-weight:700;padding:7px 11px;border-radius:9px;border:1px solid var(--teal);background:#fff}}
  .ev:hover{{background:var(--teal-soft)}} .ev::before{{content:"🔗"}}
  .contact{{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;color:var(--navy);border:1px solid var(--line);padding:8px 13px;border-radius:9px}}
  .contact:hover{{background:var(--grey-soft)}}
  .cta{{margin-left:auto;display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:800;color:#fff;background:var(--accent);padding:9px 15px;border-radius:9px;cursor:pointer;border:0}}
  .cta:hover{{filter:brightness(.95)}} .cta.added{{background:var(--ok)}}
  .note{{font-size:11px;color:var(--muted);margin-top:9px}}
  .empty{{text-align:center;color:var(--muted);padding:50px 0}}
  .cartbar{{position:fixed;left:0;right:0;bottom:0;z-index:25;background:var(--navy);color:#fff;padding:11px 24px;display:none;box-shadow:0 -4px 18px rgba(15,37,64,.25)}}
  body[data-mode="support"] .cartbar{{display:block}}
  .cartin{{max-width:1280px;margin:0 auto;display:flex;align-items:center;gap:16px}}
  .cartin .lbl{{font-weight:800;font-size:14px}} .cartin .cnt{{background:var(--amber);color:var(--navy);font-weight:800;padding:2px 10px;border-radius:999px;margin-left:6px}}
  .cartin .desc{{color:#9fb4cc;font-size:12.5px}} .cartin .r{{margin-left:auto;display:flex;gap:10px}}
  .cartin button{{border:0;font-weight:800;font-size:13px;padding:9px 16px;border-radius:9px;cursor:pointer;background:var(--amber);color:var(--navy)}}
  footer{{max-width:1280px;margin:0 auto;padding:8px 24px 30px;color:var(--muted);font-size:11.5px;line-height:1.7}}
  @media(max-width:900px){{.wrap{{grid-template-columns:1fr}}.panel{{position:static;max-height:none}}.meta{{grid-template-columns:repeat(2,1fr)}}}}
</style>

<body data-mode="facility">
<header>
  <div class="bar">
    <div class="logo"><span class="mk">🩺</span><div>ケアシル<small>KAIGO SUBSIDY PORTAL</small></div></div>
    <div class="modesw">
      <button id="mFac" class="on" onclick="setMode('facility')">🏢 施設モード</button>
      <button id="mSup" onclick="setMode('support')">🤝 支援者モード</button>
    </div>
    <a href="hikaku.html" style="font-size:12.5px;font-weight:700;color:#cfe0f0;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.14);padding:7px 13px;border-radius:999px">📊 47県比較</a>
    <div class="crawl"><span class="dot"></span>最終収集 {LAST_FETCH}</div>
  </div>
</header>

<div class="news" id="newsWrap" style="display:none">
  <div class="newsbox">
    <div class="newshead" onclick="toggleNews()">
      🆕 <b>新着・更新情報</b><span class="n" id="newsCnt">0</span>
      <span class="tgl" id="newsTgl">開く ▾</span>
    </div>
    <div class="newslist" id="newsList"></div>
  </div>
</div>

<div class="banner">
  <div class="binner">
    <span class="ic" id="bIc">🏢</span>
    <div>
      <b id="bTtl">自施設の条件を入れて、使える補助金を絞り込む</b><br>
      <span id="bDesc">所在地を選ぶと、国＋都道府県＋市区町村の制度を横断表示。全{len(SEIDO)}件（国{lv['国']}＋都道府県{lv['都道府県']}＋市区町村{lv['市区町村']}）の実データから検索。</span>
    </div>
  </div>
</div>

<div class="wrap">
  <aside class="panel">
    <div class="ph"><b id="pTtl">🏢 自施設プロフィール</b><small id="pSub">条件を入れるほどマッチ精度が上がります</small></div>
    <div class="pbody">
      <div class="fg">
        <h4>所在地（都道府県）</h4>
        <select id="prefSel" onchange="onFilter()">
          {opt_html}
        </select>
      </div>
      <div class="fg">
        <h4>実施主体</h4>
        <span class="chip lv on" data-lv="国" onclick="toggleLv(this)">国（全国）</span>
        <span class="chip lv on" data-lv="都道府県" onclick="toggleLv(this)">都道府県</span>
        <span class="chip lv on" data-lv="市区町村" onclick="toggleLv(this)">市区町村</span>
      </div>
      <div class="fg">
        <h4>受付状況</h4>
        <span class="chip st on" data-st="受付中" onclick="toggleSt(this)">受付中</span>
        <span class="chip st" data-st="受付前" onclick="toggleSt(this)">受付前</span>
        <span class="chip st" data-st="終了" onclick="toggleSt(this)">終了</span>
        <span class="chip st" data-st="未定" onclick="toggleSt(this)">未定</span>
      </div>
      <div class="fg equip">
        <h4>対象機器から逆引き（複数可）</h4>
        {chip_html}
      </div>
      <button class="reset" onclick="resetAll()">条件をリセット</button>
    </div>
  </aside>

  <main>
    <div class="toolbar">
      <div class="search"><input id="q" placeholder="🔍 制度名・自治体で絞り込み" oninput="onFilter()"></div>
      <div class="sort"><select id="sort" onchange="render()">
        <option value="deadline">締切が近い順</option>
        <option value="match">適合度が高い順</option>
        <option value="amount">補助上限が高い順</option>
      </select></div>
    </div>
    <div class="res" id="res"></div>
    <div class="hint" id="hint" style="display:none"></div>
    <div id="list"></div>
  </main>
</div>

<div class="cartbar">
  <div class="cartin">
    <div class="lbl">📋 提案リスト<span class="cnt" id="cnt">0</span></div>
    <div class="desc">施設に提示する補助金をまとめています。国＋県＋市の合算を1枚に整えて出力できます。</div>
    <div class="r"><button onclick="clearCart()">クリア</button><button onclick="exportProposal()">提案書として出力（PDF）</button></div>
  </div>
</div>

<footer>※ 重層・実データ版。カードは <code>data/公開_制度.json</code>（スキーマ検証0エラー・国/県/市を統合）から自動生成。数値・締切は各カードの公式ページ（🔗）に直結。金額は代表額（内訳は要綱参照）。併用可否は各要綱で要確認。</footer>

<script>
const SEIDO = {DATA_JSON};
const KIKI = {KIKI_JSON};
const PREFCODE = {PREFCODE_JSON};
const NEWS = {NEWS_JSON};
const NEW_IDS = new Set({NEWIDS_JSON});
const TODAY = new Date('{TODAY}');
const state = {{ pref:'', q:'', equips:new Set(), status:new Set(['受付中']),
  levels:new Set(['国','都道府県','市区町村']), mode:'facility', cart:new Set() }};

function daysLeft(d){{ if(!d) return null; return Math.ceil((new Date(d)-TODAY)/86400000); }}
function statusClass(s){{ return s==='受付中'?'s-open':s==='受付前'?'s-pre':s==='終了'?'s-closed':'s-none'; }}
function confBadge(c){{ if(c==='高')return['c-high','確認済']; if(c==='中')return['c-mid','概要確認']; return['c-low','詳細確認中']; }}

function toggleEq(el){{ el.classList.toggle('on'); const k=el.dataset.eq; state.equips.has(k)?state.equips.delete(k):state.equips.add(k); render(); }}
function toggleSt(el){{ el.classList.toggle('on'); const s=el.dataset.st; state.status.has(s)?state.status.delete(s):state.status.add(s); render(); }}
function toggleLv(el){{ el.classList.toggle('on'); const l=el.dataset.lv; state.levels.has(l)?state.levels.delete(l):state.levels.add(l); render(); }}
function onFilter(){{ state.pref=document.getElementById('prefSel').value; state.q=document.getElementById('q').value.trim(); render(); }}
function resetAll(){{
  state.pref=''; state.q=''; state.equips.clear(); state.status=new Set(['受付中']); state.levels=new Set(['国','都道府県','市区町村']);
  document.getElementById('prefSel').value=''; document.getElementById('q').value='';
  document.querySelectorAll('.chip.eq.on').forEach(c=>c.classList.remove('on'));
  document.querySelectorAll('.chip.st').forEach(c=>c.classList.toggle('on', c.dataset.st==='受付中'));
  document.querySelectorAll('.chip.lv').forEach(c=>c.classList.add('on'));
  render();
}}

function evaluate(rec){{
  if(!state.levels.has(rec.実施主体レベル)) return null;
  if(state.status.size && !state.status.has(rec.受付状況)) return null;
  const matchedEq = rec.対象機器タグ.filter(t=>state.equips.has(t));
  if(state.equips.size && matchedEq.length===0) return null;
  if(state.q){{ if(!(rec.制度名+rec.自治体名).includes(state.q)) return null; }}
  const reasons=[];
  const code = state.pref ? PREFCODE[state.pref] : '';
  if(state.pref){{
    if(rec.実施主体レベル==='国'){{ reasons.push('全国対象'); }}
    else if(rec.実施主体レベル==='都道府県'){{ if(rec.自治体コード!==code) return null; reasons.push('所在地：'+rec.自治体名+' 一致'); }}
    else {{ if(!(rec.自治体コード||'').startsWith(code)) return null; reasons.push('所在地：'+rec.自治体名+'（'+state.pref+'内）'); }}
  }} else if(rec.実施主体レベル==='国'){{ reasons.push('全国対象'); }}
  if(matchedEq.length) reasons.push('対象機器：'+matchedEq.map(t=>KIKI[t]).slice(0,3).join('・')+' 該当');
  if(rec.受付状況==='受付中') reasons.push('受付中');
  if(rec.確度==='高') reasons.push('数値まで確認済');
  return {{rec, reasons, matchedEq}};
}}

function equipRow(rec){{
  const hits=new Set(state.equips);
  const ordered=[...rec.対象機器タグ].sort((a,b)=>(hits.has(b)?1:0)-(hits.has(a)?1:0));
  const show=ordered.slice(0,6);
  let html=show.map(t=>`<span class="e ${{hits.has(t)?'hit':''}}">${{KIKI[t]||t}}</span>`).join('');
  if(rec.対象機器タグ.length>show.length) html+=`<span class="e">+${{rec.対象機器タグ.length-show.length}}</span>`;
  return rec.対象機器タグ.length?`<div class="equiprow"><span class="k">対象機器</span>${{html}}</div>`:'';
}}

function cardHTML(ev){{
  const r=ev.rec, dl=daysLeft(r.締切);
  const [cc,ct]=confBadge(r.確度);
  const bars=Array.from({{length:4}},(_,i)=>`<i class="${{i<ev.reasons.length?'':'off'}}"></i>`).join('');
  const level=ev.reasons.length>=3?'高':ev.reasons.length>=2?'中':'低';
  const dead = r.締切 ? `${{r.締切}}${{dl!=null&&dl>=0?` <span class="cd">（あと${{dl}}日）</span>`:''}}` : '未定';
  const soon = (r.受付状況==='受付中' && dl!=null && dl>=0 && dl<=7)
    ? `<span class="status s-soon">⚠ 締切まで${{dl}}日</span>` : '';
  const added = state.cart.has(r.id);
  const ctaLbl = added?'✓ 追加済':(state.mode==='support'?'＋ 提案に追加':'☆ 保存');
  const nb = NEW_IDS.has(r.id) ? '<span class="newbadge">NEW</span>' : '';
  return `<article class="card">
    <div class="crow"><span class="lvb lv-${{r.実施主体レベル}}">${{r.実施主体レベル}}</span><span class="gov">${{r.自治体名}}</span><div class="ttl">${{r.制度名}} ${{nb}}</div>
      <div class="badges">${{soon}}<span class="status ${{statusClass(r.受付状況)}}">${{r.受付状況}}</span><span class="conf ${{cc}}">${{ct}}</span></div></div>
    <div class="match"><span class="mscore">適合度 ${{level}} <span class="bars">${{bars}}</span></span>
      <div class="mreasons">${{ev.reasons.map(x=>`<span class="mr">${{x}}</span>`).join('')||'<span class="mr">条件に該当</span>'}}</div></div>
    ${{equipRow(r)}}
    <div class="meta">
      <div class="m"><label>対象施設</label><b>${{r.対象施設.join('・')}}</b></div>
      <div class="m"><label>受付開始</label><b>${{r.受付開始||'未定'}}</b></div>
      <div class="m"><label>締切</label><b>${{dead}}</b></div>
      <div class="m"><label>補助率 / 上限</label><b class="big">${{r.補助率.表示||'—'}} / ${{r.補助上限.表示||'—'}}</b></div>
    </div>
    <div class="actions">
      <a class="ev" href="${{r.出典.公式URL}}" target="_blank" rel="noopener">公式ページ（出典）</a>
      <a class="contact" href="${{r.窓口.URL}}" target="_blank" rel="noopener">☎ 窓口</a>
      <button class="cta ${{added?'added':''}}" onclick="toggleCart('${{r.id}}',this)">${{ctaLbl}}</button>
    </div>
    <div class="note">🔎 自動収集 ${{r.出典.取得日時.slice(0,10)}} 取得／確度：${{r.確度}}${{r.メモ?'／'+r.メモ:''}}</div>
  </article>`;
}}

function render(){{
  const evs=SEIDO.map(evaluate).filter(Boolean);
  const sort=document.getElementById('sort').value;
  evs.sort((a,b)=>{{
    if(sort==='match') return b.reasons.length-a.reasons.length;
    if(sort==='amount') return (b.rec.補助上限.金額_円||0)-(a.rec.補助上限.金額_円||0);
    const ax=a.rec.締切?new Date(a.rec.締切):new Date('2100-01-01');
    const bx=b.rec.締切?new Date(b.rec.締切):new Date('2100-01-01');
    return ax-bx;
  }});
  document.getElementById('res').innerHTML = `この条件で使える制度 <b>${{evs.length}}</b> 件 / 全${{SEIDO.length}}件`;
  // 重層ヒント：所在地選択時に複数レベルが並んだら併用可能性を示す
  const hint=document.getElementById('hint');
  const lvset=new Set(evs.map(e=>e.rec.実施主体レベル));
  if(state.pref && lvset.size>=2){{
    const parts=['国','都道府県','市区町村'].filter(l=>lvset.has(l));
    hint.style.display='block';
    hint.innerHTML=`💡 <b>${{state.pref}}</b>では ${{parts.join('＋')}} の制度を<b>併用できる場合があります</b>（合算で自己負担を圧縮。併用可否は各要綱で確認）。`;
  }} else {{ hint.style.display='none'; }}
  document.getElementById('list').innerHTML =
    evs.length?evs.map(cardHTML).join(''):'<div class="empty">条件に合う制度がありません。受付状況・実施主体・機器の条件を緩めてください。</div>';
}}

function setMode(m){{
  state.mode=m; document.body.dataset.mode=m; const fac=m==='facility';
  document.getElementById('mFac').classList.toggle('on',fac);
  document.getElementById('mSup').classList.toggle('on',!fac);
  document.getElementById('bIc').textContent=fac?'🏢':'🤝';
  document.getElementById('pTtl').textContent=fac?'🏢 自施設プロフィール':'🤝 訪問先 施設プロフィール';
  document.getElementById('pSub').textContent=fac?'条件を入れるほどマッチ精度が上がります':'訪問先の条件を入力して、その場で提案を組み立て';
  document.getElementById('bTtl').textContent=fac?'自施設の条件を入れて、使える補助金を絞り込む':'訪問先の条件を入れて、国＋県＋市の制度を提案リストにまとめる';
  render();
}}
function toggleCart(id,el){{ state.cart.has(id)?state.cart.delete(id):state.cart.add(id); document.getElementById('cnt').textContent=state.cart.size; render(); }}
function clearCart(){{ state.cart.clear(); document.getElementById('cnt').textContent=0; render(); }}

function exportProposal(){{
  var items=[...state.cart].map(function(id){{return SEIDO.find(function(r){{return r.id===id;}});}}).filter(Boolean);
  if(!items.length){{ alert('提案リストが空です。カードの「＋提案に追加」で選んでください。'); return; }}
  var order={{'国':0,'都道府県':1,'市区町村':2}};
  items.sort(function(a,b){{return (order[a.実施主体レベル]||9)-(order[b.実施主体レベル]||9);}});
  var total=0, hasNull=false, cnt={{}};
  items.forEach(function(r){{ total+=(r.補助上限.金額_円||0); if(r.補助上限.金額_円==null)hasNull=true; cnt[r.実施主体レベル]=(cnt[r.実施主体レベル]||0)+1; }});
  var parts=['国','都道府県','市区町村'].filter(function(l){{return cnt[l];}}).map(function(l){{return l+cnt[l];}}).join('＋');
  var cards=items.map(function(r){{
    var dl=daysLeft(r.締切); var dls=(dl!=null&&dl>=0)?('（あと'+dl+'日）'):'';
    var eq=r.対象機器タグ.slice(0,6).map(function(t){{return KIKI[t]||t;}}).join('・');
    return '<div class=pc><div class=ph><span class=lv>'+r.実施主体レベル+'</span> <b class=gov>'+r.自治体名+'</b> <b class=tt>'+r.制度名+'</b> <span class=stt>'+r.受付状況+'</span></div>'
      +'<div class=pg><div><label>補助率</label><b>'+(r.補助率.表示||'—')+'</b></div><div><label>補助上限</label><b>'+(r.補助上限.表示||'—')+'</b></div>'
      +'<div><label>締切</label><b>'+(r.締切||'未定')+' '+dls+'</b></div><div><label>対象機器</label><b>'+(eq||'—')+'</b></div></div>'
      +'<div class=pf>確度: '+r.確度+' ／ <a href="'+r.出典.公式URL+'">出典（公式ページ）</a></div></div>';
  }}).join('');
  var css='body{{font-family:sans-serif;color:#1b2a3a;margin:0;background:#eef2f6}}.pr{{text-align:right;max-width:780px;margin:10px auto}}'
    +'.pr button{{border:0;background:#12B3AE;color:#fff;font-weight:800;padding:9px 15px;border-radius:8px;cursor:pointer}}'
    +'.sh{{max-width:780px;margin:0 auto 20px;background:#fff;padding:24px 28px;box-shadow:0 4px 18px rgba(15,37,64,.12)}}'
    +'h1{{color:#0F2540;font-size:19px;border-bottom:3px solid #0F2540;padding-bottom:8px;margin:0 0 6px}}'
    +'.meta{{color:#6B7A8D;font-size:12px;margin-bottom:12px}}.sum{{background:#E6F7F6;border:1px solid #cdeae8;border-radius:10px;padding:11px 14px;font-size:13px;margin-bottom:14px}}'
    +'.pc{{border:1px solid #D9E1EA;border-radius:10px;padding:11px 13px;margin-bottom:10px}}.ph{{display:flex;align-items:center;gap:7px;flex-wrap:wrap}}'
    +'.lv{{font-size:10px;font-weight:800;background:#EEF1F5;color:#516481;padding:2px 7px;border-radius:5px}}.gov{{font-size:11px;background:#F1F4F8;padding:2px 7px;border-radius:5px;color:#0F2540}}'
    +'.tt{{font-size:14px;color:#0F2540}}.stt{{margin-left:auto;font-size:11px;font-weight:800;color:#1E9E6A}}'
    +'.pg{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:9px 0;padding:8px 0;border-top:1px solid #D9E1EA;border-bottom:1px solid #D9E1EA}}'
    +'.pg label{{display:block;font-size:10px;color:#6B7A8D}}.pg b{{font-size:12.5px;color:#0F2540}}.pf{{font-size:11px;color:#6B7A8D}}.pf a{{color:#0E9490}}'
    +'.note{{font-size:10.5px;color:#6B7A8D;margin-top:12px;border-top:1px solid #D9E1EA;padding-top:9px}}'
    +'@media print{{.pr{{display:none}}body{{background:#fff}}.sh{{box-shadow:none;margin:0;max-width:none}}}}';
  var html='<!doctype html><meta charset=utf-8><title>補助金 活用提案書</title><style>'+css+'</style>'
    +'<div class=pr><button onclick="window.print()">🖨 印刷 / PDFに保存</button></div>'
    +'<div class=sh><h1>補助金 活用提案書</h1><div class=meta>所在地：'+(state.pref||'（未選択）')+'／作成日 '+TODAY.toISOString().slice(0,10)+'／ケアシル</div>'
    +'<div class=sum>該当 <b>'+items.length+'</b> 件（'+parts+'）／補助上限の合計目安 <b>'+total.toLocaleString()+'円'+(hasNull?'〜':'')+'</b>（国＋県＋市は併用できる場合あり・可否は要綱で確認）</div>'
    +cards
    +'<div class=note>※ 金額は代表額（内訳・要件は各要綱をご確認ください）。※ 併用可否は制度により異なります。※ 締切・受付状況は変動します。</div></div>';
  var w=window.open('','_blank'); if(!w){{alert('ポップアップを許可してください');return;}} w.document.write(html); w.document.close();
}}

// 新着情報パネル
function newsKind(k){{ return k.includes('新規')?'k-new':k.includes('終了')?'k-end':'k-up'; }}
function renderNews(){{
  if(!NEWS.length) return;
  document.getElementById('newsWrap').style.display='block';
  document.getElementById('newsCnt').textContent=NEWS.length;
  document.getElementById('newsList').innerHTML = NEWS.map(e=>
    `<div class="newsitem" onclick="jumpTo('${{e.自治体名}}')">
      <span class="d">${{e.日付.slice(5)}}</span>
      <span class="k ${{newsKind(e.種別)}}">${{e.種別}}</span>
      <span class="who">${{e.自治体名}}</span>
      <span class="what">${{e.制度名}}：${{e.詳細}}</span>
    </div>`).join('');
}}
function toggleNews(){{
  const l=document.getElementById('newsList'); const open=l.classList.toggle('open');
  document.getElementById('newsTgl').textContent = open?'閉じる ▴':'開く ▾';
}}
function jumpTo(name){{
  // 該当自治体で検索絞り込み（状態フィルタは全開にして必ず見えるように）
  document.getElementById('q').value=name; state.q=name;
  state.status=new Set(['受付中','受付前','終了','未定']);
  document.querySelectorAll('.chip.st').forEach(c=>c.classList.add('on'));
  render();
  document.getElementById('list').scrollIntoView({{behavior:'smooth'}});
}}
renderNews();
render();
</script>
</body>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"生成: {os.path.relpath(OUT, BASE)}  （制度{len(SEIDO)}件: 国{lv['国']}/県{lv['都道府県']}/市{lv['市区町村']} / 機器チップ{len(present)}種）")
