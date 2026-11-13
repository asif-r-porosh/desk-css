# Real-browser check

Opens `docs.html`, `index.html` and the five templates in a real browser through WebDriver and
reports problems. Meant to be re-run after any change to the CSS.

```sh
tests/browser/run.sh firefox safari      # from the repository root
```

First run creates `.venv/` and downloads axe-core 4.10.2 (hash-checked) into `.cache/`.

## What is checked

- Feature support: `light-dark()`, relative colour, `:has()`, popover, `commandfor`,
  cascade layers, `color-mix()`, and the soft-fallback features.
- Per page, at 1440, 700 and 390 px: sideways page scroll, fonts loading, light and dark
  colours, motion tokens, axe-core (light and dark, widest size), screenshots.
- Dialog opens, animates, closes on Escape. Drawer opens, slides, closes on Escape.
- Inbox: clicking a message selects it and does not scroll the page on wide screens.
- `docs.html` and `templates/inbox.html` opened straight from disk: fonts still load.

## Output

`out/` (screenshots), `results.json`, `summary.txt`. All git-ignored.

## Notes

- Safari: run `safaridriver --enable` once. Safari opens visible windows; leave them alone
  while the run is going.
- Desktop windows cannot go much below 450 px, so the narrow test is nominally 390 px
  but the real width is recorded in the summary. A phone still needs a manual look.
- A "note: ... animation not seen" line can mean macOS Reduce motion is switched on.
- Chrome: `run.sh chrome` works with any installed Chrome.
