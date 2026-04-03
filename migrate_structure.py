from pathlib import Path
import shutil
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parent

NEW_DIRS = [
    "automation_flow/core/config",
    "automation_flow/core/prompts",
    "automation_flow/core/media",
    "automation_flow/core/video",
    "automation_flow/core/image",
    "automation_flow/core/llm",
    "automation_flow/core/publishers",
    "automation_flow/core/utils",
    "automation_flow/flows/content",
    "automation_flow/flows/sales",
    "automation_flow/cli",
]

MIGRATIONS = [
    ("main.py", "automation_flow/cli/main.py"),
    ("historico_roteiros.json", "automation_flow/core/config/historico_roteiros.json"),
    ("ffmpeg.exe", "automation_flow/core/media/ffmpeg.exe"),
    ("chromedriver.exe", "automation_flow/core/media/chromedriver.exe"),
    ("requirements.txt", "requirements.txt"),
]

FOLDER_HINTS = {
    "prompts": "automation_flow/core/prompts",
    "utils": "automation_flow/core/utils",
    "image": "automation_flow/core/image",
    "images": "automation_flow/core/image",
    "video": "automation_flow/core/video",
    "media": "automation_flow/core/media",
    "publisher": "automation_flow/core/publishers",
    "publishers": "automation_flow/core/publishers",
    "config": "automation_flow/core/config",
    "configs": "automation_flow/core/config",
}

CONTENT_KEYWORDS = [
    "motivation", "motivacional", "cartomante", "content", "conteudo", "roteiro"
]

SALES_KEYWORDS = [
    "sales", "venda", "produto", "product", "offer", "anuncio", "advert"
]

report = {
    "created_dirs": [],
    "moved": [],
    "skipped": [],
    "manual_review": [],
    "timestamp": datetime.now().isoformat(),
}

def ensure_dirs():
    for d in NEW_DIRS:
        path = ROOT / d
        path.mkdir(parents=True, exist_ok=True)
        report["created_dirs"].append(str(path.relative_to(ROOT)))

def safe_move(src: Path, dst: Path):
    if not src.exists():
        report["skipped"].append(f"origem inexistente: {src.relative_to(ROOT)}")
        return

    if src.resolve() == dst.resolve():
        report["skipped"].append(f"origem e destino iguais: {src.relative_to(ROOT)}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        report["skipped"].append(
            f"destino já existe: {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}"
        )
        return

    shutil.move(str(src), str(dst))
    report["moved"].append(f"{src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")

def create_init_files():
    pkgs = [
        "automation_flow",
        "automation_flow/core",
        "automation_flow/core/config",
        "automation_flow/core/prompts",
        "automation_flow/core/media",
        "automation_flow/core/video",
        "automation_flow/core/image",
        "automation_flow/core/llm",
        "automation_flow/core/publishers",
        "automation_flow/core/utils",
        "automation_flow/flows",
        "automation_flow/flows/content",
        "automation_flow/flows/sales",
        "automation_flow/cli",
    ]
    for pkg in pkgs:
        init_file = ROOT / pkg / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

def classify_python_file(path: Path):
    name = path.stem.lower()

    if any(k in name for k in SALES_KEYWORDS):
        return ROOT / "automation_flow/flows/sales" / path.name

    if any(k in name for k in CONTENT_KEYWORDS):
        return ROOT / "automation_flow/flows/content" / path.name

    for key, target in FOLDER_HINTS.items():
        if key in name:
            return ROOT / target / path.name

    return None

def migrate_known_files():
    for src_rel, dst_rel in MIGRATIONS:
        src = ROOT / src_rel
        dst = ROOT / dst_rel
        if src.exists():
            safe_move(src, dst)

def migrate_top_level_python_files():
    for py_file in ROOT.glob("*.py"):
        if py_file.name == Path(__file__).name:
            continue

        target = classify_python_file(py_file)
        if target:
            safe_move(py_file, target)
        else:
            report["manual_review"].append(
                f"Revisar arquivo Python sem destino automático: {py_file.relative_to(ROOT)}"
            )

def migrate_top_level_dirs():
    ignore = {
        ".git", ".github", ".venv", "venv", "__pycache__", "automation_flow"
    }

    for item in ROOT.iterdir():
        if not item.is_dir():
            continue
        if item.name in ignore:
            continue

        lowered = item.name.lower()

        matched = False
        for key, target in FOLDER_HINTS.items():
            if key in lowered:
                safe_move(item, ROOT / target / item.name)
                matched = True
                break

        if matched:
            continue

        if any(k in lowered for k in SALES_KEYWORDS):
            safe_move(item, ROOT / "automation_flow/flows/sales" / item.name)
        elif any(k in lowered for k in CONTENT_KEYWORDS):
            safe_move(item, ROOT / "automation_flow/flows/content" / item.name)
        else:
            report["manual_review"].append(
                f"Revisar pasta sem destino automático: {item.relative_to(ROOT)}"
            )

def write_report():
    report_path = ROOT / "migration_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def main():
    ensure_dirs()
    create_init_files()
    migrate_known_files()
    migrate_top_level_python_files()
    migrate_top_level_dirs()
    write_report()
    print("Migração concluída. Revise o arquivo migration_report.json antes do commit.")

if __name__ == "__main__":
    main()