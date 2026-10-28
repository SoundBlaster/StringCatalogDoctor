import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from string_catalog_doctor.__main__ import check_catalog, placeholders

TOOL = Path(__file__).resolve().parents[1] / "string_catalog_doctor"


class DoctorTests(unittest.TestCase):
    def test_positional_placeholders(self):
        self.assertEqual(placeholders("%@ %lld"), placeholders("%2$lld %1$@"))
        self.assertNotEqual(placeholders("%@ %lld"), placeholders("%1$lld %2$@"))
        self.assertEqual(placeholders("100%% %@"), [(1, "@")])

    def test_locale_and_exclusion_are_consumer_configured(self):
        doc = {"sourceLanguage": "en", "strings": {
            "Count %lld": {"localizations": {
                "es": {"stringUnit": {"state": "translated", "value": "%@"}}
            }},
            "Brand": {}
        }}
        issues = check_catalog("other.xcstrings", doc, ["es", "ru"], ["Brand"])
        self.assertEqual({(i["locale"], i["kind"]) for i in issues},
                         {("es", "placeholder"), ("ru", "missing")})

    def test_explicit_source_value_and_key_fallback(self):
        def unit(value):
            return {"stringUnit": {"state": "translated", "value": value}}
        doc = {"sourceLanguage": "en", "strings": {
            "greeting": {"localizations": {"en": unit("Hello %@"), "fr": unit("Bonjour %@")}},
            "count %lld": {"localizations": {"fr": unit("Nombre %lld")}},
        }}
        self.assertEqual(check_catalog("app.xcstrings", doc, ["fr"]), [])
        doc["strings"]["greeting"]["localizations"]["fr"] = unit("Bonjour")
        doc["strings"]["count %lld"]["localizations"]["fr"] = unit("Nombre")
        issues = check_catalog("app.xcstrings", doc, ["fr"])
        self.assertEqual({(issue["key"], issue["kind"]) for issue in issues},
                         {("greeting", "placeholder"), ("count %lld", "placeholder")})

    def test_staged_config_and_catalogs(self):
        with tempfile.TemporaryDirectory(prefix="doctor-") as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            def run(*args):
                return subprocess.run([sys.executable, str(TOOL), "--root", str(root), *args],
                                      capture_output=True, text=True)
            git("init", "-q")
            config = {"version": 1, "locales": ["es"], "baseline": "baseline.json",
                      "catalogs": [{"path": "app.xcstrings"}]}
            doc = {"sourceLanguage": "en", "strings": {"Hello": {"localizations": {
                "es": {"stringUnit": {"state": "translated", "value": "Hola"}}
            }}}}
            (root / ".string-catalog-doctor.json").write_text(json.dumps(config))
            (root / "baseline.json").write_text('{"version":1,"issues":[]}')
            (root / "app.xcstrings").write_text(json.dumps(doc))
            git("add", ".")
            doc["strings"]["Hello"]["localizations"].pop("es")
            (root / "app.xcstrings").write_text(json.dumps(doc))
            config["locales"] = ["fr"]
            (root / ".string-catalog-doctor.json").write_text(json.dumps(config))
            self.assertEqual(run("--staged").returncode, 0)
            self.assertEqual(run().returncode, 1)
            git("add", "app.xcstrings")
            result = run("--staged")
            self.assertEqual(result.returncode, 1)
            self.assertIn("es: 'Hello': missing", result.stdout)

    def test_invalid_configuration_fails(self):
        with tempfile.TemporaryDirectory(prefix="doctor-") as temp:
            root = Path(temp)
            (root / ".string-catalog-doctor.json").write_text(json.dumps({
                "version": 1, "catalogs": [{"path": "../outside"}],
                "locales": ["es"], "baseline": "baseline.json"
            }))
            result = subprocess.run([sys.executable, str(TOOL), "--root", str(root)],
                                    capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_malformed_catalog_fails_without_traceback(self):
        with tempfile.TemporaryDirectory(prefix="doctor-") as temp:
            root = Path(temp)
            (root / ".string-catalog-doctor.json").write_text(json.dumps({
                "version": 1, "catalogs": [{"path": "catalog.xcstrings"}],
                "locales": ["es"], "baseline": "baseline.json"
            }))
            (root / "catalog.xcstrings").write_text("[]")
            result = subprocess.run([sys.executable, str(TOOL), "--root", str(root)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
