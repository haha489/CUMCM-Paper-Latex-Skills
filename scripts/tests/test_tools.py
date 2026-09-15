"""Behavioral checks using deliberately synthetic, isolated paper fixtures."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_paper import inspect, escape_tex
from init_paper import initialize


class PaperChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="paper-skill-test-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "result.csv").write_text("label,value\na,40\nb,60\n", encoding="utf-8")
        self.paper = self.root / "paper"
        initialize(self.paper, self.source)
        (self.paper / "main.tex").write_text(r"\PaperDraftfalse \input{data/results.tex} \section{Example}\label{sec:one} Synthetic fixture: \Result{q01-mean}. See \ref{sec:one}.", encoding="utf-8")
        self.manifest = {"schema_version": 1, "source_root": str(self.source),
            "questions": [{"id": "q01", "requirement": "Mean of two fixture values", "status": "ready", "answer_location": "main.tex", "missing": []}],
            "claims": [{"id": "q01-mean", "question": "q01", "statement": "Synthetic fixture mean", "status": "derived", "display": "50 units", "derivation": "(40+60)/2", "sources": [{"path": "result.csv", "kind": "result", "locator": "column value, rows a and b"}]}]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.paper / "evidence.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def messages(self, **kwargs):
        return "\n".join(inspect(self.paper, **kwargs)[0])

    def add_tex(self, text):
        with (self.paper / "main.tex").open("a", encoding="utf-8") as stream:
            stream.write("\n" + text)

    def test_valid_result_and_shared_display(self):
        self.assertEqual(inspect(self.paper, write_results=True)[0], [])
        self.assertEqual(inspect(self.paper)[0], [])
        self.assertIn(r"\DeclareResult{q01-mean}{50 units}", (self.paper / "data/results.tex").read_text())

    def test_refuses_existing_output(self):
        with self.assertRaises(ValueError):
            initialize(self.paper, self.source)

    def test_missing_source(self):
        (self.source / "result.csv").unlink()
        self.assertIn("Source file missing", self.messages())

    def test_source_escape(self):
        self.manifest["claims"][0]["sources"][0]["path"] = "../elsewhere.csv"
        self.save()
        self.assertIn("escapes declared root", self.messages())

    def test_code_is_not_execution_evidence(self):
        self.manifest["claims"][0]["sources"][0]["kind"] = "code"
        self.save()
        self.assertIn("Code alone", self.messages())

    def test_unresolved_used_claim(self):
        self.manifest["claims"][0]["status"] = "conflict"
        self.save()
        self.assertIn("Unverified or undefined result", self.messages())

    def test_required_question_missing(self):
        self.manifest["questions"][0]["status"] = "partial"
        self.save()
        self.assertIn("Required answer incomplete", self.messages(final=True))

    def test_optional_missing_comparison_does_not_block(self):
        self.manifest["questions"][0]["missing"] = ["Optional model comparison was not performed"]
        self.save()
        self.assertEqual(inspect(self.paper, write_results=True)[0], [])

    def test_missing_figure_and_label(self):
        self.add_tex(r"\includegraphics{absent.png} \ref{not-defined} \label{sec:one}")
        messages = self.messages()
        for term in ("Missing or external figure", "Undefined cross-reference", "Duplicate label"):
            self.assertIn(term, messages)

    def test_comment_is_not_a_missing_figure(self):
        self.add_tex(r"% \includegraphics{absent.png}")
        self.assertEqual(inspect(self.paper, write_results=True)[0], [])

    def test_stale_result(self):
        inspect(self.paper, write_results=True)
        self.manifest["claims"][0]["display"] = "51 units"
        self.save()
        self.assertIn("result values are stale", self.messages())

    def test_missing_citation(self):
        self.add_tex(r"\cite{unknown}")
        self.assertIn("Missing bibliography entry", self.messages())

    def test_final_requires_actual_pdf(self):
        inspect(self.paper, write_results=True)
        self.assertIn("No compiled PDF", self.messages(final=True))

    def test_plain_text_tex_escaping(self):
        self.assertEqual(escape_tex("10% & x_1"), r"10\% \& x\_1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
