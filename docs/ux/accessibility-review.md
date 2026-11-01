# Accessibility & Responsive Review Checklist
*(Manual review – no automated audit performed)*

| # | Item | Requirement ID(s) | Status |
|---|------|-------------------|--------|
| 1 | **Semantic HTML structure** – page uses `<header>`, `<nav>`, `<main>`, `<section>`, `<form>`, `<ul>`, `<li>`, `<button>`, `<textarea>`, `<label>`, `<pre>`, `<footer>` as appropriate. | NFR‑01, NFR‑03 | ☐ NOT TESTED |
| 2 | **Form labels** – every input (`<textarea>`, tone radio group) has an associated `<label>` with a `for` attribute. | NFR‑01, AC‑02 | ☐ NOT TESTED |
| 3 | **ARIA roles** – tone radio group uses `role="radiogroup"`; each radio input has `aria-checked`; error messages use `aria-invalid`; toast notifications use `role="status"` with `aria-live="polite"`. | NFR‑01, AC‑02, AC‑03 | ☐ NOT TESTED |
| 4 | **Keyboard navigation** – all interactive elements reachable via Tab order that follows visual layout; radio buttons controllable with arrow keys; buttons activated with Enter/Space. | NFR‑01, AC‑02, AC‑03 | ☐ NOT TESTED |
| 5 | **Focus visibility** – focus ring is visible, meets WCAG contrast guidelines, and is not hidden by sticky elements or overlays. | NFR‑01, AC‑02 | ☐ NOT TESTED |
| 6 | **Screen‑reader announcements** – toast notifications are announced via `aria-live="polite"`; inline validation errors are announced through `aria-invalid`. | AC‑03, AC‑04 | ☐ NOT TESTED |
| 7 | **Color contrast** – text on background, error borders, success/failure toasts, and focus ring all meet WCAG AA contrast ratios (≥4.5:1 for text, ≥3:1 for UI components). | NFR‑01, NFR‑03 | ☐ NOT TESTED |
| 8 | **Reduced motion** – no animations that could trigger motion sensitivity; toast fade‑in/out respects `prefers-reduced-motion`. | NFR‑01 | ☐ NOT TESTED |
| 9 | **Responsive layout** – layout adapts at ≤480 px (mobile), 481–768 px (tablet), >768 px (desktop) as described in the specification. | NFR‑03 | ☐ NOT TESTED |
|10 | **Zoom & reflow** – interface remains usable when the user increases browser zoom (e.g., 200%) or changes system font size; no horizontal overflow or clipped content. | NFR‑03 | ☐ NOT TESTED |
|11 | **Error identification** – inline validation messages appear adjacent to the offending field; toast notifications for clipboard or persistence failures are visible and announced. | FR‑07, FR-09, FR-09 | ☐ NOT TESTED |
|12 | **Small‑screen usability** – on ≤480 px, all controls are full‑width, touch‑friendly, and the preview pane is scrollable if needed. | NFR‑03 | ☐ NOT TESTED |

> **Notes**
> - This checklist is intended for a manual review by a developer or accessibility specialist.
> - No automated testing or audit tools were used.
> - All items marked **NOT TESTED** remain to be verified before the product moves beyond the prototype stage.
