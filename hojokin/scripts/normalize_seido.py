#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""47県CSV → スキーマ準拠JSON への正規化＋自作ミニJSON Schema検証。
- 範囲短縮表記 ROB-01〜13 を明示ID(機器マスタに存在するもの)へ展開
- 曖昧日付(中旬/下旬/頃)は null 化し、原文を メモ に退避
- 補助率/補助上限を数値へ正規化（不明はnull）
- 出力を data/公開_制度_都道府県47.json に書き出し、制度スキーマ.json で検査
依存パッケージなし（標準ライブラリのみ）。
"""
import csv, re, json, os, datetime

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
FETCHED_AT = "2026-07-11T06:00:00+09:00"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RANGE_RE = re.compile(r"^(ROB|ICT|FUK)-(\d{2})〜(\d{2})$")
ID_RE = re.compile(r"^(ROB|ICT|FUK)-\d{2}$")

def load_kiki_ids():
    ids = set()
    with open(os.path.join(BASE, "機器マスタ.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ids.add(r["機器ID"].strip())
    return ids

# ---------- 正規化ヘルパ ----------
def expand_tags(raw, valid_ids):
    out = []
    for tok in [t.strip() for t in raw.split("/") if t.strip()]:
        m = RANGE_RE.match(tok)
        if m:
            pre, a, b = m.group(1), int(m.group(2)), int(m.group(3))
            for n in range(a, b + 1):
                cid = f"{pre}-{n:02d}"
                if cid in valid_ids:
                    out.append(cid)
        elif ID_RE.match(tok):
            if tok in valid_ids:
                out.append(tok)
    # 重複排除（順序保持）
    seen, uniq = set(), []
    for c in out:
        if c not in seen:
            seen.add(c); uniq.append(c)
    return uniq

def norm_date(s):
    s = (s or "").strip()
    return s if DATE_RE.match(s) else None

def norm_ratio(s):
    s = (s or "").strip()
    m = re.match(r"^(\d+)/(\d+)$", s)
    if m and int(m.group(2)):
        return round(int(m.group(1)) / int(m.group(2)), 4)
    return None

def norm_amount(s):
    s = (s or "").strip()
    if s.startswith("要確認"):
        return None
    yen = [int(x) * 10000 for x in re.findall(r"(\d+)万", s)]
    return max(yen) if yen else None

# ---------- CSV → レコード ----------
def build_records(valid_ids):
    recs = []
    path = os.path.join(BASE, "制度リスト_都道府県47.csv")
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = re.sub(r"[^0-9]", "", row["制度ID"])  # P-13 -> 13
            fuzzy = []
            for col in ("申請開始", "申請締切"):
                v = row[col].strip()
                if v and v != "未定" and not DATE_RE.match(v):
                    fuzzy.append(f"{col}原文={v}")
            memo = row.get("備考", "").strip()
            if fuzzy:
                memo = (memo + " / " if memo else "") + "・".join(fuzzy)
            conf = row["確度"].strip()
            rec = {
                "id": row["制度ID"].strip(),
                "実施主体レベル": "都道府県",
                "自治体コード": code.zfill(2),
                "自治体名": row["都道府県"].strip(),
                "制度名": row["制度名"].strip(),
                "カテゴリ": ["ICT・介護ソフト", "介護ロボット"],
                "対象施設": ["介護サービス事業所全般"],
                "対象機器タグ": expand_tags(row["対象機器タグ"], valid_ids),
                "補助率": {"表示": (row["補助率"].strip() or None), "分数": norm_ratio(row["補助率"])},
                "補助上限": {"表示": (row["補助上限"].strip() or None), "金額_円": norm_amount(row["補助上限"])},
                "受付状況": row["受付状況"].strip(),
                "受付開始": norm_date(row["申請開始"]),
                "締切": norm_date(row["申請締切"]),
                "財源": "地域医療介護総合確保基金(介護従事者確保分)",
                "上乗せ元制度ID": None,
                "併用可否": "要確認",
                "窓口": {"担当課": None, "電話": None, "URL": row["公式URL"].strip()},
                "出典": {
                    "公式URL": row["公式URL"].strip(),
                    "要綱PDF_URL": None,
                    "取得日時": FETCHED_AT,
                    "本文ハッシュ": None,
                    "PDFハッシュ": None,
                },
                "確度": conf,
                "メモ": memo or None,
                "抽出メタ": {
                    "抽出モデル": "手動裏取り(集約ページ＋公式ページ)",
                    "抽出日時": FETCHED_AT,
                    "フィールド別自信度": {},
                    "抽出根拠": [],
                    "レビュー状態": "自動承認" if conf == "高" else "レビュー待ち",
                    "検証結果": [],
                },
            }
            recs.append(rec)
    return recs

# ---------- 明示スキーマCSV(国・市区町村) → レコード ----------
def build_explicit(valid_ids, filename):
    recs = []
    path = os.path.join(BASE, filename)
    if not os.path.exists(path):
        return recs
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fuzzy = []
            for col in ("申請開始", "申請締切"):
                v = row[col].strip()
                if v and v != "未定" and not DATE_RE.match(v):
                    fuzzy.append(f"{col}原文={v}")
            memo = row.get("備考", "").strip()
            if fuzzy:
                memo = (memo + " / " if memo else "") + "・".join(fuzzy)
            conf = row["確度"].strip()
            code = row["自治体コード"].strip() or None
            recs.append({
                "id": row["制度ID"].strip(),
                "実施主体レベル": row["実施主体レベル"].strip(),
                "自治体コード": code,
                "自治体名": row["自治体名"].strip(),
                "制度名": row["制度名"].strip(),
                "カテゴリ": [c for c in row["カテゴリ"].split("|") if c],
                "対象施設": [s for s in row["対象施設"].split("|") if s],
                "対象機器タグ": expand_tags(row["対象機器タグ"], valid_ids),
                "補助率": {"表示": (row["補助率"].strip() or None), "分数": norm_ratio(row["補助率"])},
                "補助上限": {"表示": (row["補助上限"].strip() or None), "金額_円": norm_amount(row["補助上限"])},
                "受付状況": row["受付状況"].strip(),
                "受付開始": norm_date(row["申請開始"]),
                "締切": norm_date(row["申請締切"]),
                "財源": row["財源"].strip() or None,
                "上乗せ元制度ID": None,
                "併用可否": "要確認",
                "窓口": {"担当課": None, "電話": None, "URL": row["公式URL"].strip()},
                "出典": {"公式URL": row["公式URL"].strip(), "要綱PDF_URL": None,
                         "取得日時": FETCHED_AT, "本文ハッシュ": None, "PDFハッシュ": None},
                "確度": conf,
                "メモ": memo or None,
                "抽出メタ": {"抽出モデル": "手動裏取り(公式ページ)", "抽出日時": FETCHED_AT,
                            "フィールド別自信度": {}, "抽出根拠": [],
                            "レビュー状態": "自動承認" if conf == "高" else "レビュー待ち", "検証結果": []},
            })
    return recs

# ---------- 依存ゼロのミニJSON Schema検証器 ----------
def validate(inst, schema, path="$", errs=None):
    if errs is None:
        errs = []
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        if not any(_is_type(inst, x) for x in types):
            errs.append(f"{path}: 型不一致 期待={types} 実際={type(inst).__name__}")
            return errs
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: enum外 値={inst!r}")
    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: const不一致")
    if isinstance(inst, str):
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: pattern不一致 値={inst!r}")
        if "minLength" in schema and len(inst) < schema["minLength"]:
            errs.append(f"{path}: 短すぎ")
        if schema.get("format") == "date" and not DATE_RE.match(inst):
            errs.append(f"{path}: date形式でない 値={inst!r}")
        if schema.get("format") == "date-time" and "T" not in inst:
            errs.append(f"{path}: date-time形式でない")
        if schema.get("format") == "uri" and not re.match(r"^https?://", inst):
            errs.append(f"{path}: uri形式でない 値={inst!r}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append(f"{path}: minimum違反")
        if "maximum" in schema and inst > schema["maximum"]:
            errs.append(f"{path}: maximum違反")
    if _is_type(inst, "object") and isinstance(inst, dict):
        for req in schema.get("required", []):
            if req not in inst:
                errs.append(f"{path}: 必須欠落 '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in inst:
                if k not in props:
                    errs.append(f"{path}: 未定義プロパティ '{k}'")
        ap = schema.get("additionalProperties")
        for k, v in inst.items():
            if k in props:
                validate(v, props[k], f"{path}.{k}", errs)
            elif isinstance(ap, dict):
                validate(v, ap, f"{path}.{k}", errs)
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            errs.append(f"{path}: minItems違反")
        if "items" in schema:
            for i, v in enumerate(inst):
                validate(v, schema["items"], f"{path}[{i}]", errs)
    return errs

def _is_type(v, t):
    if t == "object": return isinstance(v, dict)
    if t == "array": return isinstance(v, list)
    if t == "string": return isinstance(v, str)
    if t == "integer": return isinstance(v, int) and not isinstance(v, bool)
    if t == "number": return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean": return isinstance(v, bool)
    if t == "null": return v is None
    return True

# ---------- 新着検知（公開スナップショット差分 → changelog.jsonl） ----------
def _get(r, *keys):
    cur = r
    for k in keys:
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur

def diff_changelog(old_recs, new_recs):
    """公開データの前回版との差分を変更イベント化。ソースを問わず公開時点で必ず捕捉する。"""
    olds = {r["id"]: r for r in old_recs}
    news = {r["id"]: r for r in new_recs}
    today = datetime.date.today().isoformat()
    ev = []
    def add(rec, kind, detail):
        ev.append({"日付": today, "id": rec["id"], "自治体名": rec["自治体名"],
                   "制度名": rec["制度名"], "種別": kind, "詳細": detail})
    CHECKS = [("受付状況", ("受付状況",)), ("締切", ("締切",)),
              ("補助率", ("補助率", "表示")), ("補助上限", ("補助上限", "表示")),
              ("確度", ("確度",))]
    for rid, n in news.items():
        o = olds.get(rid)
        if o is None:
            add(n, "新規掲載", n["制度名"]); continue
        for label, path in CHECKS:
            ov, nv = _get(o, *path), _get(n, *path)
            if ov != nv:
                add(n, f"{label}更新", f"{ov or '—'} → {nv or '—'}")
    for rid, o in olds.items():
        if rid not in news:
            add(o, "掲載終了", o["制度名"])
    return ev

def append_changelog(events):
    if not events:
        return
    with open(os.path.join(BASE, "changelog.jsonl"), "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

def main():
    valid_ids = load_kiki_ids()
    pref = build_records(valid_ids)                             # 47都道府県
    national = build_explicit(valid_ids, "制度リスト_国.csv")       # 国(全国)
    muni = build_explicit(valid_ids, "制度リスト_市区町村.csv")      # 市区町村
    recs = national + pref + muni                              # 国→県→市の順
    # レビュー承認済みの上書き（reviewed_overrides.json）をID一致でマージ
    ovr_path = os.path.join(BASE, "reviewed_overrides.json")
    if os.path.exists(ovr_path):
        ovr = {r["id"]: r for r in json.load(open(ovr_path, encoding="utf-8"))}
        merged = 0
        for i, r in enumerate(recs):
            if r["id"] in ovr:
                recs[i] = ovr[r["id"]]; merged += 1
        for oid, orec in ovr.items():           # 元CSVに無い新規承認レコードも追加
            if oid not in {r["id"] for r in recs}:
                recs.append(orec)
        if merged:
            print(f"レビュー承認の上書き: {merged}件マージ")
    # 47県のみのファイルも継続出力（後方互換）
    with open(os.path.join(BASE, "公開_制度_都道府県47.json"), "w", encoding="utf-8") as f:
        json.dump(pref, f, ensure_ascii=False, indent=2)
    out = os.path.join(BASE, "公開_制度.json")                  # 統合版(UIが参照)
    # 新着検知: 前回の公開版との差分を changelog に追記してから上書き
    if os.path.exists(out):
        prev = json.load(open(out, encoding="utf-8"))
        events = diff_changelog(prev, recs)
        append_changelog(events)
        if events:
            print(f"新着検知: {len(events)}件を changelog.jsonl へ追記")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=2)
    with open(os.path.join(BASE, "制度スキーマ.json"), encoding="utf-8") as f:
        schema = json.load(f)

    total_err = 0
    for r in recs:
        errs = validate(r, schema, f"[{r['id']}]")
        if errs:
            total_err += len(errs)
            print(f"■ {r['id']} {r['自治体名']}")
            for e in errs:
                print("    ✗", e)

    from collections import Counter
    lv = Counter(r["実施主体レベル"] for r in recs)
    high = sum(1 for r in recs if r["確度"] == "高")
    print("\n==== 正規化＆検証サマリ ====")
    print(f"レコード数: {len(recs)}  →  {os.path.relpath(out)}")
    print(f"実施主体レベル別: 国={lv['国']} / 都道府県={lv['都道府県']} / 市区町村={lv['市区町村']}")
    print(f"確度=高: {high} 件")
    print(f"スキーマ検証エラー: {total_err} 件")
    print("判定:", "✅ 全レコード スキーマ準拠" if total_err == 0 else "❌ 要修正")
    return 1 if total_err else 0

if __name__ == "__main__":
    raise SystemExit(main())
