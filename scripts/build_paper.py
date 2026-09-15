"""Compile a LaTeX project in a fresh directory; preserve logs and reject stale PDFs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(project: Path, engine: str, timeout: int = 180) -> Path:
    project = project.resolve()
    if not (project / "main.tex").is_file():
        raise ValueError(f"Missing main.tex in {project}")
    binary = shutil.which(engine)
    if binary is None:
        raise ValueError(f"XeLaTeX executable not found: {engine}")
    # Preserve failed logs; only a successful build replaces build/main.pdf.
    work = Path(tempfile.mkdtemp(prefix=".latex-build-", dir=project))
    out = project / "build"
    env = os.environ.copy()
    env["TEXINPUTS"] = str(work) + os.pathsep + str(project) + os.pathsep + env.get("TEXINPUTS", "")
    env["BIBINPUTS"] = str(project) + os.pathsep + env.get("BIBINPUTS", "")
    commands = []
    def run(command, name, cwd=project):
        commands.append(command)
        with (work / name).open("wb") as log:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        if result.returncode:
            raise RuntimeError(f"Compiler failed ({result.returncode}); inspect {work / name}. Previous PDF, if present, is unchanged.")
    args = [binary, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
            "-recorder", f"-output-directory={work}", "main.tex"]
    run(args, "pass1.txt")
    aux = work / "main.aux"
    auxtext = aux.read_text(encoding="utf-8", errors="replace") if aux.is_file() else ""
    if r"\citation{" in auxtext:
        bibtex = shutil.which("bibtex")
        if bibtex is None:
            candidate = Path(binary).with_name("bibtex.exe" if os.name == "nt" else "bibtex")
            bibtex = str(candidate) if candidate.is_file() else None
        if bibtex is None:
            raise RuntimeError(f"Citations found but BibTeX unavailable. Logs: {work}")
        run([bibtex, "main"], "bibtex.txt", cwd=work)
    run(args, "pass2.txt")
    run(args, "pass3.txt")
    pdf = work / "main.pdf"
    if not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-"):
        raise RuntimeError(f"Compiler returned without a valid PDF. Logs: {work}")
    inputs = {}
    for entry in (work / "main.fls").read_text(encoding="utf-8", errors="replace").splitlines():
        if entry.startswith("INPUT "):
            path = (project / entry[6:].strip('"')).resolve()
            if path.is_file() and path.is_relative_to(project) and not path.is_relative_to(work) and not path.is_relative_to(out):
                inputs[path.relative_to(project).as_posix()] = sha256(path)
    # BibTeX reads separately; retain these too for freshness checks.
    for path in project.glob("*.bib"):
        inputs[path.name] = sha256(path)
    out.mkdir(exist_ok=True)
    for path in work.iterdir():
        if path.is_file():
            shutil.copy2(path, out / path.name)
    record = {"built_at_utc": datetime.now(timezone.utc).isoformat(), "commands": commands,
              "inputs": inputs, "pdf_sha256": sha256(out / "main.pdf")}
    (out / "build-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # The path is created by mkdtemp inside this exact project and checked again.
    if work.parent == project and work.name.startswith(".latex-build-"):
        shutil.rmtree(work)
    return out / "main.pdf"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--engine", default="xelatex")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    try:
        pdf = build(args.project, args.engine, args.timeout)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"Compiled: {pdf}")
    print("Inspect main.log and render every page before delivery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
