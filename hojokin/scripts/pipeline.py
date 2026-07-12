#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""運用オーケストレータ。
  python3 scripts/pipeline.py refresh   # 公開データ→ポータル→レビューUI を一括再生成
  python3 scripts/pipeline.py status    # パイプライン健全性ダッシュボード
標準的な運用: crawler → (review apply) → pipeline refresh。
"""
import os, sys, json, csv, subprocess
from collections import Counter

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
SC = os.path.join(BASE, "scripts")

def load(p, d):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

def run(script):
    print(f"— {script}")
    r = subprocess.run([sys.executable, os.path.join(SC, script)], capture_output=True, text=True)
    tail = [l for l in r.stdout.strip().splitlines() if l][-2:]
    for l in tail:
        print("   " + l)
    if r.returncode != 0:
        print("   ! エラー:", r.stderr.strip()[:200])
    return r.returncode

def cmd_refresh(_):
    print("=== refresh: 公開データ→UI 一括再生成 ===")
    for s in ("normalize_seido.py", "build_portal.py", "build_hikaku.py", "build_review.py"):
        run(s)
    # 回帰テスト（逆引き・重層・フィルタ）: 失敗したら明示
    print("— test_portal.js（回帰テスト）")
    t = subprocess.run(["node", os.path.join(SC, "test_portal.js")], capture_output=True, text=True)
    tail = [l for l in t.stdout.strip().splitlines() if l][-1:]
    for l in tail:
        print("   " + l)
    if t.returncode != 0:
        print("   ❌ 回帰テスト失敗 — UIを公開する前に要修正")
    print("完了。")

def bar(counter, keys):
    parts = []
    for k in keys:
        if counter.get(k):
            parts.append(f"{k} {counter[k]}")
    return " / ".join(parts) if parts else "—"

def cmd_status(_):
    pub = load(os.path.join(DATA, "公開_制度.json"), [])
    staging = load(os.path.join(DATA, "crawl_staging.json"), [])
    overrides = load(os.path.join(DATA, "reviewed_overrides.json"), [])
    state = load(os.path.join(DATA, "crawl_state.json"), {})
    def load_tier(name):
        p = os.path.join(DATA, name)
        return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []
    tier1 = load_tier("市区町村シード_Tier1.csv")
    tier2 = load_tier("市区町村シード_Tier2.csv")
    audit_n = sum(1 for _ in open(os.path.join(DATA, "review_audit.jsonl"), encoding="utf-8")) \
        if os.path.exists(os.path.join(DATA, "review_audit.jsonl")) else 0

    conf = Counter(r["確度"] for r in pub)
    lv = Counter(r["実施主体レベル"] for r in pub)
    reviewed = sum(1 for r in pub if r["抽出メタ"].get("レビュー状態") == "レビュー済")
    last = max((v.get("last_checked", "") for v in state.values()), default="—")
    t1 = Counter(r["収集ステータス"] for r in tier1)

    print("╔══════════════ ケアシル パイプライン状況 ══════════════")
    print(f"║ 公開制度         : {len(pub)} 件  [{bar(lv,['国','都道府県','市区町村'])}]")
    print(f"║ 確度分布         : {bar(conf,['高','中','要確認'])}  (うちレビュー済 {reviewed})")
    print(f"║ レビュー待ち     : {len(staging)} 件（crawl_staging）")
    print(f"║ 公開上書き       : {len(overrides)} 件（reviewed_overrides）／監査ログ {audit_n} 行")
    print(f"║ クロール最終確認 : {last}（{len(state)} URL 記録）")
    if tier1:
        print(f"║ Tier1台帳(43)    : {bar(t1,['収集済','県事業カバー','要収集','未収集'])}")
    import os as _os
    llm = "有効(APIキーあり)" if _os.environ.get("ANTHROPIC_API_KEY") else "フォールバック(rule-based・ANTHROPIC_API_KEY未設定)"
    print(f"║ LLM抽出          : {llm}")
    if tier2:
        t2 = Counter(r["収集ステータス"] for r in tier2)
        print(f"║ Tier2台帳({len(tier2)})    : {bar(t2,['収集済','県事業カバー','要収集','未収集'])}")
    print("╚═══════════════════════════════════════════════════════")
    # 締切アラート（受付中で締切7日以内）
    import datetime
    today = datetime.date.today()
    soon = []
    for r in pub:
        if r["受付状況"] == "受付中" and r["締切"]:
            try:
                d = (datetime.date.fromisoformat(r["締切"]) - today).days
                if 0 <= d <= 7: soon.append((d, r["自治体名"], r["締切"]))
            except ValueError: pass
    if soon:
        print("⚠ 締切7日以内（受付中）:")
        for d, name, dl in sorted(soon):
            print(f"   あと{d}日 {name} {dl}")

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"refresh": cmd_refresh, "status": cmd_status}.get(cmd, cmd_status)(None)

if __name__ == "__main__":
    main()
