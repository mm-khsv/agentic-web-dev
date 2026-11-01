# Software Requirements Specification: Smelly Cat v1

## 1. Purpose and Scope

### 1.1 Purpose

The purpose of the Smelly Cat v1 application is to provide a local web-based tool that assists users in drafting sensitive, polite, and non-humiliating messages regarding unpleasant body or clothing odors. The application focuses on tone management to mitigate social friction.

### 1.2 Scope

The scope of v1 is limited to a local web application that facilitates message composition, tone selection, previewing, and local persistence of drafts.

### 1.3 Exclusions

The following are explicitly out of scope for v1:

- Real-world message delivery (Email, SMS, WhatsApp, etc.).
- User authentication or account management.
- Cloud deployment or remote hosting.
- Artificial Intelligence (AI) or Large Language Model (LLM) integration.
- Multi-user support or shared inboxes.
- Payment processing or subscription models.

## 2. Stakeholders and User Classes

| ID     | Stakeholder | Description                                                                            |
| :----- | :---------- | :------------------------------------------------------------------------------------- |
| STK-01 | End User    | An individual seeking to communicate a sensitive hygiene-related observation politely. |
| STK-02 | Developer   | The individual responsible for implementing and maintaining the local application.     |

## 3. System Context and Boundaries

Smelly Cat v1 is a standalone local web application. It operates within the user's local environment (developer's computer) and interacts with a local SQLite database for data persistence. It does not interact with external APIs or networks for its core functionality.

## 4. Assumptions, Constraints, and Dependencies

### 4.1 Assumptions

- **AS-01:** The user has a web browser installed on their local machine.
- **AS-02:** The user is responsible for the manual copying and pasting of the generated text into their preferred messaging platform.

### 4.2 Constraints

- **CON-01:** The application must run locally on the developer's machine.
- **CON-02:** Data must be stored using SQLite.

### 4.3 Dependencies

The application requires a local runtime capable of serving the web interface and accessing SQLite. The specific language and web framework remain implementation choices.

- **DEP-01:** A runtime environment capable of hosting a local web server (e.g., Python, Node.js, etc.) must be available.

## 5. User Stories

| ID    | User Role | Requirement                                            | Goal/Benefit                                  |
| :---- | :-------- | :----------------------------------------------------- | :-------------------------------------------- |
| US-01 | End User  | I want to input details about the situation            | To provide context for the message.           |
| US-02 | End User  | I want to select between "Friendly" and "Formal" tones | To match the social context of the recipient. |
| US-03 | End User  | I want to preview the message before saving            | To ensure the tone is appropriate.            |
| US-04 | End User  | I want to save my drafts locally                       | To revisit or edit messages later.            |
| US-05 | End User  | I want to copy the message to my clipboard             | To easily move the text to a messaging app.   |

## 6. Functional Requirements

### 6.1 Message Composition

Message composition in v1 shall use predefined templates and deterministic text formatting. No AI model or external generation service shall be used. The user-provided situation details shall be incorporated into the selected tone's template.
| ID | Requirement | Priority |
| :--- | :--- | :--- |
| FR-01 | The system shall provide a form for text input regarding the odor/situation. | High |
| FR-02 | The system shall allow the user to select one of two tones: "Friendly" or "Formal". | High |
| FR-03 | The system shall compose a preview using a predefined template for the selected tone and the user's non-empty situation details. | High |
| FR-04 | The system shall provide a "Copy to Clipboard" button for the previewed message. | High |

### 6.2 Persistence and Management

| ID    | Requirement                                                                                                                       | Priority |
| :---- | :-------------------------------------------------------------------------------------------------------------------------------- | :------- |
| FR-05 | The system shall save composed messages to a local SQLite database as drafts.                                                     | Medium   |
| FR-06 | The system shall provide a view to list and view previously saved drafts. Editing and deleting saved drafts are excluded from v1. | Medium   |

### 6.3 Notifications and Validation

