from __future__ import annotations

from docx import Document
from pathlib import Path
import json
import re
import argparse


def clean_text(text: str) -> str:
    text = re.sub(r'Page\s+\d+\s+of\s+\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\n(?=[a-zа-я])', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


SECTION_PATTERN = re.compile(
    r'\n(?=(?:ARTICLE\s+\d+[\.\s-]+)?[A-Z][A-Z\s]{3,})'
)


def split_into_sections(text: str):
    blocks = SECTION_PATTERN.split(text)
    sections = []

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        if body:
            sections.append({"section": title, "text": body})

    if not sections and text.strip():
        sections = [{"section": "FULL_TEXT", "text": text.strip()}]

    return sections


def extract_docx_text(docx_path: Path) -> str:
    doc = Document(docx_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def process_folder(input_dir: Path, output_dir: Path, recursive: bool = True) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = "**/*.docx" if recursive else "*.docx"
    files = list(input_dir.glob(pattern))

    count = 0
    for docx_file in files:
        raw_text = extract_docx_text(docx_file)
        clean = clean_text(raw_text)
        sections = split_into_sections(clean)

        result = {
            "file": docx_file.name,
            "relative_path": str(docx_file.relative_to(input_dir)),
            "sections": sections,
        }

        out_path = output_dir / f"{docx_file.stem}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Clean and segment DOCX contracts into JSON.")
    parser.add_argument("--input", required=True, help="Input folder with .docx files")
    parser.add_argument("--output", required=True, help="Output folder for .json files")
    parser.add_argument("--no-recursive", action="store_true", help="Do not scan subfolders")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        raise SystemExit(f"Input folder not found: {input_dir}")

    processed = process_folder(input_dir, output_dir, recursive=not args.no_recursive)
    print(f"Done ✅ Processed {processed} file(s). Output: {output_dir}")


if __name__ == "__main__":
    main()
