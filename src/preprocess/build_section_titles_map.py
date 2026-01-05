import argparse
import csv
import re
import unicodedata
from pathlib import Path

def slugify(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "empty"

    # Нормализуем юникод
    s = unicodedata.normalize("NFKC", s)

    # Если это латиница/цифры — делаем slug
    # (русские буквы оставим как есть, но превратим в подчёркивания и т.п.)
    s_low = s.lower()

    # заменяем всё не-буква/цифра на _
    s_low = re.sub(r"[^\w]+", "_", s_low, flags=re.UNICODE)
    s_low = re.sub(r"_+", "_", s_low).strip("_")

    # чтобы id не начинался с цифры
    if s_low and s_low[0].isdigit():
        s_low = "s_" + s_low

    return s_low or "empty"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)

    # utf-8-sig помогает, если файл сохранён из Excel с BOM
    with inp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Пустой CSV или не распознаны заголовки колонок")

        # ожидаем section_title и count
        if "section_title" not in reader.fieldnames:
            raise ValueError(f"Нет колонки 'section_title'. Есть: {reader.fieldnames}")

        rows = []
        used = set()
        for r in reader:
            title = (r.get("section_title") or "").strip()
            cnt = (r.get("count") or "").strip()

            sid_base = slugify(title)

            # гарантируем уникальность id
            sid = sid_base
            i = 2
            while sid in used:
                sid = f"{sid_base}_{i}"
                i += 1
            used.add(sid)

            rows.append({"section_id": sid, "title": title, "count": cnt})

    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["section_id", "title", "count"])
        w.writeheader()
        w.writerows(rows)

    print(f"OK: {out} (rows={len(rows)})")

if __name__ == "__main__":
    main()