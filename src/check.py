#!/usr/bin/env python3
"""Check HTML pages against desk.css. Python 3.8+, standard library only.

  python3 check.py page.html [more.html ...]
  python3 check.py --strict page.html      # warnings fail too
  python3 check.py --icon home             # look up icon codes by name or group

Prints one line per finding:  file:line: ERROR [code] message
Exit code 1 when there is any ERROR (or any WARN with --strict), else 0.

What it knows comes from the files next to the page's stylesheet link (or next to this
script): desk.css or desk.min.css for the class names and data-* values, icons.json for
the icon codes. Classes defined in the page's own <style> blocks and in other local
stylesheets are accepted too.
"""
import difflib
import json
import os
import re
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}
COMMANDS = {"show-modal", "close", "request-close", "toggle-popover", "show-popover",
            "hide-popover"}
SETTINGS = ("data-theme", "data-density", "data-accent")
FIELD_SKIP = {"hidden", "submit", "button", "reset", "image"}


# ---------- reading CSS ----------

def strip_css(css):
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    css = re.sub(r"url\([^)]*\)", " ", css)
    css = re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', " ", css)
    css = re.sub(r"@layer\s+[\w.,\s-]+?(?=[{;])", " ", css)
    css = re.sub(r"@import[^;]*;", " ", css)
    return css


def css_classes(css):
    return set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", strip_css(css)))


def css_settings(css):
    """data-theme / data-density / data-accent values named in attribute selectors."""
    found = {name: set() for name in SETTINGS}
    for name, value in re.findall(r"\[(data-(?:theme|density|accent))=[\"']?([\w-]+)[\"']?\]", css):
        found[name].add(value)
    return found


# ---------- reading HTML ----------

class Node:
    def __init__(self, tag, attrs, line, parent):
        self.tag = tag
        self.attrs = attrs
        self.line = line
        self.parent = parent
        self.children = []
        self.text = []          # (line, text) chunks directly inside

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def has_class(self, name):
        return name in self.classes()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def all_text(self):
        parts = [t for _, t in self.text]
        for child in self.children:
            parts.append(child.all_text())
        return "".join(parts)


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, 1, None)
        self.cur = self.root
        self.doctype = False
        self.styles = []        # (line, css)
        self.in_style = False
        self.style_line = 1
        self.feed(source)
        self.close()

    def handle_decl(self, decl):
        if decl.strip().lower().startswith("doctype"):
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs},
                    self.getpos()[0], self.cur)
        self.cur.children.append(node)
        if tag in VOID:
            return
        self.cur = node
        if tag == "style":
            self.in_style = True
            self.style_line = node.line

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs},
                    self.getpos()[0], self.cur)
        self.cur.children.append(node)

    def handle_endtag(self, tag):
        node = self.cur
        while node is not None and node.tag != tag:
            node = node.parent
        if node is None or node is self.root:
            return              # stray end tag
        if tag == "style":
            self.in_style = False
        self.cur = node.parent

    def handle_data(self, data):
        if self.in_style:
            self.styles.append((self.style_line, data))
        self.cur.text.append((self.getpos()[0], data))


# ---------- the checks ----------

class Report:
    def __init__(self, name):
        self.name = name
        self.items = []

    def add(self, level, line, code, message):
        self.items.append((line, level, code, message))

    def error(self, line, code, message):
        self.add("ERROR", line, code, message)

    def warn(self, line, code, message):
        self.add("WARN", line, code, message)


def suggest(name, known):
    if "-" in name:
        parts = [p for p in name.split("-") if p]
        if len(parts) > 1 and all(p in known for p in parts):
            return 'class="%s"' % " ".join(parts)
    near = difflib.get_close_matches(name, sorted(known), n=3, cutoff=0.7)
    return ", ".join(near)


def find_css(page, page_dir):
    """Return (desk css path, other local css texts)."""
    desk = None
    others = []
    for node in page.root.walk():
        if node.tag != "link" or "stylesheet" not in (node.attrs.get("rel") or "").lower():
            continue
        href = node.attrs.get("href") or ""
        if re.match(r"^[a-z][a-z0-9+.-]*:|^//", href, re.I):
            continue
        path = os.path.normpath(os.path.join(page_dir, href.split("?")[0].split("#")[0]))
        if not os.path.isfile(path):
            continue
        if re.match(r"^desk(\.min)?\.css$", os.path.basename(path)):
            desk = desk or path
        elif not os.path.basename(path).startswith("desk.icons"):
            others.append(path)
    if desk is None:
        for name in ("desk.css", "desk.min.css"):
            if os.path.isfile(os.path.join(HERE, name)):
                desk = os.path.join(HERE, name)
                break
    return desk, others


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def find_icons_css(desk_path):
    folders = [os.path.dirname(desk_path)] if desk_path else []
    for folder in folders + [HERE]:
        for name in ("desk.icons.css", "desk.icons.min.css"):
            if os.path.isfile(os.path.join(folder, name)):
                return os.path.join(folder, name)
    return None


