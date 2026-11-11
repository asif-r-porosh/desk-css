"""Keeps DESK.md and check.py honest. Standard library only.

  python3 -m unittest discover -s tests/guide -v      # from the repository root

Checks:
  - dist/DESK.md and dist/check.py are the same as their sources in src/ (run tools/build.py).
  - Every class DESK.md names exists in the CSS, and every class in the CSS is named in DESK.md.
  - Every html example in DESK.md passes check.py with no errors.
  - docs.html and every template pass check.py with no errors and no warnings.
  - check.py reports the mistakes an agent is likely to make, on a deliberately broken page.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "dist"))
sys.dont_write_bytecode = True
import check  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def run_check(*paths):
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "dist", "check.py"), *paths],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


GUIDE = read("src", "DESK.md")
CSS_CLASSES = check.css_classes(read("dist", "desk.css"))
ICON_CLASSES = check.css_classes(read("dist", "desk.icons.css"))
SKELETON = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Example</title>
<link rel="stylesheet" href="desk.min.css"><link rel="stylesheet" href="desk.icons.min.css"></head>
<body><main>
%s
</main></body></html>
"""


def listed_classes():
    """The classes in the 'Complete class list' section: lines like  - Label: `a b c`."""
    section = GUIDE.split("## Complete class list", 1)[1].split("\n## ", 1)[0]
    found = set()
    for line in section.splitlines():
        match = re.match(r"^- [^`:]+: `([^`]+)`$", line)
        if match:
            found |= set(match.group(1).split())
    return found


class Sync(unittest.TestCase):
    def test_dist_copies_match_sources(self):
        for name in ("DESK.md", "check.py"):
            self.assertEqual(read("src", name), read("dist", name),
                             "dist/%s differs from src/%s: run python3 tools/build.py" % (name, name))


class Guide(unittest.TestCase):
    def test_every_class_in_the_guide_exists(self):
        known = CSS_CLASSES | ICON_CLASSES
        used = set()
        for block in re.findall(r"```html\n(.*?)```", GUIDE, flags=re.S):
            for value in re.findall(r'class="([^"]*)"', block):
                used |= set(value.split())
        for code in re.findall(r"`\.([a-z][\w-]*)`", GUIDE):
            used.add(code)
        used |= listed_classes()
        self.assertEqual(sorted(used - known), [])

    def test_every_class_in_the_css_is_in_the_guide(self):
        self.assertEqual(sorted((CSS_CLASSES | ICON_CLASSES) - listed_classes()), [])

    def test_examples_pass_the_checker(self):
        blocks = re.findall(r"```html\n(.*?)```", GUIDE, flags=re.S)
        self.assertGreater(len(blocks), 10)
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("desk.min.css", "desk.icons.min.css", "icons.json"):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write(read("dist", name))
            for number, block in enumerate(blocks, 1):
                if block.lstrip().startswith("<!doctype"):
                    page = block
                else:
                    page = SKELETON % block
                path = os.path.join(tmp, "example%d.html" % number)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(page)
                code, out = run_check(path)
                self.assertEqual(code, 0, "example %d in DESK.md:\n%s\n%s" % (number, block, out))

    def test_icon_codes_in_the_guide_exist(self):
        codes = check.load_icons(os.path.join(ROOT, "dist", "desk.css"))
        for code in re.findall(r"&#x([0-9A-Fa-f]+);", GUIDE):
            if len(code) == 5:
                self.assertIn(code.upper(), codes)

    def test_guide_names_no_model(self):
        for word in ("claude", "anthropic", "gpt", "gemini", "sonnet", "opus", "glm"):
            self.assertNotRegex(GUIDE.lower(), r"\b%s\b" % word)


class Pages(unittest.TestCase):
    def test_docs_and_templates_are_clean(self):
        pages = [os.path.join(ROOT, "docs.html")]
        folder = os.path.join(ROOT, "templates")
        pages += sorted(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".html"))
        code, out = run_check("--strict", *pages)
        self.assertEqual(code, 0, out)


class Catches(unittest.TestCase):
    BAD = """<html data-theme="midnight">
<head><title>x</title><link rel="stylesheet" href="%s"></head>
<body><div class="container-fluid"><button class="btn-primary">Save</button>
<span class="mdi mdi-home"></span><span>&#xF9999;</span><img src="a.png">
<button commandfor="nope" command="show-modal">Open</button></div></body></html>"""

    def test_bad_page_reports_each_mistake(self):
        css = os.path.join(ROOT, "dist", "desk.min.css")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.BAD % css)
            code, out = run_check(path)
        self.assertEqual(code, 1)
        for expected in ("[doctype]", "[lang]", "[viewport]", "[setting-value]", "[unknown-class] class 'container-fluid'",
                         "did you mean class=\"btn primary\"", "[unknown-class] class 'mdi'", "[icon-code] U+F9999",
                         "[icons-css]", "[img-alt]", "[target-missing]"):
            self.assertIn(expected, out)


if __name__ == "__main__":
    unittest.main()
