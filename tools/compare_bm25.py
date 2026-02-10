import argparse, json, math, re
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9]+", re.UNICODE)

def tokenize(text: str):
    return [t.lower() for t in TOKEN_RE.findall(text or "")]

class BM25:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.docs = docs_tokens
        self.N = len(docs_tokens)
        self.doc_len = [len(d) for d in docs_tokens]
        self.avgdl = sum(self.doc_len) / self.N if self.N else 0.0

        # df
        df = {}
        for d in docs_tokens:
            seen = set(d)
            for t in seen:
                df[t] = df.get(t, 0) + 1
        self.df = df

        # idf (BM25+ safe-ish)
        self.idf = {}
        for t, n in df.items():
            self.idf[t] = math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def score(self, query_tokens):
        q = query_tokens
        scores = [0.0] * self.N
        for i, doc in enumerate(self.docs):
            dl = self.doc_len[i]
            if dl == 0:
                continue
            tf = {}
            for t in doc:
                tf[t] = tf.get(t, 0) + 1
            denom_const = self.k1 * (1 - self.b + self.b * dl / (self.avgdl + 1e-9))
            s = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = self.idf.get(t, 0.0)
                f = tf[t]
                s += idf * (f * (self.k1 + 1)) / (f + denom_const)
            scores[i] = s
        return scores

def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def build(rows, use_fields=("title","text")):
    docs_tokens = []
    for r in rows:
        parts = []
        for k in use_fields:
            parts.append(r.get(k, "") or "")
        docs_tokens.append(tokenize("\n".join(parts)))
    return BM25(docs_tokens)

def format_hit(r, score, max_chars=220):
    title = (r.get("title") or "").strip()
    doc_id = r.get("doc_id") or ""
    sid = r.get("section_id") or ""
    sgrp = r.get("section_group") or ""
    lang = r.get("language") or ""
    text = (r.get("text") or "").replace("\n", " ").strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return f"{score:8.4f} | {lang:2} | {sgrp:10} | {sid:16} | {title}  ||  {doc_id}\n    {text}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--section_id", default="", help="optional: filter to this section_id")
    ap.add_argument("--lang", default="", help="optional: filter by language, e.g. en or ru")
    args = ap.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)

    old_rows = load_jsonl(old_path)
    new_rows = load_jsonl(new_path)

    def apply_filters(rows):
        out = []
        for r in rows:
            if args.section_id and (r.get("section_id") or "") != args.section_id:
                continue
            if args.lang and (r.get("language") or "") != args.lang:
                continue
            out.append(r)
        return out

    old_rows_f = apply_filters(old_rows)
    new_rows_f = apply_filters(new_rows)

    q = tokenize(args.query)

    old_bm = build(old_rows_f)
    new_bm = build(new_rows_f)

    old_scores = old_bm.score(q)
    new_scores = new_bm.score(q)

    def topk(rows, scores, k):
        idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(rows[i], scores[i]) for i in idx]

    print("="*120)
    print(f"QUERY: {args.query}")
    if args.section_id:
        print(f"FILTER section_id={args.section_id}")
    if args.lang:
        print(f"FILTER language={args.lang}")
    print("="*120)

    print(f"\nOLD CORPUS: {old_path}   (rows used: {len(old_rows_f)} / {len(old_rows)})")
    print("-"*120)
    for r, s in topk(old_rows_f, old_scores, args.k):
        print(format_hit(r, s))
        print()

    print(f"\nNEW CORPUS: {new_path}   (rows used: {len(new_rows_f)} / {len(new_rows)})")
    print("-"*120)
    for r, s in topk(new_rows_f, new_scores, args.k):
        print(format_hit(r, s))
        print()

if __name__ == "__main__":
    main()

