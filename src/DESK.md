# desk.css: guide for coding agents

desk.css is a small CSS library for internal tools: dashboards, forms, tables, admin pages.
Plain HTML elements are already styled. Add a class only to pick a variant or a layout.
There is no JavaScript and no build step. These rules are the same for every agent and every model.

## Rules

1. Use only the classes listed in this file. Do not invent class names. Do not use classes from Bootstrap, Tailwind or any other framework.
2. Write plain HTML first. `button`, `input`, `select`, `textarea`, `table`, `dialog`, `details`, `progress`, `h1` to `h6`, `blockquote`, `pre` and the rest need no class.
3. Do not set colors, fonts, sizes or spacing with `style=""`. Change a token on `:root` instead (see Tokens). Project CSS goes outside any `@layer`; it wins over desk.css without `!important`.
4. Icons are characters, never classes. Look the code up with `python3 check.py --icon <word>`, or in `icons.json`. Never write a code from memory.
5. After writing or changing a page, run `python3 check.py page.html`. Fix every `ERROR`. Fix every `WARN` unless there is a stated reason. Repeat until it prints `0 errors`.
6. Do not add what the library leaves out: a 12-column grid, a spacing utility for every side, JavaScript widgets, fonts beyond Latin.
7. Keep markup accessible: `<html lang>`, `alt` on images, a `<label>` for every field, `aria-label` on icon-only buttons, one `<main>`, headings in order, `tabindex="0"` on a `.table-wrap` and on a `<pre>`.

## Files

Copy these from `dist/` into the project, side by side:

- `desk.min.css`: the library. Required.
- `desk.icons.min.css` and `fonts/`: icons and fonts. Optional but expected. The fonts load from `fonts/` next to the CSS.
- `icons.json`, `check.py`: for the agent only. Not needed on the server.

## Minimal page

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Example tool</title>
  <link rel="stylesheet" href="desk.min.css">
  <link rel="stylesheet" href="desk.icons.min.css">
</head>
<body>
  <main class="container">
    <h1>Hello</h1>
    <p>Plain HTML, already styled.</p>
    <button class="primary">Save</button>
  </main>
