"""Check evidence records and common literal LaTeX issues; not a semantic proof."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

IDENTIFIER = re.compile(r"[a-zA-Z][a-zA-Z0-9-]*\Z")
SOURCE_KINDS = {"result", "log", "executed_notebook", "figure", "source_document", "code"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        for match in re.finditer("%", line):
            pos = match.start()
            preceding = len(line[:pos]) - len(line[:pos].rstrip("\\"))
            if preceding % 2 == 0:
                line = line[:pos]
                break
        lines.append(line)
    return "\n".join(lines)


def escape_tex(text: str) -> str:
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
                    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, c) for c in text)


def result_text(manifest: dict) -> str:
    lines = ["% Generated from verified/derived evidence. Do not edit by hand."]
    for claim in manifest.get("claims", []):
        if claim.get("status") in {"verified", "derived"}:
            lines.append(r"\DeclareResult{" + claim["id"] + "}{" + escape_tex(claim["display"]) + "}")
    return "\n".join(lines) + "\n"


def inspect(project: Path, final: bool = False, write_results: bool = False):
    project = project.resolve()
    errors, warnings = [], []
    manifest_path = project / "evidence.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return [f"Cannot read evidence.json: {exc}"], [], {}
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["Unsupported or invalid evidence schema"], [], {}
    if not isinstance(manifest.get("questions"), list) or not isinstance(manifest.get("claims"), list):
        return ["questions and claims must be lists"], [], manifest
    root_value = manifest.get("source_root")
    if not isinstance(root_value, str) or not root_value:
        errors.append("source_root must be a non-empty path")
        source_root = project
    else:
        source_root = (project / root_value).resolve()
        if not source_root.is_dir():
            errors.append(f"Missing source root: {source_root}")
    questions, claims = {}, {}
    for question in manifest["questions"]:
        if not isinstance(question, dict):
            errors.append("Question record must be an object")
            continue
        qid = question.get("id", "")
        if not isinstance(qid, str) or not IDENTIFIER.fullmatch(qid) or qid in questions:
            errors.append(f"Invalid or duplicate question id: {qid}")
            continue
        questions[qid] = question
        if question.get("status") not in {"ready", "partial", "missing"}:
            errors.append(f"Invalid question status: {qid}")
        if final:
            if question.get("status") != "ready":
                errors.append(f"Required answer incomplete: {qid}")
            if not question.get("requirement") or not question.get("answer_location"):
                errors.append(f"Missing requirement or answer location: {qid}")
    for claim in manifest["claims"]:
        if not isinstance(claim, dict):
            errors.append("Claim record must be an object")
            continue
        cid = claim.get("id", "")
        if not isinstance(cid, str) or not IDENTIFIER.fullmatch(cid) or cid in claims:
            errors.append(f"Invalid or duplicate claim id: {cid}")
            continue
        claims[cid] = claim
        if claim.get("question") not in questions:
            errors.append(f"Unknown question for claim: {cid}")
        status = claim.get("status")
        if status not in {"verified", "derived", "conflict", "missing"}:
            errors.append(f"Invalid claim status: {cid}")
        if status not in {"verified", "derived"}:
            warnings.append(f"Excluded unresolved claim: {cid}")
            continue
        if not isinstance(claim.get("display"), str) or not claim["display"].strip() or not claim.get("statement"):
            errors.append(f"Missing display or statement: {cid}")
        if status == "derived" and not claim.get("derivation"):
            errors.append(f"Derived claim needs a calculation description: {cid}")
        sources = claim.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"Claim has no source: {cid}")
            continue
        kinds = []
        for source in sources:
            if not isinstance(source, dict):
                errors.append(f"Invalid source object: {cid}")
                continue
            kind = source.get("kind")
            kinds.append(kind)
            if kind not in SOURCE_KINDS or not source.get("locator"):
                errors.append(f"Missing source kind or precise locator: {cid}")
            relative = source.get("path")
            if not isinstance(relative, str) or not relative:
                errors.append(f"Missing source path: {cid}")
                continue
            path = (source_root / relative).resolve()
            if not path.is_relative_to(source_root):
                errors.append(f"Source escapes declared root: {cid}: {relative}")
            elif not path.is_file():
                errors.append(f"Source file missing: {cid}: {relative}")
            elif source.get("sha256") and source["sha256"].lower() != digest(path):
                errors.append(f"Source changed since verification: {cid}: {relative}")
        if kinds and all(k == "code" for k in kinds) and re.search(r"\d", claim.get("display", "")):
            errors.append(f"Code alone does not establish a numerical result: {cid}")
    if final and (not questions or not claims):
        errors.append("Final paper requires question coverage and key evidence records")

    texts = []
    def visit(path: Path, active: set):
        path = path.resolve()
        if not path.is_relative_to(project):
            errors.append(f"TeX input outside deliverable project: {path}")
            return
        if path in active:
            errors.append(f"Cyclic TeX input: {path}")
            return
        if not path.is_file():
            errors.append(f"Missing TeX input: {path}")
            return
        clean = without_comments(path.read_text(encoding="utf-8-sig"))
        texts.append((path, clean))
        for target in re.findall(r"\\(?:input|include)\s*\{([^{}]+)\}", clean):
            if "\\" in target or "#" in target:
                warnings.append(f"Dynamic TeX input needs manual review: {target}")
                continue
            child = project / target
            if not child.suffix:
                child = child.with_suffix(".tex")
            visit(child, active | {path})
    visit(project / "main.tex", set())
    combined = "\n".join(t for _, t in texts)
    body = "\n".join(t for p, t in texts if p.name not in {"preamble.tex", "results.tex"})
    if re.search(r"\\FillIn\s*\{|\bTODO\b|\bTBD\b|待补充|待核实", body):
        (errors if final else warnings).append("Unfinished writing prompts remain")
    if final and r"\PaperDrafttrue" in body:
        errors.append("Draft switch is still enabled")
    labels = re.findall(r"\\label\s*\{([^{}]+)\}", combined)
    for label, count in Counter(labels).items():
        if count > 1:
            errors.append(f"Duplicate label: {label}")
    for label in re.findall(r"\\(?:ref|eqref|autoref|pageref)\s*\{([^{}]+)\}", body):
        if label not in labels:
            errors.append(f"Undefined cross-reference: {label}")
    graphics = [project]
    for block in re.findall(r"\\graphicspath\s*\{((?:\{[^{}]*\})+)\}", combined):
        graphics += [project / x for x in re.findall(r"\{([^{}]*)\}", block)]
    for target in re.findall(r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}", body):
        if "\\" in target or "#" in target:
            warnings.append(f"Dynamic figure path needs manual review: {target}")
            continue
        candidates = [base / target for base in graphics]
        if not Path(target).suffix:
            candidates = [p.with_suffix(ext) for p in candidates for ext in (".pdf", ".png", ".jpg", ".jpeg", ".eps")]
        if not any(p.is_file() and p.resolve().is_relative_to(project) for p in candidates):
            errors.append(f"Missing or external figure: {target}")
    used_results = re.findall(r"\\Result\s*\{([^{}]+)\}", body)
    for cid in used_results:
        if cid not in claims or claims[cid].get("status") not in {"verified", "derived"}:
            errors.append(f"Unverified or undefined result used in paper: {cid}")
    citations = []
    for group in re.findall(r"\\cite[a-zA-Z*]*(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]+)\}", body):
        citations += [key.strip() for key in group.split(",")]
    bib = "\n".join(p.read_text(encoding="utf-8-sig") for p in project.rglob("*.bib") if "build" not in p.relative_to(project).parts)
    bibkeys = re.findall(r"@(?!(?:comment|string|preamble)\b)\w+\s*\{\s*([^,\s]+)", bib, re.I)
    for key in citations:
        if key not in bibkeys:
            errors.append(f"Missing bibliography entry: {key}")
    for key, count in Counter(bibkeys).items():
        if count > 1:
            errors.append(f"Duplicate bibliography key: {key}")
    if not errors:
        generated = result_text(manifest)
        result_path = project / "data" / "results.tex"
        if write_results:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(generated, encoding="utf-8")
        elif used_results and (not result_path.is_file() or result_path.read_text(encoding="utf-8") != generated):
            errors.append("Generated result values are stale; run --write-results")
    if final:
        pdf = project / "build" / "main.pdf"
        record = project / "build" / "build-record.json"
        if not pdf.is_file() or pdf.stat().st_size == 0:
            errors.append("No compiled PDF at build/main.pdf")
        if not record.is_file():
            errors.append("No build record; compile with build_paper.py or document an equivalent manual check")
        else:
            try:
                build = json.loads(record.read_text(encoding="utf-8"))
                for rel, hash_value in build["inputs"].items():
                    path = (project / rel).resolve()
                    if not path.is_relative_to(project) or not path.is_file() or digest(path) != hash_value:
                        errors.append(f"Source changed after compilation: {rel}")
                if not pdf.is_file() or digest(pdf) != build.get("pdf_sha256"):
                    errors.append("PDF does not match successful build record")
            except (ValueError, KeyError, TypeError, OSError) as exc:
                errors.append(f"Invalid build record: {exc}")
        logpath = project / "build" / "main.log"
        if logpath.is_file():
            log = logpath.read_text(encoding="utf-8", errors="replace")
            patterns = [r"Missing character:", r"(?:Reference|Citation).*undefined", r"multiply defined", r"Overfull \\[hv]box"]
            for pattern in patterns:
                if re.search(pattern, log):
                    errors.append(f"Review compiler diagnostic: {pattern}")
    return errors, warnings, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--write-results", action="store_true")
    args = parser.parse_args()
    errors, warnings, _ = inspect(args.project, args.final, args.write_results)
    for error in errors:
        print("ERROR: " + error)
    for warning in warnings:
        print("REVIEW: " + warning)
    print(f"Static check: {len(errors)} error(s), {len(warnings)} review item(s). Semantic and visual review still required.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
