# desk.css

A small CSS library for everyday tools: admin screens, dashboards, internal apps.

Many CSS frameworks are tuned for marketing pages, with large buttons, generous padding and big type. On a laptop, a data-heavy screen built with them feels zoomed in. Classless libraries stay small and quiet, but they style bare HTML elements only; layouts such as a sidebar, or components such as status badges, still need custom CSS.

desk.css sits in between. Plain HTML looks right with no classes. A short list of classes covers the rest. No JavaScript, no build step to use it, no 12-column grid.

## Features

- Plain HTML styled out of the box: text, tables, forms, dialogs, details.
- A small set of components: buttons, cards, alerts, badges, tabs, dropdowns, toasts, stats.
- An app shell with a sidebar that becomes a drawer on phones.
- Hanken Grotesk for text and JetBrains Mono for code, bundled; serif text uses the system font.
- Light and dark mode, following the system setting by default.
- One accent color, from which the related shades are derived.
- 170 optional icons, typed straight into text.

About 7 KB over the wire, plus fonts.

## Getting started

Copy `desk.min.css` and the `fonts/` folder from `dist/` into the project, side by side. For icons, add `desk.icons.min.css` as well.

```html
<link rel="stylesheet" href="desk.min.css">
<link rel="stylesheet" href="desk.icons.min.css">
```

The readable `desk.css` and `desk.icons.css` in `dist/` hold the same rules, with comments and whitespace kept.

`docs.html` shows every element and component next to the markup.

## Settings

Three attributes on `<html>` change the whole page. Without these attributes, the defaults apply.

```html
<html data-theme="dark" data-density="compact" data-accent="teal">
```

- `data-theme`: `light` or `dark`. Default follows the system.
- `data-density`: `normal` (16px text, 40px controls) or `compact` (14px text, 32px controls).
- `data-accent`: `green`, `teal`, `purple` or `orange`. Default is blue.

Any other accent color takes one line:

```css
:root { --accent: #198038; }
```

Links, buttons, focus rings, switches and tints follow the accent. Status colors (ok, warning, danger, info) do not, so a failure never looks like a success.

## Icons

With `desk.icons.min.css` (or `desk.icons.css`) loaded, an icon is its character code placed in text:

```html
<h2>&#xF02DC; Dashboard</h2>
<button class="danger">&#xF01B4; Delete</button>
```

Each icon takes the size and color of the surrounding text. Using the character code, with no icon tags or classes, is deliberate: icon markup stays as short as the text around it. The full list, with search and copy, is in `docs.html`.

The icons are from [Material Design Icons](https://github.com/Templarian/MaterialDesign) by Pictogrammers (Apache 2.0), taken through [Nerd Fonts](https://github.com/ryanoasis/nerd-fonts) Symbols (MIT). Only the 170 listed glyphs are included.

## Templates

`templates/` holds single-page examples. Each links `../dist/desk.css`, so it opens straight from a clone.

- `inbox.html`: three-pane mailbox; messages switch with plain CSS (`:target`).
- `dashboard.html`: stat cards, a bar chart in CSS, a table with filter and pagination, an activity list.
- `kanban.html`: a board with scrolling columns and a dialog for new cards.
- `blog.html`: an article page with prose, a table, code, a sticky contents list and a sign-up form.
- `showcase.html`: every component, inside an app shell.

All data is invented. Apart from the showcase, the pages use script only for the theme and density buttons.

## Overrides

All rules live in a cascade layer named `desk`. CSS written outside a layer always wins, so `!important` is never needed. Every size, space and color is a CSS variable, changeable on `:root`.

## Browser support

Target: the latest stable release of Chrome, Edge, Firefox and Safari. Older versions are not supported.

Tested: Chromium 153 (Chrome for Testing, the engine behind Chrome and Edge), Firefox 159 and Safari 26.6 on macOS. Each run covers layout, fonts, light and dark colors, dialogs, the phone drawer and accessibility (axe-core) on the docs page and the templates. Edge is not run separately. A real phone is not covered. The checks are in `tests/browser/` and run with `tests/browser/run.sh firefox safari`.

Minimum versions, from the web-features dataset (3.45.0) that Baseline is built on:

| | Chrome, Edge | Firefox | Safari |
| --- | --- | --- | --- |
| Stylesheet | 125 | 128 | 18 |
| Dialog buttons in the docs and templates | 135 | 144 | 26.2 |

The stylesheet needs `light-dark()` and relative colors (`oklch(from ...)`), which set the floor above. `:has()`, cascade layers, popover and `color-mix()` are older. A few details fall back quietly instead of breaking: `accent-color` before Safari 26.2, `scrollbar-width` before Safari 18.2, and `text-wrap: balance`.

The dialog buttons in the docs and templates use `commandfor` and `command="show-modal"`. In older browsers those buttons do nothing; a dialog can still be opened with `showModal()` in script. The stylesheet itself does not depend on these attributes.

## Building

`dist/` is generated from `src/`. Edit `src/desk.css`, then run:

```sh
python3 tools/build.py
```

That writes the readable and minified files to `dist/` and refreshes the icon list in `docs.html`. Python 3 is the only requirement.

Changing the icon set (`tools/icons.txt`) or updating the fonts needs `fonttools` and `brotli`:

```sh
python3 tools/build.py --fonts <fonts-folder> [<SymbolsNerdFont-Regular.ttf>]
```

The fonts folder holds three variable font files from the [Google Fonts repository](https://github.com/google/fonts), under these names: `HankenGrotesk[wght].ttf` and `HankenGrotesk-Italic[wght].ttf` (folder `ofl/hankengrotesk`), and `JetBrainsMono[wght].ttf` (folder `ofl/jetbrainsmono`). The build pins the weights (450 and 600) and cuts the glyphs down to Latin. The Symbols Nerd Font file is only needed to rebuild the icons.

## License

desk.css is released under the [MIT License](LICENSE).

Fonts and icons carry their own licenses, included in `dist/fonts/`:

- Hanken Grotesk: SIL Open Font License 1.1 (`LICENSE-Hanken-Grotesk.txt`).
- JetBrains Mono: SIL Open Font License 1.1 (`LICENSE-JetBrains-Mono.txt`).
- Material Design Icons: Apache 2.0, with the Pictogrammers notice (`LICENSE-Material-Design-Icons.txt`).
- Nerd Fonts Symbols, the source of the icon glyphs: MIT (`LICENSE-Nerd-Fonts.txt`).

---
RnD: Used Claude Sonnet 5.5
