---
name: design-ux
description: Design a coherent, accessible, responsive, and reviewable user experience using evidence-based UI/UX principles inspired by UI/UX Pro Max. Use for UX specifications, visual design systems, screen states, interaction patterns, UI copy, prototypes, and accessibility reviews.
---

# UX Design Skill

## 1. Mission and Boundaries

Produce a coherent, visually intentional, accessible, responsive, and testable UX design package from the approved Software Requirements Specification (SRS).

This Skill belongs to the existing `ui-ux-designer` agent. It does not create, delegate to, or require additional agents.

The output is a draft for human review at G2. Never approve G2 or claim human validation.

Use UI/UX Pro Max as a design-knowledge reference. Apply its relevant principles to this project rather than assuming its external search scripts, data catalogs, frameworks, or runtime integrations are installed.

Do not claim to have run an external design search, inspected a reference implementation, measured contrast, tested assistive technology, or performed usability research unless that action actually occurred.

## 2. Source of Truth and Scope Control

Before making design decisions:

1. Read the approved SRS and identify relevant user stories, functional requirements, non-functional requirements, and acceptance criteria.
2. Extract confirmed scope, explicit exclusions, user roles, constraints, assumptions, and unresolved decisions.
3. Identify the target platform and implementation constraints only from available project evidence.
4. Distinguish requirements from design recommendations and unresolved decisions.
5. Map substantive design decisions to SRS requirement IDs where available.

The approved SRS and project governance take precedence over design trends, examples, and this Skill's recommendations.

Never invent product capabilities, business rules, integrations, technology choices, performance targets, or stakeholder approvals.

For Smelly Cat v1, preserve the approved scope: compose a respectful message about unpleasant body or clothing odor, select a tone, preview and copy the message, save drafts, and view saved drafts. Do not introduce external email/SMS delivery, user accounts, cloud deployment, payments, AI generation, or a multi-user inbox.

## 3. Design Intelligence Workflow

### Step A — Understand the product

Identify:

- Product type and primary user goal.
- Primary user journey and important secondary journeys.
- User context, expected device sizes, and likely interaction constraints supported by the requirements.
- Content density, information hierarchy, and the most important action on each screen.
- Emotional context and tone appropriate to the product.
- Confirmed requirements, assumptions, exclusions, and open decisions.

Do not assume a framework or component library. Use only a stack established by the project when implementation-specific guidance is needed.

### Step B — Establish a coherent visual direction

Before specifying detailed screens, choose and explain one coherent visual direction.

Document:

- The intended visual character and why it suits the product.
- Layout strategy and content hierarchy.
- Color roles: page background, surfaces, primary action, secondary action, text, borders, focus, success, warning, and error.
- Typography roles, sizes, weights, line heights, and readable text widths.
- A consistent spacing scale, radii, borders, elevation, and focus treatment.
- Icon style and rules for consistent use.
- Responsive layout principles and the important breakpoints or layout transitions.
- Relevant visual anti-patterns to avoid.

Avoid arbitrary mixtures of design styles, excessive decoration, gratuitous gradients, inconsistent radii, random spacing, emoji used as interface icons, and generic layouts that ignore the product's purpose.

A visual choice must have a reason. Prefer clarity, hierarchy, consistency, and appropriate emotional tone over novelty for its own sake.

### Step C — Define design tokens

Create a small, reusable token system in `docs/ux/design-tokens.css`.

Include semantic CSS custom properties for:

- Colors and surface roles.
- Typography families, sizes, weights, and line heights.
- Spacing.
- Borders and radii.
- Shadows or elevation when useful.
- Focus indicators.
- Layout constraints and responsive breakpoints where appropriate.

Use the tokens consistently in the prototype. Avoid scattering unrelated hard-coded colors and spacing values throughout components.

Do not claim a contrast ratio is compliant unless it has actually been calculated and checked. Record intended contrast requirements separately from verified measurements.

Do not require an external font, icon service, CDN, or network dependency for the prototype. Prefer robust system-font fallbacks and self-contained assets unless the approved project constraints explicitly permit external resources.

### Step D — Design screens and interactions

For each screen, describe:

- Purpose and primary user task.
- Content order and visual hierarchy.
- Controls, labels, actions, and navigation.
- Default state and available alternatives.
- Input validation and error prevention.
- Empty, loading, success, failure, and recovery states when relevant.
- Keyboard interaction, focus behavior, and accessibility semantics.
- Responsive behavior at narrow, medium, and wide viewports.
- Requirement traceability.

