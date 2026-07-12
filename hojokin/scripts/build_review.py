#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""レビューUIを生成。crawl_staging.json の候補を、現公開値との差分・抽出根拠つきで表示し、
承認/保留/却下＋編集の決定を decisions.json 形式でエクスポートする（review.py が適用）。
file:// で動くようデータ埋め込み・依存なし。"""
import os, json

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "review.html")

staging = json.load(open(os.path.join(DATA, "crawl_staging.json"), encoding="utf-8"))
public = {r["id"]: r for r in json.load(open(os.path.join(DATA, "公開_制度.json"), encoding="utf-8"))}

S_JSON = json.dumps(staging, ensure_ascii=False)
P_JSON = json.dumps(public, ensure_ascii=False)

HTML = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ケアシル｜レビュー（承認→公開ゲート）</title>
<style>
  :root{{--navy:#0F2540;--teal:#12B3AE;--teal-d:#0E9490;--teal-soft:#E6F7F6;--line:#E4E9F0;--bg:#F5F8FB;
    --card:#fff;--muted:#6B7A8D;--ok:#1E9E6A;--ok-soft:#E7F5EE;--warn:#E8873B;--warn-soft:#FDF1E6;--danger:#D8503E;--danger-soft:#FBE9E6;}}
  *{{box-sizing:border-box}} body{{margin:0;font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP",system-ui,sans-serif;background:var(--bg);color:#1b2a3a}}
  header{{background:linear-gradient(120deg,var(--navy),#153154);color:#fff;padding:13px 24px;position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:14px}}
  header b{{font-size:17px}} header small{{color:#9fb4cc;font-size:12px}}
  .bar{{margin-left:auto;display:flex;gap:10px;align-items:center}}
  .btn{{border:0;border-radius:9px;padding:9px 15px;font-weight:800;font-size:13px;cursor:pointer;background:var(--teal);color:#fff}}
  .btn.ghost{{background:rgba(255,255,255,.12);color:#fff}}
  .wrap{{max-width:1080px;margin:18px auto 60px;padding:0 20px}}
  .sum{{color:var(--muted);font-size:13px;margin-bottom:14px}} .sum b{{color:var(--navy)}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:14px;box-shadow:0 8px 24px rgba(15,37,64,.05)}}
  .top{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
  .gov{{font-size:11.5px;font-weight:700;background:#EEF1F5;color:var(--navy);padding:4px 10px;border-radius:7px}}
  .ttl{{font-weight:800;color:var(--navy);font-size:15.5px}}
  .conf{{margin-left:auto;font-size:11.5px;font-weight:800;padding:4px 10px;border-radius:999px;background:#F1F4F8;color:#516481}}
  table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}}
  th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
  th{{color:var(--muted);font-weight:700;font-size:11.5px;width:22%}}
  .old{{color:var(--muted)}} .new{{font-weight:700;color:var(--navy)}}
  .chg{{background:var(--warn-soft)}} .chg .new{{color:var(--warn)}}
  .ev{{font-size:11.5px;color:#2f6f6d;background:var(--teal-soft);border:1px solid #c7e6e5;border-radius:8px;padding:8px 10px;margin:2px 0}}
  .ev b{{color:var(--teal-d)}}
  .src{{font-size:11.5px}} .src a{{color:var(--teal-d);font-weight:700}}
  .decide{{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}}
  .decide label{{font-size:13px;font-weight:700;display:inline-flex;align-items:center;gap:5px;cursor:pointer}}
  .decide .r-approve{{color:var(--ok)}} .decide .r-hold{{color:var(--warn)}} .decide .r-reject{{color:var(--danger)}}
  .edits{{display:none;gap:8px;flex-wrap:wrap;margin-top:10px}} .edits.show{{display:flex}}
  .edits input{{font-size:12.5px;padding:6px 8px;border:1px solid var(--line);border-radius:7px}}
  .edits .fld{{display:flex;flex-direction:column;gap:3px}} .edits .fld span{{font-size:10.5px;color:var(--muted)}}
  .note{{flex:1;min-width:180px;font-size:12.5px;padding:6px 8px;border:1px solid var(--line);border-radius:7px}}
  .out{{background:#0f1b2a;color:#cfe0f0;border-radius:12px;padding:14px;font-family:ui-monospace,monospace;font-size:12px;white-space:pre-wrap;max-height:260px;overflow:auto;margin-top:10px}}
  .flag{{font-size:11px;font-weight:800;padding:3px 8px;border-radius:6px;margin-left:6px}}
  .f-ok{{background:var(--ok-soft);color:var(--ok)}} .f-warn{{background:var(--warn-soft);color:var(--warn)}}
</style>
<header>
  <div><b>🩺 ケアシル レビュー</b> <small>ステージング → 承認 → 公開ゲート</small></div>
  <div class="bar">
    <button class="btn ghost" onclick="bulk('hold')">全部 保留</button>
    <button class="btn" onclick="exportDecisions()">決定をエクスポート（decisions.json）</button>
  </div>
</header>
<div class="wrap">
  <div class="sum" id="sum"></div>
  <div id="list"></div>
  <div id="outwrap" style="display:none">
    <div class="sum">↓ これを <b>data/decisions.json</b> に保存し <code>python3 scripts/review.py apply --decisions data/decisions.json</code> を実行、続けて <code>normalize_seido.py</code>→<code>build_portal.py</code> で公開反映。</div>
    <div class="out" id="out"></div>
    <button class="btn" onclick="dl()">ファイルとしてダウンロード</button>
    <button class="btn ghost" onclick="copyOut()">コピー</button>
  </div>
</div>
<script>
const STAGING = {S_JSON};
const PUBLIC = {P_JSON};
const REVIEWER = "shin.tanaka";
const disp = v => (v===null||v===undefined||v==="")?"—":v;

function pubVal(id, field){{
  const p = PUBLIC[id]; if(!p) return "（新規）";
  if(field==="締切") return disp(p.締切);
  if(field==="補助率") return disp(p.補助率 && p.補助率.表示);
  if(field==="補助上限") return disp(p.補助上限 && p.補助上限.表示);
  if(field==="対象機器") return (p.対象機器タグ||[]).length+"種";
  return "—";
}}
function newVal(r, field){{
  if(field==="締切") return disp(r.締切);
  if(field==="補助率") return disp(r.補助率.表示);
  if(field==="補助上限") return disp(r.補助上限.表示);
  if(field==="対象機器") return r.対象機器タグ.length+"種";
}}
function row(r, field){{
  const o=pubVal(r.id,field), n=newVal(r,field), chg=(o!==n);
  return `<tr class="${{chg?'chg':''}}"><th>${{field}}</th><td class="old">${{o}}</td><td class="new">${{n}}</td></tr>`;
}}
function card(r){{
  const vNG = (r.抽出メタ.検証結果||[]).some(v=>v.判定==='fail');
  const flag = vNG?'<span class="flag f-warn">検証NG</span>':'<span class="flag f-ok">検証pass</span>';
  const ev = (r.抽出メタ.抽出根拠||[]).map(e=>`<div class="ev"><b>${{e.フィールド}}</b>：「${{e.原文引用}}」<span style="color:#6B7A8D">(${{e.出典箇所}})</span></div>`).join('');
  const pdf = r.出典.要綱PDF_URL?`<a href="${{r.出典.要綱PDF_URL}}" target="_blank">要綱PDF</a>`:'要綱PDFなし';
  return `<div class="card" data-id="${{r.id}}">
    <div class="top"><span class="gov">${{r.自治体名}}</span><span class="ttl">${{r.制度名}}</span>
      <span class="conf">抽出確度 ${{r.確度}} ${{flag}}</span></div>
    <table><tr><th>項目</th><td class="old">現在の公開値</td><td class="new">クローラ抽出値</td></tr>
      ${{['締切','補助率','補助上限','対象機器'].map(f=>row(r,f)).join('')}}</table>
    ${{ev}}
    <div class="src" style="margin-top:8px">出典：<a href="${{r.出典.公式URL}}" target="_blank">公式ページ</a>／${{pdf}}／取得 ${{r.出典.取得日時.slice(0,10)}}</div>
    <div class="decide">
      <label class="r-approve"><input type="radio" name="a-${{r.id}}" value="approve" onchange="toggleEdit('${{r.id}}',true)">承認</label>
      <label class="r-hold"><input type="radio" name="a-${{r.id}}" value="hold" checked onchange="toggleEdit('${{r.id}}',false)">保留</label>
      <label class="r-reject"><input type="radio" name="a-${{r.id}}" value="reject" onchange="toggleEdit('${{r.id}}',false)">却下</label>
      <input class="note" id="note-${{r.id}}" placeholder="メモ（保留/却下の理由など）">
    </div>
    <div class="edits" id="edits-${{r.id}}">
      <div class="fld"><span>確度に昇格</span><select id="conf-${{r.id}}"><option>高</option><option selected>中</option></select></div>
      <div class="fld"><span>締切を修正(YYYY-MM-DD)</span><input id="ed-締切-${{r.id}}" value="${{disp(r.締切)==='—'?'':r.締切}}"></div>
      <div class="fld"><span>補助率(表示)</span><input id="ed-率-${{r.id}}" value="${{disp(r.補助率.表示)==='—'?'':r.補助率.表示}}"></div>
      <div class="fld"><span>補助上限(表示)</span><input id="ed-上限-${{r.id}}" value="${{disp(r.補助上限.表示)==='—'?'':r.補助上限.表示}}"></div>
    </div>
  </div>`;
}}
function toggleEdit(id, show){{ document.getElementById('edits-'+id).classList.toggle('show', show); }}
function bulk(action){{ document.querySelectorAll('input[type=radio][value='+action+']').forEach(r=>{{r.checked=true;r.dispatchEvent(new Event('change'));}}); }}

function exportDecisions(){{
  const decisions=[];
  STAGING.forEach(r=>{{
    const action=document.querySelector('input[name=a-'+r.id+']:checked').value;
    const note=document.getElementById('note-'+r.id).value.trim();
    const d={{id:r.id, action}};
    if(action==='approve'){{
      d.confidence=document.getElementById('conf-'+r.id).value;
      const edits={{}};
      const dd=document.getElementById('ed-締切-'+r.id).value.trim();
      if(dd && dd!==(r.締切||'')) edits['締切']=dd;
      const rr=document.getElementById('ed-率-'+r.id).value.trim();
      if(rr && rr!==(r.補助率.表示||'')) edits['補助率.表示']=rr;
      const uu=document.getElementById('ed-上限-'+r.id).value.trim();
      if(uu && uu!==(r.補助上限.表示||'')) edits['補助上限.表示']=uu;
      if(Object.keys(edits).length) d.edits=edits;
    }} else if(note) d.note=note;
    decisions.push(d);
  }});
  const payload=JSON.stringify({{reviewer:REVIEWER, decisions}}, null, 2);
  document.getElementById('out').textContent=payload;
  document.getElementById('outwrap').style.display='block';
  window._payload=payload;
}}
function dl(){{
  const a=document.createElement('a');
  a.href='data:application/json;charset=utf-8,'+encodeURIComponent(window._payload||'');
  a.download='decisions.json'; a.click();
}}
function copyOut(){{ navigator.clipboard && navigator.clipboard.writeText(window._payload||''); }}

document.getElementById('sum').innerHTML=`レビュー待ち <b>${{STAGING.length}}</b> 件。承認すると公開上書きに反映（保留/却下は反映しない）。`;
document.getElementById('list').innerHTML=STAGING.map(card).join('');
</script>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"生成: {os.path.relpath(OUT, BASE)}（レビュー待ち {len(staging)}件）")
