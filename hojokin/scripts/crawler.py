#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ケアシル 実クローラ v0.1（設計書 §0 フローの実装）。
 取得(HTML+PDFリンク検出) → ハッシュ差分検知 → 抽出(ルールベース) → 機器正規化
 → スキーマ検証(既存部品を再利用) → 確度判定 → ステージング出力。
実LLM抽出は Extractor 差し替えで対応（本版はAPIキー不要のルールベース抽出で end-to-end 実証）。

使い方:
  python3 scripts/crawler.py            # 受付中の都道府県から5件を実クロール
  python3 scripts/crawler.py --limit 3
  python3 scripts/crawler.py --ids P-07,P-11,P-47
状態は data/crawl_state.json に保持し、2回目以降は本文ハッシュ差分がある時だけ再抽出する。
"""
import os, sys, re, io, csv, json, time, hashlib, datetime, argparse, importlib.util
import urllib.request, urllib.robotparser, urllib.parse, socket

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
STATE = os.path.join(DATA, "crawl_state.json")
STAGING = os.path.join(DATA, "crawl_staging.json")
UA = "CaresilBot/0.1 (+https://caresil.example/bot; contact: ops@caresil.example)"
socket.setdefaulttimeout(12)

# ---- 既存パイプライン部品の再利用（重複実装しない＝バグ源を増やさない）----
def _load(mod, path):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(BASE, "scripts", path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
NZ = _load("normalize_seido", "normalize_seido.py")  # validate, norm_*, expand_tags, load_kiki_ids

def load_synonyms():
    syn = []  # (シノニム, 機器ID) 長い順にマッチ
    with open(os.path.join(DATA, "シノニム辞書.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            syn.append((r["シノニム"], r["機器ID"]))
    return sorted(syn, key=lambda x: -len(x[0]))

# ---- 取得 ----
def fetch(url):
    try:
        rp = urllib.robotparser.RobotFileParser()
        p = urllib.parse.urlparse(url)
        rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
        try: rp.read()
        except Exception: pass
        if rp.default_entry is not None and not rp.can_fetch(UA, url):
            return None, "robots_disallow"
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req) as r:
            raw = r.read()
        enc = "utf-8"
        m = re.search(rb'charset=["\']?([\w-]+)', raw[:2000], re.I)
        if m:
            enc = m.group(1).decode("ascii", "ignore")
        return raw.decode(enc, "ignore"), None
    except Exception as e:
        return None, f"{type(e).__name__}:{str(e)[:60]}"

def html_to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", text).strip()

def find_pdf_links(html, base_url):
    """(url, アンカー文言) の一覧。アンカーは要綱判定に使う。"""
    out = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        anchor = re.sub(r"<[^>]+>", "", m.group(2)).strip()[:50]
        out.append((urllib.parse.urljoin(base_url, m.group(1)), anchor))
    # アンカー無しの裸リンクも拾う
    for l in re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.I):
        u = urllib.parse.urljoin(base_url, l)
        if u not in [x[0] for x in out]:
            out.append((u, ""))
    seen, uniq = set(), []
    for u, a in out:
        if u not in seen:
            seen.add(u); uniq.append((u, a))
    return uniq

YOUKOU = re.compile(r"要綱|要領|募集|交付|チラシ|ちらし|概要|手引|リーフレット")

def pick_youkou(links):
    """要綱/募集要項らしいPDFを優先選択（数値の一次情報源）。"""
    for u, a in links:
        if YOUKOU.search(a) or YOUKOU.search(u):
            return u
    return links[0][0] if links else None

def encode_url(url):
    """パスに日本語等の非ASCIIを含むURLを安全にエンコード（自治体PDFで頻出）。"""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), p.query, ""))

def pdf_text(url, max_pages=8):
    """要綱PDF本文をpypdfで抽出（未導入/失敗時は空文字で安全に劣化）。"""
    try:
        import pypdf
    except Exception:
        return ""
    try:
        req = urllib.request.Request(encode_url(url), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    except Exception:
        return ""

# ---- 抽出（ルールベース v0：LLM差し替え可能なインターフェース）----
WAREKI = re.compile(r"令和(\d+)年(\d+)月(\d+)日")
ISO = re.compile(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})")
RATIO = re.compile(r"(\d+)\s*分の\s*(\d+)|(\d+)\s*/\s*(\d+)")
YEN = re.compile(r"([0-9][0-9,]*)\s*万円")

def _iso(y, m, d):
    try: return datetime.date(int(y), int(m), int(d)).isoformat()
    except ValueError: return None

class RuleBasedExtractor:
    name = "rule-based v0"
    def __init__(self, synonyms): self.syn = synonyms
    def extract(self, text):
        ev, out = [], {}
        # 締切（「締切/期限/必着/まで」近傍の最終日付を優先）
        cands = []
        for m in WAREKI.finditer(text):
            iso = _iso(2018 + int(m.group(1)), m.group(2), m.group(3))
            if iso: cands.append((m.start(), iso, m.group(0)))
        for m in ISO.finditer(text):
            iso = _iso(m.group(1), m.group(2), m.group(3))
            if iso: cands.append((m.start(), iso, m.group(0)))
        if cands:
            # 「締切/期限/必着/締切/エントリー」語の近傍を優先、無ければ最遅日
            key = None
            for pos, iso, s in cands:
                ctx = text[max(0, pos-12):pos]
                if re.search(r"締切|期限|必着|まで|〆", ctx):
                    key = (iso, s); break
            if not key:
                latest = max(cands, key=lambda c: c[1]); key = (latest[1], latest[2])
            out["締切"] = key[0]; ev.append({"フィールド": "締切", "原文引用": key[1], "出典箇所": "本文"})
        # 補助率（最大）。「X分のY」= Y/X。スラッシュ形は補助率らしい小さな分母のみ採用しURL中の数字誤検出を防ぐ
        best = None
        for m in RATIO.finditer(text):
            try:
                if m.group(1):            # 「5分の4」→ 4/5
                    den, num = int(m.group(1)), int(m.group(2)); disp = m.group(0)
                else:                      # 「4/5」形は分母10以下・分子<分母に限定（URL数字を除外）
                    num, den = int(m.group(3)), int(m.group(4)); disp = m.group(0)
                    if den > 10 or num >= den:
                        continue
                r = num / den
                if 0 < r <= 1 and (best is None or r > best[0]):
                    best = (r, disp)
            except (ValueError, ZeroDivisionError): pass
        if best:
            out["補助率"] = {"表示": best[1].replace(" ", ""), "分数": round(best[0], 4)}
            ev.append({"フィールド": "補助率", "原文引用": best[1], "出典箇所": "本文"})
        # 補助上限（万円の最大＝代表額）
        yens = [(int(x.replace(",", "")) * 10000, x) for x in YEN.findall(text)]
        yens = [(v, s) for v, s in yens if 100000 <= v <= 100000000]  # 10万〜1億の常識レンジ
        if yens:
            v, s = max(yens, key=lambda z: z[0])
            out["補助上限"] = {"表示": f"{s}万円", "金額_円": v}
            ev.append({"フィールド": "補助上限", "原文引用": f"{s}万円", "出典箇所": "本文"})
        # 対象機器（シノニム辞書でヒット→機器ID）
        hit, matched = [], []
        for word, kid in self.syn:
            if word in text and kid not in hit:
                hit.append(kid); matched.append(f"{word}→{kid}")
        if hit:
            out["対象機器タグ"] = hit
            ev.append({"フィールド": "対象機器タグ", "原文引用": "・".join(matched[:6]), "出典箇所": "本文"})
        # 対象施設
        FAC = [("特別養護老人ホーム", "特養"), ("特養", "特養"), ("介護老人保健施設", "老健"),
               ("グループホーム", "GH"), ("通所", "通所"), ("訪問介護", "訪問介護"),
               ("小規模多機能", "小多機"), ("養護老人ホーム", "養護老人ホーム"), ("軽費老人ホーム", "軽費老人ホーム")]
        fac = []
        for kw, tag in FAC:
            if kw in text and tag not in fac: fac.append(tag)
        out["対象施設"] = fac or ["介護サービス事業所全般"]
        return out, ev

# LLM抽出: 公式SDK + structured outputs(スキーマ強制)。出力が必ずスキーマに適合するため
# 「JSONで返して」方式のパース失敗という類型のバグが構造的に発生しない。
LLM_SYSTEM = """あなたは日本の介護補助金の募集要綱を読む厳密な情報抽出器です。
与えられた本文(HTML＋要綱PDF)から制度情報を抽出してください。
規則:
- 推測で埋めない。本文に明記のない値は null。数値は本文に明記された値のみ。
- 「締切」は申請/事前協議/エントリーの締切。導入・支払・実績報告の完了期限と厳密に区別する。
- 「対象機器タグ」は機器マスタID(ROB-01〜13/ICT-01〜12/FUK-01〜05)のみ。本文の機器名から該当IDへ正規化する。
- 各値には抽出根拠(原文引用と出典箇所)を必ず付ける。"""

LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "締切": {"type": ["string", "null"]},
        "受付開始": {"type": ["string", "null"]},
        "補助率": {"type": "object", "properties": {
            "表示": {"type": ["string", "null"]}, "分数": {"type": ["number", "null"]}},
            "required": ["表示", "分数"], "additionalProperties": False},
        "補助上限": {"type": "object", "properties": {
            "表示": {"type": ["string", "null"]}, "金額_円": {"type": ["integer", "null"]}},
            "required": ["表示", "金額_円"], "additionalProperties": False},
        "対象施設": {"type": "array", "items": {"type": "string"}},
        "対象機器タグ": {"type": "array", "items": {"type": "string"}},
        "抽出根拠": {"type": "array", "items": {"type": "object", "properties": {
            "フィールド": {"type": "string"}, "原文引用": {"type": "string"},
            "出典箇所": {"type": "string"}},
            "required": ["フィールド", "原文引用", "出典箇所"], "additionalProperties": False}},
    },
    "required": ["締切", "受付開始", "補助率", "補助上限", "対象施設", "対象機器タグ", "抽出根拠"],
    "additionalProperties": False,
}

class LLMExtractor:
    """本番用の高精度抽出（公式SDK + structured outputs）。
    ANTHROPIC_API_KEY 未設定/SDK未導入なら available()=False → 呼び出し側がルールベースへフォールバック。"""
    name = "llm (claude / structured-outputs)"
    def __init__(self, synonyms=None, model=None):
        # 抽出タスクの既定は claude-sonnet-5（精度/コストの均衡）。CARESIL_LLM_MODEL で変更可:
        # claude-haiku-4-5=最安・単純抽出向き / claude-opus-4-8=最高精度・難読要綱向き
        self.model = model or os.environ.get("CARESIL_LLM_MODEL", "claude-sonnet-5")
        self._client = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic
                self._client = anthropic.Anthropic()  # 429/5xxのリトライはSDKが自動処理
            except ImportError:
                pass
    def available(self):
        return self._client is not None
    def extract(self, text):
        if not self.available():
            raise RuntimeError("ANTHROPIC_API_KEY 未設定またはSDK未導入（ルールベースへフォールバック）")
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=LLM_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": LLM_SCHEMA}},
            messages=[{"role": "user", "content": text[:16000]}],
        )
        raw = next(b.text for b in resp.content if b.type == "text")
        out = json.loads(raw)  # structured outputs によりスキーマ適合が保証される
        ev = out.pop("抽出根拠", [])
        return {k: v for k, v in out.items() if v not in (None, [], "")}, ev

# ---- レコード組み立て＋検証 ----
def build_candidate(seed, extracted, ev, html, youkou_url, pdf_count, valid_ids, extractor_name):
    now = datetime.datetime.now().replace(microsecond=0).isoformat() + "+09:00"
    tags = extracted.get("対象機器タグ") or NZ.expand_tags("ROB-01〜13/ICT-01〜09", valid_ids)
    tags = [t for t in tags if t in valid_ids]
    rec = {
        "id": seed["id"], "実施主体レベル": seed["実施主体レベル"],
        "自治体コード": seed["自治体コード"] or None, "自治体名": seed["自治体名"],
        "制度名": seed["制度名"], "カテゴリ": ["ICT・介護ソフト", "介護ロボット"],
        "対象施設": extracted.get("対象施設", ["介護サービス事業所全般"]),
        "対象機器タグ": tags,
        "補助率": extracted.get("補助率", {"表示": None, "分数": None}),
        "補助上限": extracted.get("補助上限", {"表示": None, "金額_円": None}),
        "受付状況": seed.get("受付状況", "未定"),
        "受付開始": None, "締切": extracted.get("締切"),
        "財源": "地域医療介護総合確保基金(介護従事者確保分)",
        "上乗せ元制度ID": None, "併用可否": "要確認",
        "窓口": {"担当課": None, "電話": None, "URL": seed["url"]},
        "出典": {"公式URL": seed["url"], "要綱PDF_URL": youkou_url,
                 "取得日時": now, "本文ハッシュ": None, "PDFハッシュ": None},
        "確度": "中", "メモ": f"クローラ自動抽出(要綱PDF{'あり' if youkou_url else 'なし'}・PDF{pdf_count}本検出)",
        "抽出メタ": {"抽出モデル": extractor_name, "抽出日時": now,
                    "フィールド別自信度": {}, "抽出根拠": ev,
                    "レビュー状態": "レビュー待ち", "検証結果": []},
    }
    rec["出典"]["本文ハッシュ"] = hashlib.sha256(html.encode("utf-8", "ignore")).hexdigest()
    # スキーマ検証（既存の依存ゼロ検証器を再利用）
    with open(os.path.join(DATA, "制度スキーマ.json"), encoding="utf-8") as f:
        schema = json.load(f)
    errs = NZ.validate(rec, schema, f"[{rec['id']}]")
    # 確度判定：数値が揃い検証通過→中、欠落→要確認、検証NG→保留
    if errs:
        rec["確度"] = "要確認"; rec["抽出メタ"]["レビュー状態"] = "保留(検証NG)"
        rec["抽出メタ"]["検証結果"] = [{"ルール": "schema", "判定": "fail", "詳細": e} for e in errs[:5]]
    else:
        got = sum(1 for k in ("締切", "補助率", "補助上限") if rec.get(k) and (rec[k] if k == "締切" else rec[k].get("分数") or rec[k].get("金額_円")))
        rec["確度"] = "中" if got >= 2 else "要確認"
        rec["抽出メタ"]["検証結果"] = [{"ルール": "schema", "判定": "pass", "詳細": None}]
    return rec, errs

def load_state():
    return json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}

def load_seeds(ids=None):
    seeds = []
    src = [("制度リスト_都道府県47.csv", None), ("制度リスト_市区町村.csv", "M"), ("制度リスト_国.csv", "G")]
    # 都道府県CSVは列構成が異なるため個別に読む
    with open(os.path.join(DATA, "制度リスト_都道府県47.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            seeds.append({"id": r["制度ID"], "実施主体レベル": "都道府県",
                          "自治体コード": re.sub(r"[^0-9]", "", r["制度ID"]).zfill(2),
                          "自治体名": r["都道府県"], "制度名": r["制度名"],
                          "受付状況": r["受付状況"], "url": r["公式URL"]})
    for fn in ("制度リスト_市区町村.csv", "制度リスト_国.csv"):
        p = os.path.join(DATA, fn)
        if not os.path.exists(p): continue
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                seeds.append({"id": r["制度ID"], "実施主体レベル": r["実施主体レベル"],
                              "自治体コード": r["自治体コード"], "自治体名": r["自治体名"],
                              "制度名": r["制度名"], "受付状況": r["受付状況"], "url": r["公式URL"]})
    if ids:
        want = set(ids); seeds = [s for s in seeds if s["id"] in want]
    return seeds

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--ids", default="")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--extractor", choices=["rule", "llm"], default="llm",
                    help="llm はAPIキーが無ければ自動でruleにフォールバック")
    ap.add_argument("--no-pdf", action="store_true", help="要綱PDF本文の取得を無効化")
    args = ap.parse_args()

    valid_ids = NZ.load_kiki_ids()
    syn = load_synonyms()
    rule = RuleBasedExtractor(syn)
    extractor = rule
    if args.extractor == "llm":
        llm = LLMExtractor(syn)
        if llm.available():
            extractor = llm
            print(f"抽出器: {llm.name} (model={llm.model})")
        else:
            print(f"抽出器: {rule.name}（LLM未設定のためフォールバック）")
    else:
        print(f"抽出器: {rule.name}")
    state = load_state()

    ids = [x for x in args.ids.split(",") if x] or None
    seeds = load_seeds(ids)
    if not ids:  # 既定は受付中を優先して limit 件
        seeds = [s for s in seeds if s["受付状況"] == "受付中"][:args.limit]

    staging, changed, unchanged, failed = [], 0, 0, 0
    print(f"=== クロール対象 {len(seeds)} 件 ===")
    for s in seeds:
        html, err = fetch(s["url"])
        if html is None:
            failed += 1; print(f"  ✗ {s['id']} {s['自治体名']}: 取得失敗({err})")
            time.sleep(args.delay); continue
        h = hashlib.sha256(html.encode("utf-8", "ignore")).hexdigest()
        prev = state.get(s["url"], {}).get("hash")
        state[s["url"]] = {"hash": h, "last_checked": datetime.date.today().isoformat()}
        if prev == h:
            unchanged += 1; print(f"  ・{s['id']} {s['自治体名']}: 変更なし(スキップ)")
            time.sleep(args.delay); continue
        changed += 1
        text = html_to_text(html)
        pdfs = find_pdf_links(html, s["url"])
        youkou = pick_youkou(pdfs)
        combined = text
        if not args.no_pdf and youkou:
            ptxt = pdf_text(youkou)
            if ptxt:
                combined = text + " 【要綱PDF】 " + re.sub(r"\s+", " ", ptxt)
        # 抽出（LLM選択時も失敗したらルールベースへフォールバック）
        try:
            ext, ev = extractor.extract(combined)
            used = extractor.name
        except Exception as e:
            ext, ev = rule.extract(combined); used = rule.name + f"(fallback:{type(e).__name__})"
        rec, errs = build_candidate(s, ext, ev, html, youkou, len(pdfs), valid_ids, used)
        staging.append(rec)
        flag = "新規" if prev is None else "変更検知"
        print(f"  ◆ {s['id']} {s['自治体名']}: {flag}／確度{rec['確度']}／"
              f"締切{rec['締切'] or '-'}／率{(rec['補助率']['表示'] or '-')}／"
              f"上限{(rec['補助上限']['表示'] or '-')}／機器{len(rec['対象機器タグ'])}／PDF{len(pdfs)}"
              + (f"／検証NG{len(errs)}" if errs else ""))
        time.sleep(args.delay)

    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(staging, open(STAGING, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== サマリ ===")
    print(f"新規/変更: {changed}  変更なし: {unchanged}  取得失敗: {failed}")
    print(f"ステージング出力: {os.path.relpath(STAGING, BASE)}（{len(staging)}件・全てレビュー待ち/保留＝公開DBには未反映）")
    print(f"状態保存: {os.path.relpath(STATE, BASE)}")

if __name__ == "__main__":
    main()
