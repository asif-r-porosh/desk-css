#!/usr/bin/env python3
"""Real-browser check for desk.css (Firefox, Safari, Chrome) through WebDriver.

Loads docs.html and the four templates, runs feature probes, layout, font, colour
and accessibility (axe-core) checks, exercises the dialog, the drawer and the inbox,
and writes screenshots, results.json and summary.txt into tests/browser/out/.

Usage (from the repository root):
  tests/browser/run.sh firefox safari
  tests/browser/run.sh firefox
  tests/browser/run.sh chrome

Safari needs `safaridriver --enable` once. Firefox and Chrome drivers come from
Selenium Manager. See tests/browser/README.md.
"""
import hashlib
import http.server
import json
import pathlib
import socketserver
import sys
import threading
import time
import traceback
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]   # tests/browser -> repository root
OUT = HERE / "out"
PAGES = ["docs.html", "templates/inbox.html", "templates/dashboard.html",
         "templates/kanban.html", "templates/showcase.html"]
WIDTHS = [1440, 700, 390]          # requested; the browser may refuse the narrowest
FILE_PAGES = ["docs.html", "templates/inbox.html"]   # also opened straight from disk
AXE_VERSION = "4.10.2"
AXE_SHA256 = "b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3"
AXE_URL = f"https://cdnjs.cloudflare.com/ajax/libs/axe-core/{AXE_VERSION}/axe.min.js"


def load_axe():
    """Return axe-core source, downloaded once into .cache/ and checked against a pinned hash."""
    cached = HERE / ".cache" / f"axe-{AXE_VERSION}.min.js"
    if not cached.exists():
        cached.parent.mkdir(exist_ok=True)
        with urllib.request.urlopen(AXE_URL, timeout=60) as r:
            cached.write_bytes(r.read())
    data = cached.read_bytes()
    if hashlib.sha256(data).hexdigest() != AXE_SHA256:
        cached.unlink()
        sys.exit(f"axe-core download does not match the pinned hash: {AXE_URL}")
    return data.decode("utf-8")


AXE = load_axe()

# ---------- probes: JavaScript function bodies, run in the page ----------

JS_ENV = """
return {ua: navigator.userAgent, innerWidth: innerWidth, innerHeight: innerHeight, dpr: devicePixelRatio};
"""

JS_FEATURES = """
const s = (p, v) => { try { return CSS.supports(p, v); } catch (e) { return false; } };
const sel = (q) => { try { return CSS.supports('selector(' + q + ')'); } catch (e) { return false; } };
return {
  'light-dark()': s('color', 'light-dark(red, blue)'),
  'relative color': s('color', 'oklch(from red l c h)'),
  'color-mix()': s('color', 'color-mix(in srgb, red, blue)'),
  ':has()': sel(':has(a)'),
  ':focus-visible': sel(':focus-visible'),
  'popover': 'popover' in HTMLElement.prototype,
  'commandfor': 'commandForElement' in HTMLButtonElement.prototype,
  'cascade layers': typeof CSSLayerBlockRule !== 'undefined',
  'dvh unit': s('height', '1dvh'),
  'lh unit': s('height', '1lh'),
  'text-wrap: balance': s('text-wrap', 'balance'),
  'accent-color': s('accent-color', 'red'),
  'contrast-color()': s('color', 'contrast-color(red)'),
  'scrollbar-width': s('scrollbar-width', 'none'),
  '@starting-style': typeof CSSStartingStyleRule !== 'undefined'
};
"""

JS_LAYOUT = """
const vw = document.documentElement.clientWidth;
const inScroller = (el) => {
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX;
    if ((o === 'auto' || o === 'scroll' || o === 'hidden') && p.scrollWidth > p.clientWidth) return true;
  }
  return false;
};
const name = (el) => el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ')[0] : '');
const wide = [];
for (const el of document.body.querySelectorAll('*')) {
  const r = el.getBoundingClientRect();
  if (r.width && r.right > vw + 1 && getComputedStyle(el).position !== 'fixed') {
    wide.push(name(el) + ' right=' + Math.round(r.right) + ' pos=' + getComputedStyle(el).position + (inScroller(el) ? ' (inside scroll box)' : ''));
    if (wide.length >= 8) break;
  }
}
return {scrollWidth: document.documentElement.scrollWidth, clientWidth: vw,
        pageOverflowsX: document.documentElement.scrollWidth > vw + 1, wideElements: wide,
        docHeight: document.documentElement.scrollHeight};
"""

