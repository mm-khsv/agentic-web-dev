## Purpose and Source Requirements
The Smelly Cat v1 application is a **local web‑based tool** that assists users in drafting polite, non‑humiliating messages about unpleasant body or clothing odors.
The design specification below is derived directly from the approved SRS (see the “Approved Source Requirements” document).
All requirement IDs referenced in this document (US‑xx, FR‑xx, NFR‑xx, AC‑xx, AS‑xx, CON‑xx, DEP‑xx, EH‑xx, STK‑xx) are taken verbatim from that SRS and are used for traceability.

---

## UX Goals
| Goal | Rationale | Related Requirement IDs |
|------|-----------|--------------------------|
| **Simplicity** | Users should be able to compose, preview, copy, and save a draft with minimal clicks and no learning curve. | NFR‑01, US‑01, US‑02, US‑03, US‑04, US‑05 |
| **Clarity of Tone** | The tone selector must be obvious and the resulting message preview must reflect the chosen tone. | FR‑02, FR‑03 |
| **Immediate Feedback** | Validation, success, and error notifications should appear promptly and be accessible. | FR‑07, FR‑08, FR‑09, AC‑02, AC‑03, AC‑04, AC‑06 |
| **Local Persistence** | Drafts must survive application restarts and be viewable in a dedicated list. | FR‑05, FR‑06, AC‑05 |
| **Accessibility** | All interactive elements must be keyboard‑navigable, labelled, and provide visible focus. | NFR‑01, NFR‑03, AC‑02, AC‑03, AC‑04, AC‑05 |

---

## Information Architecture
The application consists of two primary top‑level sections:

1. **Compose** – the default landing page where users enter situation details, choose a tone, preview, copy, and save.
2. **Drafts** – a list view of all locally saved drafts; selecting a draft shows its content and tone.

Navigation is linear:
- From **Compose** → **Drafts** via a top‑bar link.
- From **Drafts** → **Compose** via the same link.
No editing or deletion is available, in line with the scope.

---

## Screen Inventory
| Screen | Purpose | Primary Task | Key Controls | Notes |
|--------|---------|--------------|--------------|-------|
| **Compose Screen** | Compose a new message | Enter details, choose tone, preview, copy, save | Textarea, tone radio buttons, “Preview”, “Copy”, “Save” buttons, preview pane | Validation errors shown inline; success/error toasts appear at top. |
| **Drafts List Screen** | View saved drafts | Browse list, select a draft to view | List of draft titles, “View” button per row, back link to Compose | Empty state message when no drafts exist. |
| **Draft Detail Screen** | Inspect a saved draft | Read composed text, tone, created date | Read‑only textarea or preformatted block, back link | No copy or save actions; copy is available via the preview pane on Compose. |

---

## User Flows

### 1. Compose → Preview → Copy → Save
1. User lands on **Compose**.
2. Enters non‑empty situation details in the textarea.
3. Selects a tone (default “Friendly”).
4. Clicks **Preview**.
5. System validates input; if valid, renders the composed message in the preview pane.
6. User may click **Copy** to copy the previewed text; a toast “Copied!” appears.
7. User may click **Save** to persist the draft; a toast “Draft saved” appears.
8. User can navigate to **Drafts** to view the new entry.

### 2. View Drafts
1. User clicks **Drafts** link.
2. **Drafts List** shows all saved drafts.
3. Clicking **View** on a row opens **Draft Detail** showing the composed text and tone.
4. User can return to **Compose** via the top‑bar link.

### 3. Validation Failure
- If the textarea is empty or whitespace only, clicking **Preview** or **Save** shows an inline error “Please enter situation details.” and prevents further action.

### 4. Clipboard Failure
- If the Clipboard API rejects the copy request, a toast “Failed to copy” is shown.

### 5. Persistence Failure
- If the database write fails, a toast “Failed to save draft” is shown.

---

## Interaction Specifications

| Element | Interaction | State | Accessibility |
|---------|-------------|-------|---------------|
| **Textarea** | Focus, type, blur | Normal, focus, error (red border) | `label` element, `aria-invalid` when error |
| **Tone Radio Buttons** | Click or keyboard space/enter | Selected, focus | `role="radiogroup"`, each `input` has `aria-checked` |
| **Preview Button** | Click or Enter | Disabled when input empty | `aria-disabled` when disabled |
| **Copy Button** | Click or Enter | Disabled until preview exists | `aria-disabled` when disabled |
| **Save Button** | Click or Enter | Disabled until preview exists | `aria-disabled` when disabled |
| **Draft List Items** | Click | Highlighted row | `role="button"` on “View” link |
| **Toast Notifications** | Auto‑dismiss after 3 s | Success (green), Error (red) | `role="status"` with `aria-live="polite"` |

