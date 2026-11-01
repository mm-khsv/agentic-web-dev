# Screen & State Inventory

## 1. Compose Screen

| State | Purpose | Content | Controls | Actions | Navigation | Validation | Empty / Loading / Success / Failure | Keyboard Interaction | Responsive Behavior | Traceability |
|-------|---------|---------|----------|---------|------------|------------|--------------------------------------|-----------------------|---------------------|--------------|
| **Default** | User begins composing a new message. | • `<textarea>` for situation details (placeholder: “Describe the situation…”) <br>• Tone selector (radio group: Friendly, Formal) <br>• **Preview** button <br>• **Copy** button (disabled) <br>• **Save** button (disabled) <br>• Preview pane (hidden) | • Textarea <br>• Radio inputs <br>• Buttons (Preview, Copy, Save) | • Type text <br>• Select tone <br>• Click Preview / Copy / Save | • Top‑bar link to **Drafts** | • None (no validation yet) | • No preview pane displayed <br>• Copy & Save disabled until preview exists | • Tab to textarea, radio group, buttons <br>• Arrow keys to change tone <br>• Enter/Space to activate buttons | • ≤480 px: single‑column stack (textarea → tone → buttons → preview) <br>• 481–768 px: two‑column (form left, preview right) <br>• >768 px: two‑column with wider preview | FR‑01, FR‑02, FR‑03, FR‑04, FR‑05, NFR‑01, NFR‑03 |
| **Preview Generated** | Successful preview of composed message. | • Same form elements <br>• Preview pane visible with `<pre>` containing the generated message | • Copy button (enabled) <br>• Save button (enabled) | • Click Copy → clipboard <br>• Click Save → persist draft | • Top‑bar link to **Drafts** | • None | • Preview pane shows message <br>• Copy & Save enabled | • Same as Default | • Same as Default | FR‑03, FR‑04, FR‑05, NFR‑01, NFR‑03 |
| **Validation Error** | User attempts to preview or save with empty/whitespace textarea. | • Textarea with red border <br>• Inline error message “Please enter situation details.” <br>• Preview pane hidden | • Preview button (disabled) <br>• Copy & Save remain disabled | • Click Preview/Save → error shown | • Top‑bar link to **Drafts** | • Textarea `aria-invalid="true"` | • Error message displayed inline <br>• No preview pane | • Tab to textarea <br>• Enter/Space on Preview/Save does nothing | • Same layout as Default | FR‑07, FR-07, AC‑02 |
| **Copy Success** | User clicks **Copy** and clipboard succeeds. | • Toast notification “Copied!” at top (auto‑dismiss after 3 s) | • None | • Toast auto‑dismiss | • Top‑bar link to **Drafts** | • None | • Toast appears, disappears | • Focus remains on Copy button | • Same layout | FR‑04, AC‑03 |
| **Copy Failure** | Clipboard API rejects copy. | • Toast notification “Failed to copy” | • None | • Toast auto‑dismiss | • Top‑bar link to **Drafts** | • None | • Toast appears, disappears | • Focus remains on Copy button | • Same layout | FR-09, AC‑04 |
| **Save Success** | Draft persisted successfully. | • Toast notification “Draft saved” | • None | • Toast auto‑dismiss | • Top‑bar link to **Drafts** | • None | • Toast appears, disappears | • Focus remains on Save button | • Same layout | FR‑05, AC‑05 |
| **Save Failure** | Persistence fails (e.g., SQLite write error). | • Toast notification “Failed to save draft” | • None | • Toast auto‑dismiss | • Top‑bar link to **Drafts** | • None | • Toast appears, disappears | • Focus remains on Save button | • Same layout | FR-09, AC‑06 |

---

## 2. Drafts List Screen

| State | Purpose | Content | Controls | Actions | Navigation | Validation | Empty / Loading / Success / Failure | Keyboard Interaction | Responsive Behavior | Traceability |
|-------|---------|---------|----------|---------|------------|------------|--------------------------------------|-----------------------|---------------------|--------------|
| **Default (Non‑empty)** | Show list of saved drafts. | • `<ul>` of draft items: each item shows title (first 30 chars of message), tone badge, created‑date <br>• **View** button per row <br>• Back link to **Compose** | • View buttons <br>• Back link | • Click View → **Draft Detail** <br>• Click Back → **Compose** | • Top‑bar link to **Compose** | • None | • List displayed <br>• No errors | • Tab to list items, View buttons, Back link | • ≤480 px: list items stack vertically <br>• 481–768 px: two‑column layout (list left, preview right) <br>• >768 px: same as 481–768 px but wider | FR‑06, NFR‑01, NFR‑03 |
| **Empty** | No drafts saved yet. | • Message “No drafts yet. Start composing a message.” <br>• Back link to **Compose** | • Back link | • Click Back → **Compose** | • Top‑bar link to **Compose** | • None | • Empty state message displayed | • Tab to Back link | • Same layout as Default | FR‑06, NFR‑01, NFR‑03 |

---

## 3. Draft Detail Screen

| State | Purpose | Content | Controls | Actions | Navigation | Validation | Empty / Loading / Success / Failure | Keyboard Interaction | Responsive Behavior | Traceability |
|-------|---------|---------|----------|---------|------------|------------|--------------------------------------|-----------------------|---------------------|--------------|
| **Default** | View a single draft’s details. | • Read‑only `<pre>` with full message <br>• Tone badge <br>• Created‑date <br>• Back link to **Drafts** | • Back link | • Click Back → **Drafts List** | • Top‑bar link to **Compose** | • None | • Draft content displayed | • Tab to Back link | • ≤480 px: single‑column <br>• 481–768 px: two‑column (content left, meta right) <br>• >768 px: same as 481–768 px | FR‑06, NFR‑01, NFR‑03 |

---

### Notes on State Transitions

- **Compose → Preview**: Triggers validation; if textarea is non‑empty, preview pane becomes visible and Copy/Save buttons enable.
- **Preview → Copy**: Calls Clipboard API; success/failure handled via toast.
- **Preview → Save**: Persists draft; success/failure handled via toast.
- **Drafts List → Draft Detail**: Loads selected draft; no validation required.
- **All screens**: Top‑bar navigation link toggles between **Compose** and **Drafts**; the current screen is highlighted.

### Accessibility & Keyboard Interaction Summary

- All form controls are native `<input>`, `<textarea>`, `<button>` elements.
- Radio group uses `role="radiogroup"` and `aria-checked` on each input.
- Validation errors set `aria-invalid="true"` on textarea; error message is associated via `aria-describedby`.
- Toast notifications use `role="status"` with `aria-live="polite"` to announce success/failure.
- Focus styles are defined in the design‑tokens and meet WCAG AA contrast (to be verified in the accessibility review).
- Keyboard navigation follows visual order: textarea → tone radio group → Preview → Copy → Save → Back link / Drafts link.

### Responsive Behavior Summary

- Breakpoints: ≤480 px (mobile), 481–768 px (tablet), >768 px (desktop).
- Layout shifts from single‑column to two‑column; buttons remain full‑width on mobile for touch friendliness.
- Textarea and preview pane widths are fluid (`max-width: 100%`) to accommodate text scaling.
- Toasts appear at the top of the viewport and are fully visible on all breakpoints.

---