JS_FONTS = """
const done = arguments[arguments.length - 1];
const faces = [...document.fonts];
Promise.all(faces.map(f => f.load().then(() => f.family.replace(/"/g, '') + ' ' + f.weight + ' ' + f.style + ': loaded',
                                         () => f.family.replace(/"/g, '') + ' ' + f.weight + ' ' + f.style + ': ERROR'))).then(list =>
  done({faces: list, failed: list.filter(x => x.endsWith('ERROR')), count: list.length,
        bodyFont: getComputedStyle(document.body).fontFamily.slice(0, 60)}));
"""

JS_COLORS = """
const cs = (el) => el ? {color: getComputedStyle(el).color, bg: getComputedStyle(el).backgroundColor} : null;
const root = document.documentElement;
const out = {};
for (const theme of ['light', 'dark']) {
  root.dataset.theme = theme;
  out[theme] = {body: cs(document.body), badge: cs(document.querySelector('.badge.primary')),
                accentInk: getComputedStyle(root).getPropertyValue('--accent-ink').trim().slice(0, 60)};
}
delete root.dataset.theme;
out.themesDiffer = JSON.stringify(out.light.body) !== JSON.stringify(out.dark.body);
return out;
"""

JS_MOTION = """
const g = (q) => { const e = document.querySelector(q); return e ? getComputedStyle(e).transitionDuration + ' ' + getComputedStyle(e).transitionTimingFunction.slice(0, 30) : null; };
return {button: g('button'), navLink: g('nav a'), tab: g('.tabs > a, .tabs > button'),
        durToken: getComputedStyle(document.documentElement).getPropertyValue('--dur').trim(),
        easeToken: getComputedStyle(document.documentElement).getPropertyValue('--ease').trim()};
"""

JS_DIALOG_STATE = """
const enterAnims = () => document.getAnimations().map(a => a.animationName || '').filter(n => /^desk-(rise|fade|slide)$/.test(n));
const d = document.querySelector('dialog[open]');
if (!d) return {open: false};
return {open: true, animations: enterAnims(),
        opacity: getComputedStyle(d).opacity};
"""

JS_DRAWER_STATE = """
const enterAnims = () => document.getAnimations().map(a => a.animationName || '').filter(n => /^desk-(rise|fade|slide)$/.test(n));
const s = document.querySelector('.sidebar[popover]');
if (!s) return {exists: false};
return {exists: true, open: s.matches(':popover-open'), animations: enterAnims()};
"""

JS_INBOX_STATE = """
const msgs = [...document.querySelectorAll('.msg')];
const shown = msgs.filter(m => getComputedStyle(m).display !== 'none');
const list = document.querySelector('.list');
return {hash: location.hash, scrollY: Math.round(scrollY), shownCount: shown.length,
        shownId: shown[0] && shown[0].previousElementSibling ? shown[0].previousElementSibling.id : null,
        listShown: list ? getComputedStyle(list).display !== 'none' : null};
"""

JS_AXE = """
const done = arguments[arguments.length - 1];
axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']}})
  .then(r => done({violations: r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length,
                    sample: v.nodes[0] ? v.nodes[0].target.join(' ').slice(-80) : ''}))}))
  .catch(e => done({error: String(e)}));
"""

JS_FONTS_READY = """
const done = arguments[arguments.length - 1];
document.fonts.ready.then(() => done(true), () => done(false));
"""


# ---------- helpers ----------

class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *a):
        pass


def serve():
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Quiet)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def make_driver(name):
    if name == "firefox":
        o = webdriver.FirefoxOptions()
        o.add_argument("-headless")
        return webdriver.Firefox(options=o)
    if name == "safari":
        return webdriver.Safari()
    if name == "chrome":
        o = webdriver.ChromeOptions()
        o.add_argument("--headless=new")
        return webdriver.Chrome(options=o)
    raise SystemExit(f"unknown browser: {name}")


def set_viewport(d, w, h=900):
    """Resize the window until the page viewport is as wide as requested, or the browser refuses."""
    d.set_window_size(w, h)
    for _ in range(3):
        iw, ih = d.execute_script("return [innerWidth, innerHeight];")
        if iw == w and ih == h:
            break
        cw, ch = d.get_window_size()["width"], d.get_window_size()["height"]
        d.set_window_size(cw + (w - iw), ch + (h - ih))
    return d.execute_script("return innerWidth;")


def load(d, url):
    d.get(url)
    d.set_script_timeout(60)
    d.execute_async_script(JS_FONTS_READY)
    time.sleep(0.4)


def visible(d, css):
    for e in d.find_elements(By.CSS_SELECTOR, css):
        try:
            if e.is_displayed():
                return e
        except Exception:
            pass
    return None


