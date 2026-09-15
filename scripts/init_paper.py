"""Copy a clean LaTeX starter without overwriting an existing project."""
import argparse
import json
from pathlib import Path
import shutil


def initialize(output: Path, source_root: Path) -> None:
    output = output.resolve()
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise ValueError(f"Source root is not a directory: {source_root}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"Refusing to overwrite non-empty output: {output}")
    assets = Path(__file__).resolve().parents[1] / "assets"
    template = assets / "latex"
    shutil.copytree(template, output, dirs_exist_ok=True)
    shutil.copy2(assets / "review" / "论文完善建议.md", output / "论文完善建议.md")
    (output / "figures").mkdir(exist_ok=True)
    manifest = {"schema_version": 1, "source_root": str(source_root), "questions": [], "claims": []}
    (output / "evidence.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "写作核查.md").write_text(
        "# 写作核查\n\n## 任务与成果版本\n\n## 逐问答案与证据\n\n"
        "## 问题追踪\n\n面向作者的缺口分析与图表建议统一见 [论文完善建议.md](论文完善建议.md)；"
        "此处仅记录对应条目编号、来源核查与处理状态。\n\n## 本次新增核算或分析\n\n"
        "## 内容、格式与最终 PDF 核查\n\n"
        "状态：已初始化，尚未填写论文，尚未完成研究证据或版式核查。\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        initialize(args.output, args.source_root)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"Created LaTeX starter: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