Specify real interaction behavior rather than relying on appearance alone. Each interactive control must have a clear purpose and meaningful feedback.

### Step E — Produce and cross-check the complete bundle

Keep all seven assigned artifact paths unchanged. Generate and validate the artifacts as a coherent package, not as seven unrelated documents.

## 4. Visual Quality Principles

### Hierarchy and composition

- Give every screen a clear primary task and a recognizable primary action.
- Establish hierarchy through spacing, alignment, typography, contrast, and grouping.
- Group related information and controls; separate unrelated tasks.
- Maintain consistent alignment and a deliberate content width.
- Use whitespace intentionally, without making the interface feel empty or forcing unnecessary scrolling.
- Ensure headings, labels, controls, and supporting text remain easy to scan.
- Avoid overcrowding and competing primary actions.

### Color and contrast

- Use semantic color roles rather than arbitrary per-component colors.
- Maintain sufficient contrast for text, controls, boundaries, and focus indicators.
- Do not use color as the only means of conveying errors, success, or status.
- Make error, success, and neutral feedback visually distinguishable.
- Keep the palette restrained and consistent with the product's emotional context.
- Do not present unmeasured contrast as verified compliance.

### Typography and content

- Prefer readable body text, clear heading levels, suitable line lengths, and comfortable line height.
- Avoid tiny low-contrast text and excessive use of all caps.
- Use consistent typographic roles across screens.
- Write labels and actions in clear, concise language.
- Keep product copy respectful, non-judgmental, and free of shaming language.
- Never imply that a message was sent externally when it was only copied or saved.

### Responsive behavior

- Design for narrow screens first, then enhance the layout for wider screens.
- Use flexible widths and layout constraints instead of rigid page widths.
- Avoid horizontal overflow and clipped content.
- Let forms, buttons, text, and feedback messages adapt to available space.
- Ensure controls remain usable with touch, mouse, and keyboard.
- Consider zoom, text enlargement, and content reflow.
- Specify meaningful layout changes rather than listing arbitrary breakpoints without a reason.

### Interaction and feedback

- Every actionable control must communicate its purpose and state.
- Provide visible hover, focus, active, disabled, and feedback states where applicable.
- Never rely on hover alone to expose essential functionality.
- Keep validation messages close to the relevant field and explain how to recover.
- Prevent accidental data loss when practical within the approved scope.
- Communicate copy, save, load, and failure outcomes truthfully.
- Respect reduced-motion preferences if motion is introduced.
- Avoid animations that distract from the task or make controls harder to use.

### Forms and error prevention

- Use persistent, programmatically associated labels.
- Do not use placeholder text as the only label.
- Explain constraints before or at the point where users need them.
- Preserve valid user input when an operation fails.
- Identify errors in text and explain corrective actions.
- Keep validation behavior consistent across related fields and screens.
- Do not invent validation rules that the SRS has not established. Mark unresolved rules as open decisions.

### Accessibility

- Prefer semantic HTML elements and native controls.
- Associate labels and descriptions with their inputs.
- Ensure all core actions are keyboard accessible.
- Preserve a visible focus indicator and a logical focus order.
- Ensure focus is not hidden behind sticky elements or overlays.
- Use appropriate accessible names for controls and meaningful text alternatives for informative images.
- Announce dynamic success and error feedback appropriately when implemented.
- Ensure status is not conveyed through color alone.
- Consider text zoom, reflow, reduced motion, and assistive-technology expectations.
- Treat accessibility review status honestly: a written checklist is not evidence that testing passed.

## 5. Prototype Requirements

For `docs/ux/prototypes/smelly-cat-v1.html`:

1. Produce a complete, self-contained HTML document with embedded CSS and JavaScript.
2. Build a usable interface, not a static screenshot or decorative mockup.
3. Include two switchable visual alternatives with a meaningful difference in visual direction or composition. Both must preserve the same approved product scope and core functionality.
4. Implement the tone selector and message preview.
5. Implement copy-to-clipboard behavior with honest success and failure feedback.
6. Implement draft saving and viewing for the prototype.
7. Use `localStorage` only as explicitly labelled prototype-only persistence. Do not represent it as production SQLite persistence.
8. Include empty, success, and relevant failure states.
9. Use semantic HTML, associated labels, visible focus, responsive layout, and keyboard-operable controls.
10. Ensure buttons perform their stated actions. Avoid dead controls and decorative actions that appear functional but do nothing.
11. Do not implement external message delivery, authentication, network requests, or unapproved features.
12. Keep the prototype self-contained and usable without remote dependencies.