def esc(d):
    ActionChains(d).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.2)


def shot(d, name):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save_screenshot(str(path))
    return str(path.relative_to(OUT))


def safe(label, fn, sink):
    try:
        sink[label] = fn()
    except Exception as e:      # keep going: one failed probe must not hide the rest
        sink[label] = {"error": f"{type(e).__name__}: {str(e).splitlines()[0][:200] if str(e) else ''}"}


# ---------- one browser ----------

def check_browser(name, base):
    res = {"browser": name, "pages": {}}
    d = make_driver(name)
    try:
        res["version"] = d.capabilities.get("browserVersion") or d.capabilities.get("version")
        res["platform"] = d.capabilities.get("platformName")
        for page in PAGES:
            pr = res["pages"][page] = {}
            slug = page.replace("/", "_").replace(".html", "")
            for w in WIDTHS:
                wr = pr[str(w)] = {}
                try:
                    load(d, f"{base}/{page}")
                    actual = set_viewport(d, w)
                    wr["requested"], wr["actual"] = w, actual
                    time.sleep(0.3)
                    safe("env", lambda: d.execute_script(JS_ENV), wr)
                    if w == WIDTHS[0] and page == PAGES[0]:
                        safe("features", lambda: d.execute_script(JS_FEATURES), res)
                    safe("layout", lambda: d.execute_script(JS_LAYOUT), wr)
                    if w == WIDTHS[0]:
                        safe("fonts", lambda: d.execute_async_script(JS_FONTS), wr)
                        safe("colors", lambda: d.execute_script(JS_COLORS), wr)
                        safe("motion", lambda: d.execute_script(JS_MOTION), wr)
                    # screenshots, light then dark
                    safe("screenshot_light", lambda: shot(d, f"{name}/{slug}-{w}-light.png"), wr)
                    if w == WIDTHS[0]:
                        d.execute_script(AXE)
                        safe("axe_light", lambda: d.execute_async_script(JS_AXE), wr)
                    d.execute_script("document.documentElement.dataset.theme = 'dark';")
                    time.sleep(0.3)
                    safe("screenshot_dark", lambda: shot(d, f"{name}/{slug}-{w}-dark.png"), wr)
                    if w == WIDTHS[0]:
                        safe("axe_dark", lambda: d.execute_async_script(JS_AXE), wr)
                    d.execute_script("delete document.documentElement.dataset.theme;")
                    # interactions
                    narrow = actual < 768
                    if narrow:
                        def drawer():
                            btn = visible(d, "[popovertarget]")
                            if not btn:
                                return {"skipped": "no visible drawer button"}
                            btn.click()
                            time.sleep(0.12)
                            mid = d.execute_script(JS_DRAWER_STATE)
                            time.sleep(0.4)
                            end = d.execute_script(JS_DRAWER_STATE)
                            shot(d, f"{name}/{slug}-{w}-drawer.png")
                            esc(d)
                            after = d.execute_script(JS_DRAWER_STATE)
                            return {"mid": mid, "end": end, "closedByEscape": not after.get("open", False)}
                        safe("drawer", drawer, wr)
                    else:
                        def dialog():
                            btn = visible(d, "button[commandfor]")
                            if not btn:
                                return {"skipped": "no dialog button on this page"}
                            btn.click()
                            time.sleep(0.12)
                            mid = d.execute_script(JS_DIALOG_STATE)
                            time.sleep(0.4)
                            end = d.execute_script(JS_DIALOG_STATE)
                            shot(d, f"{name}/{slug}-{w}-dialog.png")
                            esc(d)
                            after = d.execute_script(JS_DIALOG_STATE)
                            return {"mid": mid, "end": end, "closedByEscape": not after.get("open", False)}
                        safe("dialog", dialog, wr)
                    if page == "templates/inbox.html":
                        def inbox():
                            load(d, f"{base}/{page}")
                            set_viewport(d, w)
                            before = d.execute_script(JS_INBOX_STATE)
                            link = visible(d, ".list a[href=\"#m3\"]")
                            link.click()
                            time.sleep(0.4)
                            after = d.execute_script(JS_INBOX_STATE)
                            shot(d, f"{name}/{slug}-{w}-message.png")
                            return {"before": before, "afterClick": after}
                        safe("inbox", inbox, wr)
                except Exception as e:
                    wr["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:200] if str(e) else ''}"
                    traceback.print_exc(limit=1)
        # pages opened straight from disk: stylesheet and fonts must still resolve
        res["fromDisk"] = {}
        for page in FILE_PAGES:
            def disk():
                load(d, (ROOT / page).as_uri())
                set_viewport(d, WIDTHS[0])
                return {"fonts": d.execute_async_script(JS_FONTS), "layout": d.execute_script(JS_LAYOUT),
                        "colors": d.execute_script(JS_COLORS)["light"]["body"]}
            safe(page, disk, res["fromDisk"])
    finally:
        try:
            d.quit()
        except Exception:
            pass
    return res


# ---------- summary ----------

def summarize(allres):
    lines = []
    for r in allres:
        lines.append(f"=== {r['browser']} {r.get('version', '?')} ({r.get('platform', '?')})")
        if "error" in r:
            lines.append("  FAILED TO RUN: " + r["error"])
            continue
        feats = r.get("features", {})
        miss = [k for k, v in feats.items() if v is False]
        lines.append("  features missing: " + (", ".join(miss) if miss else "none"))
        for page, widths in r["pages"].items():
            for w, wr in widths.items():
                tag = f"  {page} @{wr.get('actual', '?')}px (asked {w})"
                issues = []
                if "error" in wr:
                    issues.append("ERROR " + wr["error"])
                lay = wr.get("layout", {})
                if lay.get("pageOverflowsX"):
                    issues.append(f"page scrolls sideways ({lay.get('scrollWidth')} > {lay.get('clientWidth')}): {lay.get('wideElements')}")
                fo = wr.get("fonts")
                if fo and not fo.get("error") and (fo.get("failed") or not fo.get("count")):
                    issues.append(f"fonts failed: {fo.get('failed') or 'no font faces found'}")
                co = wr.get("colors")
                if co and not co.get("error") and not co.get("themesDiffer"):
                    issues.append("light and dark look the same")
                for k in ("axe_light", "axe_dark"):
                    ax = wr.get(k)
                    if ax and ax.get("violations"):
                        issues.append(f"{k}: " + "; ".join(f"{v['id']}({v['nodes']})" for v in ax["violations"]))
                    elif ax and ax.get("error"):
                        issues.append(f"{k} error: {ax['error']}")
                dl = wr.get("dialog")
                if dl and not dl.get("skipped") and not dl.get("error"):
                    if not dl["end"].get("open"):
                        issues.append("dialog did not open")
                    elif "desk-rise" not in dl["mid"].get("animations", []):
                        issues.append("note: dialog opening animation not seen (Reduce motion switched on in macOS settings would cause this)")
                    elif not dl.get("closedByEscape"):
                        issues.append("dialog did not close on Escape")
                dr = wr.get("drawer")
                if dr and not dr.get("skipped") and not dr.get("error"):
                    if not dr["end"].get("open"):
                        issues.append("drawer did not open")
                    elif "desk-slide" not in dr["mid"].get("animations", []):
                        issues.append("note: drawer slide animation not seen (Reduce motion would cause this)")
                    if not dr.get("closedByEscape"):
                        issues.append("drawer did not close on Escape")
                ib = wr.get("inbox")
                if ib and not ib.get("error"):
                    a = ib["afterClick"]
                    if a.get("hash") != "#m3":
                        issues.append(f"inbox click did not select message 3: {a}")
                    if actual_wide(wr) and a.get("scrollY", 0) > 2:
                        issues.append(f"inbox page scrolled {a['scrollY']}px on click (wide)")
                lines.append(tag + ": " + ("ok" if not issues else ""))
                for i in issues:
                    lines.append("      - " + i)
        for page, v in r.get("fromDisk", {}).items():
            if v.get("error"):
                lines.append(f"  from disk {page}: ERROR {v['error']}")
            else:
                f = v["fonts"]
                lines.append(f"  from disk {page}: fonts {'ok' if f.get('count') and not f.get('failed') else 'FAILED ' + str(f.get('failed'))}")
    return "\n".join(lines)


def actual_wide(wr):
    return (wr.get("actual") or 0) >= 1100


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not names:
        sys.exit(__doc__)
    OUT.mkdir(exist_ok=True)
    srv, base = serve()
    results = []
    for n in names:
        print(f"--- {n}: starting", flush=True)
        try:
            results.append(check_browser(n, base))
        except Exception as e:
            traceback.print_exc(limit=2)
            results.append({"browser": n, "error": f"{type(e).__name__}: {e}"})
        print(f"--- {n}: finished", flush=True)
    srv.shutdown()
    (HERE / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    text = summarize(results)
    (HERE / "summary.txt").write_text(text + "\n", encoding="utf-8")
    print("\n" + text)
    print(f"\nSaved: {HERE / 'results.json'}, {HERE / 'summary.txt'}, screenshots in {OUT}")


if __name__ == "__main__":
    main()
