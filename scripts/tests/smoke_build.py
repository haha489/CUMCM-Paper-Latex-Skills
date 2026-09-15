"""Optional real-TeX integration test. All data and bibliography are synthetic fixtures."""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from init_paper import initialize
from check_paper import inspect, digest
from build_paper import build


def png_fixture(path):
    def chunk(name, payload):
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload) & 0xffffffff)
    width, height = 320, 160
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            bar = (50 < x < 110 and y > 75) or (200 < x < 260 and y > 35)
            rows.extend((49, 97, 143) if bar else (255, 255, 255))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = output / "source"
    source.mkdir()
    (source / "result.csv").write_text("label,value\na,40\nb,60\n", encoding="utf-8")
    paper = output / "paper"
    initialize(paper, source)
    manifest = {"schema_version": 1, "source_root": str(source),
        "questions": [{"id": "q01", "requirement": "Synthetic mean for software test", "status": "ready", "answer_location": "main.tex"}],
        "claims": [{"id": "q01-mean", "question": "q01", "statement": "Synthetic mean", "status": "derived", "display": "50 单位", "derivation": "(40+60)/2", "sources": [{"path": "result.csv", "locator": "value column, a and b", "kind": "result", "sha256": digest(source / "result.csv")}]}]}
    (paper / "evidence.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (paper / "main.tex").write_text(r"""\documentclass[UTF8,a4paper,zihao=-4,fontset=none]{ctexart}
\input{preamble.tex}
\PaperDraftfalse
\input{data/results.tex}
\begin{document}
\begin{center}{\heiti\zihao{3}LaTeX 编译与核查测试}\end{center}
本文件仅用合成数据检查软件功能，不是参赛论文。两个测试输入的平均值为\Result{q01-mean}。
\section{公式、统一结果与交叉引用}
\label{sec:test}
式\eqref{eq:mean}给出测试计算，数值再次引用为\Result{q01-mean}。
\begin{equation}\bar{x}=\frac{40+60}{2}=50.\label{eq:mean}\end{equation}
\begin{table}[htbp]\centering\caption{软件测试输入与计算值}\label{tab:test}
\begin{tabular}{lr}\toprule 项目 & 数值 \\\midrule 输入一 & 40 \\ 输入二 & 60 \\ 平均值 & 50 \\\bottomrule\end{tabular}\end{table}
表\ref{tab:test}和图\ref{fig:test}用于检验表题、图题、引用和浮动排版。
\begin{figure}[htbp]\centering\includegraphics[width=.5\linewidth]{fixture.png}\caption{合成图形，仅用于插图构建测试}\label{fig:test}\end{figure}
\section{文献构建测试}
文献条目\cite{syntheticfixture}是明确标记的虚构软件夹具，用于验证 BibTeX 调用与编号；不得用于真实论文。
\bibliographystyle{unsrt}\bibliography{references}
\end{document}
""", encoding="utf-8")
    (paper / "references.bib").write_text('@misc{syntheticfixture, author={Software Test Fixture}, title={Synthetic bibliography entry for compiler testing only}, year={2000}}\n', encoding="utf-8")
    png_fixture(paper / "figures" / "fixture.png")
    errors, _, _ = inspect(paper, write_results=True)
    assert not errors, errors
    build(paper, "xelatex")
    errors, _, _ = inspect(paper, final=True)
    assert not errors, errors
    original = (paper / "main.tex").read_text(encoding="utf-8")
    (paper / "main.tex").write_text(original + "\n% Changed after compilation\n", encoding="utf-8")
    errors, _, _ = inspect(paper, final=True)
    assert any("Source changed after compilation" in error for error in errors), errors
    (paper / "main.tex").write_text(original, encoding="utf-8")
    print("PASS: real XeLaTeX, BibTeX, figures, equations, shared results, final check, and stale-source detection.")


if __name__ == "__main__":
    main()
