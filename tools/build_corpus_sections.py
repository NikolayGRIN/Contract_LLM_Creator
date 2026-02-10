import json
from pathlib import Path

SRC = Path("data/segmented_contracts.jsonl")
DST = Path("data/corpus_sections.jsonl")

# минимальный маппинг section_id → section_group
SECTION_GROUP_MAP = {
    # commercial
    "payment_terms": "commercial",
    "price": "commercial",
    "prices": "commercial",
    "settlement": "commercial",
    "delivery_terms": "commercial",
    "delivery": "commercial",

    # liability
    "liability": "liability",
    "penalties": "liability",

    # disputes
    "disputes": "disputes",
    "governing_law": "disputes",
}

def infer_section_group(section_id: str) -> str:
    sid = (section_id or "").lower()
    for key, group in SECTION_GROUP_MAP.items():
        if key in sid:
            return group
    return "other"


def infer_language(text: str) -> str:
    # грубо, но достаточно для MVP
    for ch in text:
        if "a" <= ch.lower() <= "z":
            return "en"
    return "ru"


with SRC.open(encoding="utf-8") as src, DST.open("w", encoding="utf-8") as out:
    for line_no, line in enumerate(src, start=1):
        line = line.strip()
        if not line:
            continue

        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            print(f"Skip invalid JSON at line {line_no}")
            continue

        doc_id = str(doc.get("contract_id", f"doc_{line_no}"))
        sections = doc.get("sections", [])

        if not isinstance(sections, list):
            continue

        for sec in sections:
            text = (sec.get("text") or "").strip()
            if len(text) < 80:
                continue  # отсекаем мусор

            section_id = (sec.get("section_id") or "").strip()
            section_group = infer_section_group(section_id)
            language = infer_language(text)

            record = {
                "doc_id": doc_id,
                "section_group": section_group,
                "section_id": section_id,
                "language": language,
                "text": text
            }

            out.write(json.dumps(record, ensure_ascii=False) + "\n")

print("DONE: corpus_sections.jsonl created")
