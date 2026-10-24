#!/usr/bin/env python3
"""Offline checks for the static site. No network access or build dependencies."""

from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = []
        self.scripts = []
        self.script = None
        self.title = False
        self.heading = False
        self.language = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.title |= tag == "title"
        self.heading |= tag == "h1"
        self.language |= tag == "html" and bool(attrs.get("lang"))
        for attr in ("href", "src"):
            if attrs.get(attr):
                self.references.append(attrs[attr])
        if tag == "script" and not attrs.get("src") and attrs.get("type", "").lower() in (
            "", "text/javascript", "application/javascript", "module"
        ):
            self.script = []

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None


def validate(root, pages):
    errors = []
    for path in pages:
        label = path.relative_to(root)
        page = Page()
        page.feed(path.read_text(encoding="utf-8"))
        for present, name in ((page.title, "title"), (page.heading, "h1"), (page.language, "html lang")):
            if not present:
                errors.append(f"{label}: missing {name}")
        for reference in page.references:
            url = urlsplit(reference)
            # External links, mail, telephone and same-page fragments are not fetched.
            if url.scheme or url.netloc or not url.path:
                continue
            target = (root / unquote(url.path).lstrip("/") if url.path.startswith("/")
                      else path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root):
                errors.append(f"{label}: reference escapes site root: {reference}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{label}: missing local file: {reference}")
        for index, script in enumerate(page.scripts, 1):
            result = subprocess.run(
                ["node", "--check", "--input-type=module"], input=script,
                text=True, capture_output=True, check=False,
            )
            if result.returncode:
                errors.append(f"{label}: inline script {index} is invalid:\n{result.stderr}")
    return errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    files = subprocess.check_output(["git", "ls-files", "-z", "*.html"], cwd=root).decode().split("\0")
    pages = [root / name for name in files if name]
    if not pages:
        sys.exit("No tracked HTML pages found")
    errors = validate(root, pages)
    if errors:
        sys.exit("\n".join(errors))
    print(f"Validated {len(pages)} pages: page metadata, local links/assets and inline JavaScript")