| ID    | Requirement                                                                                     | Priority |
| :---- | :---------------------------------------------------------------------------------------------- | :------- |
| FR-07 | The system shall validate that required input fields are not empty before saving or previewing. | High     |
| FR-08 | The system shall display a success notification upon successful saving or copying.              | Medium   |
| FR-09 | The system shall display an error notification if a process (e.g., saving) fails.               | Medium   |

## 7. Non-Functional Requirements

| ID     | Category    | Requirement                                                                                    |
| :----- | :---------- | :--------------------------------------------------------------------------------------------- |
| NFR-01 | Usability   | The interface shall be simple enough to require no user manual.                                |
| NFR-02 | Reliability | The system shall maintain data integrity within the SQLite database during save operations.    |
| NFR-03 | Portability | The application shall be runnable on the developer's local machine via a standard web browser. |

## 8. Data Model (Draft)

The system will utilize a SQLite database with a `drafts` table.

- **Table: `drafts`**
  - `id`: Primary Key (Integer)
  - `content`: Text (The input details)
  - `tone`: Text ("Friendly" or "Formal")
  - `composed_text`: Text (The resulting message)
  - `created_at`: Timestamp

## 9. Error Handling and Validation

| ID    | Scenario                                       | Expected Behavior                                                            |
| :---- | :--------------------------------------------- | :--------------------------------------------------------------------------- |
| EH-01 | User attempts to save/preview with empty input | System prevents action and displays a validation error message.              |
| EH-02 | Clipboard API failure                          | System displays an error notification stating "Failed to copy to clipboard." |
| EH-03 | Database write failure                         | System displays an error notification stating "Failed to save draft."        |

## 10. Privacy, Security, and Abuse Considerations

- **Privacy:** Since the application is local, data remains on the user's machine. No data is transmitted to external servers.
- **Security:** As a local tool, the primary risk is local file system access via the web server.
- **Abuse:** The tool is designed for politeness; however, there are no technical controls to prevent users from using the tool to generate malicious content.

## 11. Acceptance Criteria

| ID    | Requirement/Story           | Acceptance Criteria                                                                                                                                                                                   |
| :---- | :-------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC-01 | FR-01, FR-02, FR-03         | **Given** the user has entered text and selected a tone, **When** they click "Preview", **Then** the system displays a message in the selected tone.                                                  |
| AC-02 | FR-07 (Validation)          | Given the required situation-details field is empty or contains only whitespace, when the user clicks Preview or Save, the system displays a validation error and does not preview or save the draft. |
| AC-03 | FR-04 (Clipboard)           | **Given** a message is previewed, **When** the user clicks "Copy", **Then** the text is available in the system clipboard and a "Copied!" notification appears.                                       |
| AC-04 | FR-04 (Clipboard Failure)   | **Given** a clipboard error occurs, **When** the user clicks "Copy", **Then** an error message "Failed to copy" is displayed.                                                                         |
| AC-05 | FR-05, FR-06 (Persistence)  | Given a valid draft is saved, it appears in Saved Drafts; after the application is stopped and restarted, the same saved draft remains available.                                                     |
| AC-06 | FR-05 (Persistence Failure) | **Given** a database error occurs, **When** the user clicks "Save", **Then** an error notification "Failed to save draft" is displayed.                                                               |

## 12. Traceability Matrix (Summary)

- **Goal: Polite Communication** $\rightarrow$ US-02, FR-02, FR-03
- **Goal: Ease of Use** $\rightarrow$ US-05, FR-04, AC-03
- **Goal: Local Persistence** $\rightarrow$ FR-05, FR-06, AC-05

## 13. Assumptions and Open Questions

### 13.1 Assumptions

- **AS-01:** (See Section 4.1)

### 13.2 Open Questions

- **OQ-01 (Technical):** Which web framework/language is preferred for the local server (e.g., Flask/Python, Express/Node.js)?
- **OQ-02 (Functional):** The initial message-composition approach is resolved for v1: use predefined templates for friendly and formal tones without AI. Template wording can be reviewed during implementation.
- **OQ-03 (UI/UX):** Resolved for v1: saved drafts can be listed and viewed; editing and deleting are excluded.
