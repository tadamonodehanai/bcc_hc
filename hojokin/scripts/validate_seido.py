#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""制度データ検証ゲート（設計書 §3 の実装・最小版）。
機器マスタと47県CSVを読み、整合性ルールを適用して不整合を報告する。
公開判定: fail が1つでもあれば「保留」、warnは「レビュー」、それ以外は「自動承認」。
"""
import csv, re, sys, datetime, os

TODAY = datetime.date(2026, 7, 11)
BASE = os.path.join(os.path.dirname(__file__), "..", "data")

STATUS_ENUM = {"受付前", "受付中", "まもなく締切", "終了", "未定"}
CONF_ENUM = {"高", "中", "要確認"}
ID_RE = re.compile(r"^(ROB|ICT|FUK)-[0-9]{2}$")
RANGE_RE = re.compile(r"^(ROB|ICT|FUK)-[0-9]{2}〜[0-9]{2}$")  # 範囲短縮表記(スキーマ非準拠)
UNSET = {"要確認", "要確認(要綱PDF)", "未定", ""}

def load_kiki_ids():
    ids = set()
    with open(os.path.join(BASE, "機器マスタ.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids.add(row["機器ID"].strip())
    return ids

def parse_date(s):
    try:
        return datetime.date.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        return None

def validate():
    kiki = load_kiki_ids()
    path = os.path.join(BASE, "制度リスト_都道府県47.csv")
    fails = warns = 0
    rows_with_issues = 0
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            issues = []
            rid, name = row["制度ID"], row["都道府県"]
            status, conf = row["受付状況"].strip(), row["確度"].strip()
            start, deadline = parse_date(row["申請開始"]), parse_date(row["申請締切"])

            # V4 列挙値
            if status not in STATUS_ENUM:
                issues.append(("fail", "V4", f"受付状況が列挙外: {status}"))
            if conf not in CONF_ENUM:
                issues.append(("fail", "V4", f"確度が列挙外: {conf}"))

            # 非正規日付の検出（未定/中旬等）
            for col in ("申請開始", "申請締切"):
                v = row[col].strip()
                if v and v != "未定" and parse_date(v) is None:
                    issues.append(("warn", "V2", f"{col}が非正規日付(要正規化): {v}"))

            # V1 締切 >= 開始
            if start and deadline and deadline < start:
                issues.append(("fail", "V1", f"締切{deadline} < 開始{start}"))

            # V2 状況と日付の整合
            if deadline:
                if status == "受付中" and deadline < TODAY:
                    issues.append(("fail", "V2", f"受付中だが締切{deadline}は過去(→終了へ補正要)"))
                if status == "終了" and deadline >= TODAY:
                    issues.append(("warn", "V2", f"終了だが締切{deadline}は未来"))

            # V3 機器タグ
            for tok in [t for t in row["対象機器タグ"].split("/") if t]:
                tok = tok.strip()
                if RANGE_RE.match(tok):
                    issues.append(("warn", "V3", f"範囲短縮表記(スキーマ非準拠・要展開): {tok}"))
                elif ID_RE.match(tok):
                    if tok not in kiki:
                        issues.append(("fail", "V3", f"機器マスタに存在しないID: {tok}"))
                else:
                    issues.append(("fail", "V3", f"不正な機器タグ形式: {tok}"))

            # V5 確度=高の要件
            if conf == "高":
                if row["補助率"].strip() in UNSET or row["補助上限"].strip() in UNSET:
                    issues.append(("warn", "V5", "確度=高だが補助率/上限が未確定(→中へ降格検討)"))

            if issues:
                rows_with_issues += 1
                print(f"■ {rid} {name}")
                for lvl, rule, msg in issues:
                    mark = "✗FAIL" if lvl == "fail" else "△WARN"
                    print(f"    {mark} [{rule}] {msg}")
                    if lvl == "fail":
                        fails += 1
                    else:
                        warns += 1

    print("\n==== サマリ ====")
    print(f"問題のある行: {rows_with_issues} / 47")
    print(f"FAIL(公開停止相当): {fails}   WARN(レビュー相当): {warns}")
    return fails

if __name__ == "__main__":
    sys.exit(1 if validate() else 0)