Prototype limitations must be visible in the relevant UX documentation. Simulated persistence and untested accessibility must never be presented as production-ready or verified.

## 6. Required Artifact Contract

Produce exactly these seven artifacts:

1. `docs/ux/ux-specification.md`
   - Purpose, source requirements, goals, design principles, information architecture, screen descriptions, flows, interaction specifications, validation and error states, accessibility, responsive behavior, traceability, assumptions, and open questions.

2. `docs/ux/user-flows.md`
   - Primary and relevant alternative flows, decisions, validation failures, recovery paths, and requirement traceability. Diagrams may be used when they improve clarity.

3. `docs/ux/screen-state-inventory.md`
   - Screen and component inventory with default, empty, validation, success, failure, and recovery states where applicable. Include keyboard and responsive behavior.

4. `docs/ux/ui-copy.md`
   - Labels, button text, helper text, validation messages, empty-state content, confirmation messages, and recovery guidance. Copy must remain respectful and must not imply external delivery.

5. `docs/ux/design-tokens.css`
   - Valid CSS containing reusable design tokens and any clearly documented foundational styling needed by the prototype.

6. `docs/ux/prototypes/smelly-cat-v1.html`
   - Self-contained, interactive HTML prototype with two switchable visual alternatives and the behaviors described above.

7. `docs/ux/accessibility-review.md`
   - A structured manual-review checklist covering semantics, labels, keyboard operation, focus, announcements, contrast measurement, zoom/reflow, error identification, reduced motion, and small screens. Mark unperformed checks `NOT TESTED`.

Do not create extra candidate, final, review, backup, or alternative artifacts outside the assigned paths unless explicitly requested.

## 7. Cross-Artifact Consistency

Before delivery, verify that:

- The same feature scope and terminology appear across all documents.
- Screen names and user-flow steps agree.
- Every important interaction has a corresponding state and UI copy where relevant.
- The prototype uses the documented design tokens.
- The two visual alternatives preserve the same product capabilities.
- Every substantive UX decision traces to a requirement, a clearly labelled recommendation, or an explicit assumption.
- Unresolved technical and product decisions remain open rather than being silently decided.
- No artifact claims testing, measurement, or human approval that did not occur.
- No excluded capability has entered the design.

## 8. Quality Checklist

### Product and requirements

- [ ] Approved requirements were reviewed.
- [ ] Scope and exclusions are preserved.
- [ ] Important user journeys and failure paths are represented.
- [ ] Requirement IDs are used consistently where available.
- [ ] Assumptions and open questions are explicit.

### Visual design

- [ ] A coherent visual direction is explained.
- [ ] Hierarchy, alignment, spacing, and typography are consistent.
- [ ] Semantic design tokens are defined and reused.
- [ ] Responsive behavior is specified and implemented.
- [ ] No arbitrary visual decoration undermines usability.
- [ ] No unsupported design research or contrast measurements are claimed.

### Interaction and accessibility

- [ ] Controls have meaningful behavior.
- [ ] Validation and recovery feedback are documented.
- [ ] Keyboard access and visible focus are considered.
- [ ] Labels, semantics, contrast, and reflow are addressed.
- [ ] Reduced motion is addressed if animation is used.
- [ ] Unperformed accessibility checks remain marked NOT TESTED.

### Deliverables and governance

- [ ] All seven required artifacts are present and mutually consistent.
- [ ] The prototype is self-contained and interactive.
- [ ] Prototype-only persistence is labelled honestly.
- [ ] No excluded feature has been introduced.
- [ ] No existing artifact was overwritten.
- [ ] The bundle is ready for human review.
- [ ] G2 remains pending until explicitly approved by a human.

## 9. Output and Approval Rules

- Write technical artifacts in professional English.
- Save only to paths assigned by the workflow under `docs/ux/`.
- Never overwrite an existing artifact.
- Do not implement production application code.
- Do not change approved requirements or silently resolve open decisions.
- Do not approve G1, G2, or any other human gate.
- Report validation failures honestly. Do not weaken a quality rule merely to force a successful run.
- Completion of UX design means a reviewable draft has been produced; it does not mean that accessibility, usability, or production readiness has been verified.