All buttons are native `<button>` elements to preserve keyboard operability. Focus styles are visible and meet WCAG contrast guidelines (to be verified in the accessibility review).

---

## Validation and Error States
| Condition | UI Feedback | Toast | Requirement ID |
|-----------|-------------|-------|----------------|
| Empty or whitespace textarea | Inline error message below textarea; red border | None | FR‑07, AC‑02 |
| Clipboard API failure | Toast “Failed to copy” | Yes | FR-09, AC‑04 |
| Database write failure | Toast “Failed to save draft” | Yes | FR-09, AC‑06 |
| Successful copy | Toast “Copied!” | Yes | FR‑04, AC‑03 |
| Successful save | Toast “Draft saved” | Yes | FR‑05, AC‑05 |

The preview pane is hidden until a successful preview is generated; it then displays the composed message in a read‑only `<pre>` block.

---

## Accessibility
- **Semantic HTML**: `<form>`, `<label>`, `<textarea>`, `<button>`, `<nav>`, `<ul>`, `<li>`, `<section>`.
- **Labels**: Each input has an associated `<label>` with `for` attribute.
- **ARIA**: `role="radiogroup"`, `aria-checked`, `aria-invalid`, `role="status"` for toasts.
- **Keyboard**: All interactive elements reachable via Tab; radio buttons controllable with arrow keys; buttons via Enter/Space.
- **Focus**: Visible focus ring on all controls; focus order follows visual layout.
- **Color Contrast**: Text and background colors meet WCAG AA (to be verified in the accessibility review).
- **Reduced Motion**: No animations that could trigger motion sensitivity; toasts fade in/out via CSS transitions respecting `prefers-reduced-motion`.
- **Screen Reader**: Toasts announced via `aria-live="polite"`; validation errors announced via `aria-invalid`.

---

## Responsive Behavior
| Breakpoint | Layout | Notes |
|------------|--------|-------|
| **≤ 480 px** (mobile) | Single‑column stack: textarea, tone selector, buttons, preview pane below. | Buttons full width. |
| **481–768 px** (tablet) | Two‑column: left column for form, right column for preview. | Buttons remain full width. |
| **> 768 px** (desktop) | Two‑column with larger preview pane; navigation bar at top. | Buttons inline. |

The design uses fluid widths (`max-width: 600px` for the form area) and `rem` units for spacing to support text scaling.

---

## Requirements Traceability

| UX Decision | SRS Requirement(s) |
|-------------|---------------------|
| Compose screen with situation details, tone selector, and preview | FR-01, FR-02, FR-03, AC-01 |
| Copy previewed message to clipboard | FR-04, AC-03 |
| Save a composed draft | FR-05 |
| Drafts list view | FR-06 |
| Validation of non-empty situation details | FR-07, AC-02 |
| Success notification after saving or copying | FR-08 |
| Error notification when saving or another process fails | FR-09, AC-04, AC-06 |
| Clipboard failure handling | AC-04 |
| SQLite data integrity during save operations | NFR-02 |
| Usability and accessibility features | NFR-01, AC-02, AC-03, AC-04, AC-05 |
| Local browser portability and responsive layout | NFR-03 |


## Assumptions and Open Questions
| ID | Assumption / Question | Status |
|----|-----------------------|--------|
| **AS‑01** | User has a modern web browser that supports the Clipboard API and localStorage. | Assumed |
| **AS‑02** | User will manually copy the message to their preferred messaging platform. | Assumed |
| **CON‑01** | Application runs locally on the developer’s machine. | Assumed |
| **CON‑02** | Data stored in SQLite. | Assumed |
| **DEP‑01** | A local web server (e.g., Flask, Express) will host the app. | Assumed |
| **OQ‑01** | Which web framework/language will be used for the local server? | Unresolved |
| **OQ‑02** | Exact wording of the friendly and formal templates. | Unresolved |
| **OQ‑03** | Whether the prototype will use `localStorage` or SQLite for persistence. | Unresolved (prototype uses `localStorage` only, production will use SQLite) |

All open questions are documented and must be resolved before implementation proceeds beyond the prototype stage.