def load_icons(desk_path):
    for folder in (os.path.dirname(desk_path) if desk_path else None, HERE):
        if folder and os.path.isfile(os.path.join(folder, "icons.json")):
            with open(os.path.join(folder, "icons.json"), encoding="utf-8") as fh:
                return {entry["code"].upper() for entry in json.load(fh)}
    return None


def is_private(ch):
    cp = ord(ch)
    return 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD or 0x100000 <= cp <= 0x10FFFD


def page_classes_elsewhere(page, desk):
    """Classes the page or desk.css define themselves: those are not icon-only classes."""
    found = set()
    for _, css in page.styles:
        found |= css_classes(css)
    if desk:
        found |= css_classes(read(desk))
    return found


def check_file(path):
    report = Report(path)
    try:
        source = read(path)
    except (OSError, UnicodeDecodeError) as err:
        report.error(1, "read", "cannot read the file as UTF-8: %s" % err)
        return report
    page = Page(source)
    nodes = list(page.root.walk())
    by_tag = lambda tag: [n for n in nodes if n.tag == tag]

    desk, others = find_css(page, os.path.dirname(os.path.abspath(path)))
    known = set()
    settings = {name: set() for name in SETTINGS}
    if desk is None:
        report.error(1, "no-css", "desk.css or desk.min.css not found: link it and keep it "
                     "next to check.py or at the linked path")
    else:
        css = read(desk)
        known |= css_classes(css)
        settings = css_settings(css)
    icons_css = find_icons_css(desk)
    icon_classes = css_classes(read(icons_css)) if icons_css else set()
    known |= icon_classes
    for other in others:
        known |= css_classes(read(other))
    for _, css in page.styles:
        known |= css_classes(css)
    settings["data-density"].add("normal")

    # --- page basics
    links = [n for n in by_tag("link") if "stylesheet" in (n.attrs.get("rel") or "").lower()]
    hrefs = [n.attrs.get("href") or "" for n in links]
    if not any(re.search(r"(^|/)desk(\.min)?\.css(\?|#|$)", h) for h in hrefs):
        report.error(1, "link-css", 'link desk.css: <link rel="stylesheet" href="desk.min.css">')
    if not page.doctype:
        report.error(1, "doctype", "start the file with <!doctype html>")
    html = by_tag("html")
    if not html or not (html[0].attrs.get("lang") or "").strip():
        report.error(html[0].line if html else 1, "lang", '<html> needs lang, for example lang="en"')
    if not any((n.attrs.get("charset") or "").lower() == "utf-8" for n in by_tag("meta")):
        report.error(1, "charset", 'add <meta charset="utf-8"> in <head>')
    if not any((n.attrs.get("name") or "").lower() == "viewport" for n in by_tag("meta")):
        report.error(1, "viewport", 'add <meta name="viewport" content="width=device-width, initial-scale=1">')
    titles = by_tag("title")
    if not titles or not titles[0].all_text().strip():
        report.error(titles[0].line if titles else 1, "title", "add a non-empty <title>")
    if not by_tag("main"):
        report.warn(1, "main", "no <main> element")

    # --- classes
    for node in nodes:
        for name in node.classes():
            if re.search(r"[{}$<>%]", name):
                continue        # template syntax
            if name not in known:
                hint = suggest(name, known)
                if re.match(r"^(icon-|mdi|md-|fa[a-z]?$|fa-|material-icons|bi-|bi$)", name):
                    hint = ("icons are typed as character codes, not classes; "
                            "look the code up in icons.json")
                elif hint:
                    hint = "did you mean %s" % hint
                report.error(node.line, "unknown-class",
                             "class '%s' is not defined%s" % (name, " (%s)" % hint if hint else ""))
        if any(c.startswith("cols-") for c in node.classes()) and not node.has_class("grid"):
            report.error(node.line, "cols-without-grid", ".cols-N only works together with .grid")

    # --- page settings
    for node in html[:1]:
        for name in SETTINGS:
            if name in node.attrs:
                value = node.attrs[name]
                if settings[name] and value not in settings[name]:
                    report.error(node.line, "setting-value", '%s="%s" is not a value of desk.css (use: %s)'
                                 % (name, value, ", ".join(sorted(settings[name]))))

    # --- icons
    codes = load_icons(desk)
    icon_uses = []
    for node in nodes:
        for line, text in node.text:
            if node.tag in ("script", "style"):
                continue
            for idx, ch in enumerate(text):
                if is_private(ch):
                    icon_uses.append((line + text[:idx].count("\n"), ch))
        for value in node.attrs.values():
            for ch in value:
                if is_private(ch):
                    icon_uses.append((node.line, ch))
    for line, ch in icon_uses:
        code = "%X" % ord(ch)
        if codes is None:
            report.warn(line, "icons-json", "icons.json not found, cannot check U+%s" % code)
        elif code not in codes:
            report.error(line, "icon-code", "U+%s is not an icon of desk.css: copy a code from icons.json, never guess" % code)
    icons_linked = any(re.search(r"(^|/)desk\.icons(\.min)?\.css(\?|#|$)", h) for h in hrefs)
    icon_only = icon_classes - page_classes_elsewhere(page, desk)
    icon_class_uses = [n.line for n in nodes if icon_only & set(n.classes())]
    if (icon_uses or icon_class_uses) and not icons_linked:
        report.error((icon_uses[0][0] if icon_uses else icon_class_uses[0]), "icons-css", 'icons are used but desk.icons.css is not linked: '
                     '<link rel="stylesheet" href="desk.icons.min.css">')

    # --- ids and targets
    ids = {}
    for node in nodes:
        ident = node.attrs.get("id")
        if ident:
            if ident in ids:
                report.error(node.line, "dup-id", "id '%s' is already used on line %d" % (ident, ids[ident]))
            ids[ident] = node.line
    for node in nodes:
        for attr in ("commandfor", "popovertarget"):
            target = node.attrs.get(attr)
            if target is not None and target not in ids:
                report.error(node.line, "target-missing", '%s="%s" points at an id that does not exist' % (attr, target))
        command = node.attrs.get("command")
        if command is not None and command not in COMMANDS and not command.startswith("--"):
            report.error(node.line, "command", 'command="%s" is not valid (use: %s)' % (command, ", ".join(sorted(COMMANDS))))
        if "command" in node.attrs and "commandfor" not in node.attrs:
            report.error(node.line, "command", "command needs commandfor")

    # --- accessibility basics
    for node in by_tag("img"):
        if "alt" not in node.attrs:
            report.error(node.line, "img-alt", '<img> needs alt (alt="" when purely decorative)')
    levels = [(n.line, int(n.tag[1])) for n in nodes if re.fullmatch(r"h[1-6]", n.tag)]
    for (_, before), (line, after) in zip(levels, levels[1:]):
        if after > before + 1:
            report.warn(line, "heading-skip", "heading jumps from h%d to h%d" % (before, after))
    for node in by_tag("button"):
        if node.has_class("icon") or not node.all_text().strip() or all(is_private(c) or c.isspace() for c in node.all_text()):
            named = node.attrs.get("aria-label") or node.attrs.get("title") or node.attrs.get("aria-labelledby")
            visible = "".join(c for c in node.all_text() if not is_private(c)).strip()
            if not named and not visible:
                report.error(node.line, "button-name", "icon-only button needs aria-label")
    labelled = {n.attrs.get("for") for n in by_tag("label") if n.attrs.get("for")}
    for node in nodes:
        if node.tag not in ("input", "select", "textarea"):
            continue
        if node.tag == "input" and (node.attrs.get("type") or "text").lower() in FIELD_SKIP:
            continue
        inside = False
        up = node.parent
        while up is not None:
            if up.tag == "label":
                inside = True
                break
            up = up.parent
        if not (inside or node.attrs.get("id") in labelled or node.attrs.get("aria-label")
                or node.attrs.get("aria-labelledby") or node.attrs.get("title")):
            report.warn(node.line, "field-name", "<%s> has no label (wrap it in <label> or add aria-label)" % node.tag)
    for node in nodes:
        if (node.has_class("table-wrap") or node.tag == "pre") and "tabindex" not in node.attrs:
            report.warn(node.line, "scroll-focus", '%s scrolls: add tabindex="0" so the keyboard can reach it'
                        % ("<pre>" if node.tag == "pre" else ".table-wrap"))

    # --- style
    for line, css in page.styles:
        if "!important" in strip_css(css):
            report.warn(line, "important", "!important in <style>: not needed, unlayered CSS already wins over desk.css")
    return report


