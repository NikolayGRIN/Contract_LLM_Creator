from pathlib import Path
import zipfile

# Корень проекта
ROOT = Path(__file__).parent.resolve()

# Выходной архив
OUT = ROOT / "colab_bundle.zip"

# ЧТО ВКЛЮЧАЕМ В УНИВЕРСАЛЬНЫЙ BUNDLE
INCLUDE = [
    "run_generate.py",
    "src",                         # весь код генерации
    "data/corpus_sections.jsonl",  # корпус для ВСЕХ секций

    # валидатор
    "src/validation/payment_terms_validator.py",
    "src/validation/__init__.py",
]

# Откуда берём form_input.json
FORM_INPUT_SRC = ROOT / "form_input.json"

# ЧТО ИСКЛЮЧАЕМ ЯВНО
EXCLUDE_DIRS = {
    "contracts_docx",
    "contracts_docx_healed",
    "contracts_json",
    "__pycache__",
}

def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)

def add_file(zf: zipfile.ZipFile, p: Path, arcname: str | None = None):
    if arcname is None:
        arcname = p.relative_to(ROOT).as_posix()
    zf.write(p, arcname=arcname)

def add_dir(zf: zipfile.ZipFile, d: Path):
    for p in d.rglob("*"):
        if not p.is_file():
            continue
        if should_exclude(p):
            continue
        add_file(zf, p)

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    # основной код
    for item in INCLUDE:
        p = ROOT / item
        if not p.exists():
            raise FileNotFoundError(f"Missing required path: {p}")

        if p.is_dir():
            add_dir(zf, p)
        else:
            add_file(zf, p)

    # ✅ form_input.json → В КОРЕНЬ АРХИВА
    if not FORM_INPUT_SRC.exists():
        raise FileNotFoundError(f"Missing form_input.json: {FORM_INPUT_SRC}")

    add_file(zf, FORM_INPUT_SRC, arcname="form_input.json")

print(" Colab bundle created:")
print(" ", OUT)
print()
print("Included:")
for i in INCLUDE:
    print(" -", i)
print()
print("Excluded dirs:")
for e in sorted(EXCLUDE_DIRS):
    print(" -", e)
