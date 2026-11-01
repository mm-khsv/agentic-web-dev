# UI Copy Inventory

**Purpose** – This document lists all user‑facing text used in the Smelly Cat v1 prototype.
All copy is derived from the approved SRS and the UX specification.
Each entry is tagged with the relevant requirement ID(s) for traceability.

| Element | Copy | Requirement ID(s) |
|---------|------|-------------------|
| **Page Title – Compose** | *Compose a Polite Message* | US‑01 |
| **Page Title – Drafts** | *Saved Drafts* | US‑02 |
| **Textarea Label** | *Describe the situation* | FR‑01 |
| **Textarea Placeholder** | *e.g., “I noticed a faint odor in the shared office space…”* | FR‑01 |
| **Tone Selector – Group Label** | *Choose a tone* | FR‑02 |
| **Tone Option – Friendly** | *Friendly* | FR‑02 |
| **Tone Option – Formal** | *Formal* | FR‑02 |
| **Preview Button** | *Preview* | FR‑03 |
| **Copy Button** | *Copy* | FR‑04 |
| **Save Button** | *Save Draft* | FR‑05 |
| **Draft List – Empty State** | *No drafts saved yet.* | FR‑06 |
| **Draft List – View Button** | *View* | FR‑06 |
| **Draft Detail – Back Link** | *Back to Compose* | FR‑06 |
| **Validation – Empty Textarea** | *Please enter situation details.* | FR‑07 |
| **Success – Copy** | *Copied!* | FR‑04 |
| **Error – Clipboard Failure** | *Failed to copy. Please try again.* | FR-09 |
| **Success – Save** | *Draft saved.* | FR‑05 |
| **Error – Save Failure** | *Failed to save draft. Please try again.* | FR-09 |
| **Error – Load Failure** | *Failed to load drafts. Please try again.* | FR-09 |
| **Toast – General Success** | *Success.* | AC‑03 |
| **Toast – General Error** | *Error.* | AC‑04 |

---

### Helper Text

| Context | Helper Text | Requirement ID(s) |
|---------|-------------|-------------------|
| **Tone Selector** | *Select how formal you want the message to sound.* | FR‑02 |
| **Preview Button** | *Generate the message preview.* | FR‑03 |
| **Copy Button** | *Copy the previewed message to your clipboard.* | FR‑04 |
| **Save Button** | *Save the current draft locally.* | FR‑05 |

---

### Accessibility‑Related Text

| Element | Accessible Name | Requirement ID(s) |
|---------|-----------------|-------------------|
| **Preview Button** | *Preview – generates the message preview* | NFR‑01 |
| **Copy Button** | *Copy – copies the previewed message to clipboard* | NFR‑01 |
| **Save Button** | *Save Draft – saves the current draft locally* | NFR‑01 |
| **Draft List – View Button** | *View – opens the draft for review* | NFR‑01 |
| **Toast Notifications** | *Status message – announces success or error* | NFR‑01 |

---

### Notes

* All copy is intentionally neutral and respectful; no wording suggests that the message is sent automatically.
* The tone options (“Friendly” and “Formal”) are presented as radio buttons; the labels are the same as the option names.
* Toast messages are concise and use the same wording for all success or error cases to maintain consistency.

---