</body>
</html>
```

## Page settings

Three optional attributes on `<html>`. Leave one out for its default.

| Attribute | Values | Default |
| --- | --- | --- |
| `data-theme` | `light`, `dark` | follows the system |
| `data-density` | `normal`, `compact` | `normal` |
| `data-accent` | `green`, `teal`, `purple`, `orange` | blue |

Any other accent: `:root { --accent: #198038; }`. Status colors never follow the accent.

## Icons

An icon is one private-use character typed into text. It takes the size and color of the text around it.

```html
<h2>&#xF02DC; Home</h2>
<button class="icon" aria-label="Refresh">&#xF0450;</button>
<button>&#xF04BA; Sort</button>
```

- Look up: `python3 check.py --icon home` prints `name  group  code`. The code goes into `&#x<code>;`.
- Link `desk.icons.min.css` on every page that uses icons.
- Two optional classes from that file: `.icon-lg` (bigger glyph) and `.spin` (turning glyph).
- An icon-only button needs `aria-label`.

## Buttons

```html
<button>Default</button>
<button class="primary">Primary</button>
<button class="danger">Delete</button>
<button class="ghost sm">Small ghost</button>
<a class="btn" href="/x">A link that looks like a button</a>
<button class="primary" aria-busy="true">Saving</button>
```

- Tones: `.primary .danger .ok .warn .info`.
- Shapes: `.ghost .link .icon .block`. Sizes: `.sm .lg`.
- Loading: `aria-busy="true"`. Disabled: the `disabled` attribute.
- `.group` joins controls into one bar:

```html
<div class="group">
  <span>smpp://</span>
  <input aria-label="Host" value="10.20.4.17">
  <span>:2775</span>
</div>
```

## Forms

```html
<form class="stack narrow">
  <div class="field">
    <label for="host">Host</label>
    <input id="host" value="10.20.4.17">
    <span class="help">IP address or host name.</span>
  </div>
  <div class="field error">
    <label for="tps">TPS limit</label>
    <input id="tps" value="5000" aria-invalid="true">
    <span class="help">Above the agreed limit.</span>
  </div>
  <label><input type="checkbox" checked> Retry on throttling</label>
  <label><input type="checkbox" role="switch"> Route enabled</label>
  <label><input type="radio" name="mode" checked> Final status only</label>
  <input type="range" aria-label="Weight">
  <button class="primary block">Save</button>
</form>
```

- `.field` wraps a label, a control and `.help`. Add `.error` and `aria-invalid="true"` for an invalid field.
- `.narrow` limits a form to 26rem.

## Dialog

Plain HTML, no script. `form method="dialog"` closes it.

```html
<button commandfor="rename" command="show-modal">Rename</button>
<dialog id="rename">
  <form method="dialog">
    <header><h4>Rename route</h4></header>
    <label for="new-name">New name</label>
    <input id="new-name">
    <footer>
      <button value="cancel" formnovalidate>Cancel</button>
      <button class="primary" value="save">Save</button>
    </footer>
  </form>
</dialog>
```

`command` is one of `show-modal`, `close`, `request-close`, `toggle-popover`, `show-popover`, `hide-popover`. `commandfor` is the id of the target.

## Cards, alerts, badges

```html
<article class="card">
  <header><h4>sms-gw-03</h4><span class="badge ok">healthy</span></header>
  <p>Header and footer are optional.</p>
  <footer><button class="sm ghost">Logs</button><button class="sm">Drain</button></footer>
</article>

<div class="alert warn"><span>&#xF0026;</span><div>DLR wait above 90 seconds.</div></div>

<span class="badge">Default</span>
<span class="badge outline info">OTP</span>
<span><span class="dot ok"></span>Up</span>
<span><span class="dot warn pulse"></span>Degraded</span>
```

- Alert and badge tones: `info ok warn danger`; a badge also takes `primary`. `.badge.outline` draws a border instead of a fill.
- `.dot` is a status dot. `.pulse` makes it blink.

## Tables

```html
<div class="table-wrap" tabindex="0">
  <table class="hover striped">
    <thead><tr><th>Route</th><th class="num">TPS</th></tr></thead>
    <tbody>
      <tr><td>OA-01</td><td class="num">1,200</td></tr>
    </tbody>
  </table>
</div>
```

- Always wrap a table in `.table-wrap` with `tabindex="0"`; it scrolls sideways on narrow screens.
- Table modifiers: `.hover .striped .bordered .compact`. Add `.sticky` to `.table-wrap` for a fixed header with a 70vh height limit.
- `.num` right-aligns a number cell and equalises the digits.

## Navigation

```html
<ol class="breadcrumb">
  <li><a href="/">Gateway</a></li>
  <li aria-current="page">Routes</li>
</ol>

<div class="tabs">
  <a href="/traffic" aria-current="page">Traffic</a>
  <a href="/delivery">Delivery</a>
</div>

<ul class="pagination">
  <li><a href="?p=1">1</a></li>
  <li><a href="?p=2" aria-current="page">2</a></li>
</ul>

<details class="dropdown">
  <summary>Actions</summary>
  <ul>
    <li><a href="/dup">Duplicate</a></li>
    <li><hr></li>
    <li><button type="button" class="text-danger">Remove</button></li>
  </ul>
</details>
```

- The current item carries `aria-current="page"`. Tabs also accept `.active`.
- `.dropdown.end` opens the menu at the right edge.

## Feedback

```html
<progress value="72" max="100"></progress>
<progress class="warn" value="94" max="100"></progress>
<span class="spinner"></span>
<span data-tip="Delivery report">Hover for a tooltip</span>

<div class="toasts">
  <div class="toast ok">Route saved.</div>
</div>
```

- Put one `.toasts` container at the end of `<body>`. A script adds and removes `.toast` elements (`.toast` takes a tone).
- `data-tip="text"` on any element gives a tooltip.

## Stats, lists, text blocks

```html
<div class="grid cols-3">
  <div class="stat">
    <span class="label">Messages today</span>
    <span class="value">31,482,907</span>
    <span class="delta up">4.2% vs yesterday</span>
  </div>
  <div class="card">
    <dl class="kv"><dt>Uptime</dt><dd>41 d 6 h</dd><dt>Version</dt><dd class="mono">4.12.3</dd></dl>
  </div>
</div>

<div class="accordion">
  <details open><summary>What counts as failed?</summary><p>Any final DLR other than DELIVRD.</p></details>
  <details><summary>Who gets paged?</summary><p>The on-call engineer.</p></details>
</div>

<div class="empty">
  <span>&#xF0687;</span>
  <p><strong>No undelivered messages</strong><br>Stuck messages appear here.</p>
</div>

<article class="prose"><p>Long-form text in the system serif.</p></article>
```

- `.delta` takes `.up` (green) or `.down` (red).
- `.prose` is for long reading text; it uses a serif at a comfortable width.

## Layout

```html
<div class="grid cols-4">
  <div class="stat"><span class="label">One</span><span class="value">1</span></div>
  <div class="stat"><span class="label">Two</span><span class="value">2</span></div>
</div>

<div class="row between">
  <strong>Title</strong>
  <div class="row"><button class="sm">One</button><button class="sm">Two</button></div>
</div>

<div class="split">
  <div class="stack gap-sm"><span class="badge">a</span><span class="badge">b</span></div>
  <div class="stack gap-sm"><span class="badge">c</span><span class="badge">d</span></div>
</div>
```

- `.container`: page width with side padding. `.narrow`: 26rem, centered (forms, login).
- `.grid` fits as many columns as there is room. `.cols-2` to `.cols-6` mean "at most that many columns"; they drop to fewer by themselves and need `.grid` on the same element.
- `.stack`: a vertical flex column. `.row`: a wrapping flex row, with `.between .end .top .nowrap`. `.split`: equal columns that wrap.
- Gaps: `.gap-sm`, `.gap-lg`. `.push` moves an item to the far end of a row. `.center` centers its content in both directions.

## App shell

A top bar, a sidebar and a main area. Above 768px the sidebar sits beside the content. Below it, the sidebar is a drawer behind the menu button.

```html
<header class="topbar">
  <button class="ghost icon narrow-only" popovertarget="side" aria-label="Menu">
    <span class="burger"></span>
  </button>
  <a class="brand" href="/">Example tool</a>
  <nav class="wide-only"><ul><li><a href="/">Home</a></li></ul></nav>
</header>
<div class="shell">
  <aside class="sidebar" id="side" popover>
    <nav class="vertical">
      <ul><li><a href="#one" aria-current="page">Section one</a></li></ul>
    </nav>
  </aside>
  <main>
    <section id="one"><h2>Section one</h2></section>
  </main>
</div>
```

- `.wide-only` and `.narrow-only` show or hide any element at the 768px breakpoint.
- Inside `nav.vertical`, an `h6` is a group heading.

## Utilities

- Text color: `.muted .faint .text-ok .text-warn .text-danger .text-info .text-accent`.
- Text size: `.text-xs .text-sm .text-lg .text-xl`. Alignment: `.text-left .text-center .text-right`.
- Fonts and digits: `.mono` (code font), `.zero` (slashed zero).
- Width and wrap: `.w-full`, `.nowrap`, `.truncate` (one line with an ellipsis).
- Visibility: `.hidden` (display none), `.sr-only` (visible to screen readers only).

## Tokens

Every value is a CSS variable. Override on `:root` in project CSS, outside any layer.

```css
:root { --r: 2px; --side: 13rem; --font-sans: "Inter", system-ui, sans-serif; }
```

Main tokens: `--accent`, `--r`, `--side`, `--container`, `--h-control`, `--h-topbar`, `--font-sans`, `--font-serif`, `--font-mono`, `--dur`, `--ease`, spacing `--s-1` to `--s-7`, font sizes `--fs-xs` to `--fs-2xl`.

## Complete class list

Any class not named here is an error. Classes in the page's own `<style>` are the project's own.

- Layout: `container narrow grid cols-2 cols-3 cols-4 cols-5 cols-6 stack row split between end top nowrap gap-sm gap-lg push center shell topbar brand burger sidebar vertical wide-only narrow-only`
- Controls: `btn primary danger ok warn info ghost link icon block sm lg group field help error`
- Content: `card alert badge outline dot pulse stat label value delta up down kv accordion empty prose mono zero`
- Tables: `table-wrap sticky hover striped bordered compact num`
- Navigation: `tabs active breadcrumb pagination dropdown`
- Feedback: `spinner toasts toast`
- Utilities: `muted faint text-xs text-sm text-lg text-xl text-left text-center text-right text-ok text-warn text-danger text-info text-accent truncate w-full hidden sr-only`
- From the icons stylesheet: `icon-lg spin`

Attributes the library reacts to: `aria-current`, `aria-busy`, `aria-invalid`, `aria-selected`, `data-tip`, `popover`, `commandfor`, `command`, `role="switch"`.

## Limits

- Supported browsers: the latest stable release of Chrome, Edge, Firefox and Safari, and the release before it.
- `dir="rtl"` on `<html>` mirrors the layout.
- Do not edit `desk.css` or `desk.min.css` in a project. Override in project CSS.
