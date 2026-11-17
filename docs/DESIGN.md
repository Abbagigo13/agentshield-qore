# Design

The website (`web/index.html`) is one self-contained file: a plain landing page and a multi-page dashboard.

## Direction
Soft **neumorphism**: a single matte surface with raised and pressed-in elements, calm and instrument-like. Verdict color
carries the meaning. No glossy cards, gradients, glassmorphism or stock security imagery.

## Visual identity
| Item | Choice |
|---|---|
| Surface | Light `#e9edf3`; dark `#20232e` (follows system setting) |
| Shadows | Raised: two offset shadows (dark and light). Pressed: the same inset |
| Accent | Purple `#6b4df0` (dark mode `#9a85ff`), orange `#f5a352` for denied/secondary |
| Verdicts | ALLOW green, ESCALATE amber, DENY red. Color is never the only signal; the word is always shown |
| Type | Geist for interface, Geist Mono for hashes, addresses, amounts. System fallbacks included |
| Icons | Simple text glyphs in the nav to stay dependency-free |

## Layout
- **Landing:** logo, headline, one paragraph, a single large **Enter** button, then Overview, Documentation and FAQ sections as plain text lists.
- **Dashboard:** fixed left sidebar on desktop; bottom tab bar on phones.
- Pages (hash routes): `overview`, `overtime`, `receipts`, `approvals`, `playground`, `policies`, `docs`.

## Interaction
- Verdict stamps land with a short scale animation.
- **Verify chain** animates row by row, recomputing each SHA-256 in the browser.
- **Tamper** edits a record without fixing its hash; verification fails at exactly that record. **Undo** restores it.
- Buttons press inward on click. Nothing animates longer than about 300 ms except the verify sweep.
- `prefers-reduced-motion` disables animation.

## Components
Raised panels, inset inputs, tile stats, receipt rows (sequence, kind, verdict, summary, copyable hash), bar chart and
donut (inline SVG), approval items with Approve and Reject, FAQ disclosure list, code blocks, responsive tables.

## States
- **Empty:** short instruction naming the next action ("Send a payment above 0.5 QOR from the Playground").
- **Error / denial:** exact rule and reason in plain language.
- **Success:** verdict stamp plus what happened ("Hybrid transaction signed (demo: not broadcast)").
- **Loading:** buttons disable while an operation runs. The page has no network loading yet.

## Mobile
Designed separately from desktop: bottom tab bar, single-column grids, receipt rows collapse to three columns, wide
tables scroll inside their own container, safe-area insets respected.

## Honesty rules for the UI
- Browser demo hashes are real SHA-256 over the gateway's canonical JSON.
- ML-DSA-87 signatures are **not** computed in the browser; the page says so.
- Sample history on "Over time" is labeled as sample data.

## Known gaps
Not yet connected to a live gateway; not audited with a screen reader; low-contrast risk inherent to neumorphism, so
body text is kept dark and verdict colors strong.
