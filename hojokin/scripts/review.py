#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""レビュー人手ゲート。ステージング(crawl_staging.json)の候補を、決定(decisions.json)に従って
承認/却下/保留する。承認レコードは検証を通した上で reviewed_overrides.json に反映し、監査ログを残す。
公開反映は normalize_seido が override をマージすることで行う（このスクリプトは公開DBを直接触らない）。

使い方:
  python3 scripts/review.py list                         # レビュー待ちキューを表示
  python3 scripts/review.py apply --decisions data/decisions.json
decisions.json:
  {"reviewer":"名前",
   "decisions":[
     {"id":"P-27","action":"approve","confidence":"高"},
     {"id":"P-07","action":"approve","confidence":"高","edits":{"締切":"2026-07-31"}},
     {"id":"P-26","action":"hold","note":"上限が要綱内・未取得"},
     {"id":"P-11","action":"reject","note":"別事業と重複"}
   ]}
"""
import os, sys, json, argparse, datetime, importlib.util

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
STAGING = os.path.join(DATA, "crawl_staging.json")
OVERRIDES = os.path.join(DATA, "reviewed_overrides.json")
AUDIT = os.path.join(DATA, "review_audit.jsonl")

def _load(mod, path):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(BASE, "scripts", path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
NZ = _load("normalize_seido", "normalize_seido.py")

def load_json(p, default):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def set_dotted(rec, key, val):
    """'補助上限.金額_円' のようなドットキーで値を設定。"""
    parts = key.split("."); cur = rec
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = val

def cmd_list(_):
    staging = load_json(STAGING, [])
    if not staging:
        print("レビュー待ちなし（crawl_staging.json が空）"); return
    print(f"=== レビュー待ち {len(staging)} 件 ===")
    for r in staging:
        rv = r["抽出メタ"]["レビュー状態"]
        print(f"  {r['id']} {r['自治体名']:6} 確度{r['確度']}／{rv}／締切{r['締切'] or '-'}"
              f"／率{r['補助率']['表示'] or '-'}／上限{r['補助上限']['表示'] or '-'}／機器{len(r['対象機器タグ'])}")

def merge_from_public(rec, pub):
    """クローラ抽出が欠損の項目は、現公開値を保持（上書きでの良データ消失を防ぐ）。"""
    if not pub:
        return rec
    if not rec.get("締切") and pub.get("締切"): rec["締切"] = pub["締切"]
    if not rec.get("受付開始") and pub.get("受付開始"): rec["受付開始"] = pub["受付開始"]
    if rec["補助率"].get("分数") is None and not rec["補助率"].get("表示") and pub.get("補助率"):
        rec["補助率"] = pub["補助率"]
    if rec["補助上限"].get("金額_円") is None and not rec["補助上限"].get("表示") and pub.get("補助上限"):
        rec["補助上限"] = pub["補助上限"]
    if not rec.get("対象機器タグ") and pub.get("対象機器タグ"): rec["対象機器タグ"] = pub["対象機器タグ"]
    return rec

def cmd_apply(args):
    staging_list = load_json(STAGING, [])
    staging = {r["id"]: r for r in staging_list}
    overrides = {r["id"]: r for r in load_json(OVERRIDES, [])}
    public = {r["id"]: r for r in load_json(os.path.join(DATA, "公開_制度.json"), [])}
    resolved = set()   # 承認/却下で決着→キューから除去（保留・検証NGは残す）
    dec = json.load(open(args.decisions, encoding="utf-8"))
    reviewer = dec.get("reviewer", "unknown")
    now = datetime.datetime.now().replace(microsecond=0).isoformat() + "+09:00"
    schema = json.load(open(os.path.join(DATA, "制度スキーマ.json"), encoding="utf-8"))
    audit = []
    approved = rejected = held = refused = 0

    for d in dec.get("decisions", []):
        rid, action = d["id"], d["action"]
        rec = staging.get(rid)
        if rec is None:
            print(f"  ! {rid}: ステージングに無し（スキップ）"); continue
        if action == "approve":
            rec = json.loads(json.dumps(rec))            # copy
            rec = merge_from_public(rec, public.get(rid))  # 欠損は現公開値を保持
            for k, v in (d.get("edits") or {}).items():
                set_dotted(rec, k, v)
            if "confidence" in d:
                rec["確度"] = d["confidence"]
            rec["抽出メタ"]["レビュー状態"] = "レビュー済"
            rec["抽出メタ"]["レビュアー"] = reviewer
            rec["抽出メタ"]["レビュー日時"] = now
            errs = NZ.validate(rec, schema, f"[{rid}]")
            if errs:
                refused += 1
                print(f"  ✗ {rid}: 承認を却下（検証NG {len(errs)}件）: {errs[0]}")
                audit.append({"id": rid, "action": "refuse", "reason": errs[:3], "at": now, "by": reviewer})
                continue
            overrides[rid] = rec
            resolved.add(rid)
            approved += 1
            print(f"  ✓ {rid} {rec['自治体名']}: 承認→公開上書き（確度{rec['確度']}"
                  + (f"・編集{list((d.get('edits') or {}).keys())}" if d.get("edits") else "") + "）")
            audit.append({"id": rid, "action": "approve", "confidence": rec["確度"],
                          "edits": d.get("edits") or {}, "at": now, "by": reviewer})
        elif action in ("reject", "hold"):
            if action == "reject" and rid in overrides:
                del overrides[rid]                        # 既存の公開上書きを撤回
            if action == "reject":
                rejected += 1; resolved.add(rid)          # 却下→キューから除去
            else:
                held += 1                                 # 保留→キューに残す
            print(f"  – {rid}: {action}（{d.get('note','')}）")
            audit.append({"id": rid, "action": action, "note": d.get("note", ""), "at": now, "by": reviewer})
        else:
            print(f"  ? {rid}: 未知のaction '{action}'")

    json.dump(list(overrides.values()), open(OVERRIDES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    remaining = [r for r in staging_list if r["id"] not in resolved]   # 決着分をキューから除去
    json.dump(remaining, open(STAGING, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(AUDIT, "a", encoding="utf-8") as f:
        for a in audit:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(f"\n=== 結果 ===")
    print(f"承認{approved} / 却下{rejected} / 保留{held} / 検証却下{refused}")
    print(f"ステージング残: {len(remaining)}件（決着{len(resolved)}件を除去・保留/検証NGは残置）")
    print(f"公開上書きストア: {os.path.relpath(OVERRIDES, BASE)}（{len(overrides)}件）")
    print(f"監査ログ追記: {os.path.relpath(AUDIT, BASE)}")
    print("→ 公開反映は `python3 scripts/normalize_seido.py` で override がマージされる")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    a = sub.add_parser("apply"); a.add_argument("--decisions", required=True)
    args = ap.parse_args()
    {"list": cmd_list, "apply": cmd_apply}[args.cmd](args)

if __name__ == "__main__":
    main()
