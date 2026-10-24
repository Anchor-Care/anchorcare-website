"""Exercise validation against real temporary page and asset files."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("validate_site", Path(__file__).with_name("validate-site.py"))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class SiteValidationTests(unittest.TestCase):
    def test_pages_and_assets(self):
        # Test-owned files only; no production content or services are touched.
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            page = root / "index.html"
            asset = root / "logo.png"
            asset.write_bytes(b"synthetic asset")
            page.write_text('<html lang="en"><title>Test</title><h1>Test</h1>'
                            '<img src="logo.png"><a href="https://example.com">External</a>'
                            '<script>const value = 1;</script></html>')
            self.assertEqual(validator.validate(root, [page]), [])
            asset.unlink()
            self.assertIn("missing local file: logo.png", "\n".join(validator.validate(root, [page])))

    def test_invalid_javascript_and_missing_metadata_fail(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            page = root / "index.html"
            page.write_text('<html><script>const = ;</script></html>')
            errors = "\n".join(validator.validate(root, [page]))
            for expected in ("missing title", "missing h1", "missing html lang", "inline script 1 is invalid"):
                self.assertIn(expected, errors)

    def test_directory_links_and_root_escape(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            (root / "guide").mkdir()
            (root / "guide/index.html").write_text("synthetic page")
            page = root / "index.html"
            page.write_text('<html lang="en"><title>Test</title><h1>Test</h1>'
                            '<a href="/guide/">Guide</a><a href="#top">Top</a></html>')
            self.assertEqual(validator.validate(root, [page]), [])
            page.write_text(page.read_text() + '<a href="../outside.html">Outside</a>')
            self.assertIn("escapes site root", "\n".join(validator.validate(root, [page])))


if __name__ == "__main__":
    unittest.main()