def icon_lookup(words):
    codes_path = None
    for folder in (HERE,):
        if os.path.isfile(os.path.join(folder, "icons.json")):
            codes_path = os.path.join(folder, "icons.json")
    if codes_path is None:
        sys.stderr.write("icons.json not found next to check.py\n")
        return 1
    with open(codes_path, encoding="utf-8") as fh:
        entries = json.load(fh)
    words = [w.lower() for w in words]
    hits = [e for e in entries
            if all(w in e["name"].lower() or w in e["group"].lower() for w in words)]
    for e in hits:
        print("%-22s %-16s &#x%s;" % (e["name"], e["group"], e["code"]))
    if not hits:
        print("no icon matches %s; groups: %s" % (" ".join(words), ", ".join(sorted({e["group"] for e in entries}))))
        return 1
    return 0


def main(argv):
    if argv and argv[0] == "--icon":
        return icon_lookup(argv[1:]) if len(argv) > 1 else icon_lookup([""])
    strict = "--strict" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files or "-h" in argv or "--help" in argv:
        sys.stdout.write(__doc__)
        return 2
    errors = warns = 0
    for path in files:
        report = check_file(path)
        for line, level, code, message in sorted(report.items, key=lambda i: (i[0], i[1])):
            print("%s:%d: %s [%s] %s" % (path, line, level, code, message))
            if level == "ERROR":
                errors += 1
            else:
                warns += 1
    print("%d error%s, %d warning%s in %d file%s" % (
        errors, "" if errors == 1 else "s", warns, "" if warns == 1 else "s",
        len(files), "" if len(files) == 1 else "s"))
    return 1 if errors or (strict and warns) else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:   # output piped into head and the like
        sys.stderr.close()
        sys.exit(0)
