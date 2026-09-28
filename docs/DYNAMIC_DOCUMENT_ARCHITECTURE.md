# Dynamic Document System Architecture

The Caregiver Communications Platform uses a **Schema-Driven Architecture** to handle client documents. This allows for flexible, customizable forms without changing the app code for every new document type.

## 1. Core Architecture & Data Flow

### The "Schema-Driven" Concept
In a traditional app, adding a "Medical History" form would require developers to write new React screens, add database tables, and deploy a new app update. 

In this system, we store the **form definition itself** in the database (`document_templates`.`form_schema`). The frontend allows administrators to build forms dynamically (text inputs, checkboxes, dates). When the app loads, it downloads these schemas and **builds the UI on the fly**.

### Data Hierarchy
- **Categories:** Top-level folders (e.g., "Individual", "Medical Records").
- **Subcategories:** Nested folders (e.g., "Protocols", "Agreements").
- **Templates:** The empty forms living in subcategories.
- **Documents:** Filled-out instances of templates attached to a specific Client.

---

## 2. The Management Portal (Web)
**Target Users:** Admins, Directors, Site Directors (Limited)

The Portal is the "Command Center" for the organization. It runs in a browser (React) and handles high-level management.

### Key Responsibilities
1.  **Template Builder:**
    - A drag-and-drop interface to create new forms.
    - Users define fields (e.g., "Allergies" as a text list) and validation rules.
    - They set the `revision_interval_days` (e.g., 365 days) to automate compliance tracking.

2.  **Compliance Dashboard:**
    - A centralized view of **"Who needs what?"**.
    - **Expired Documents Widget:** Instantly filters thousands of records to show only the documents that are overdue *right now*.

3.  **Role-Based Access (RBAC):**
    - The Portal hides features based on login.
    - **Site Directors** logging in only see the "Client Documents" tab for *their* location. The "Templates" tab is completely hidden to prevent unauthorized editing of company-wide forms.

---

## 3. The Caregiver App (iOS)
**Target Users:** Direct Support Professionals (DSPs)

 is the "Boots on the Ground" tool. It is optimized for runtime usage by staff working directly with clients. DSPs can navigate the folder hierarchy to find "Emergency Protocols" or "Behavior Plans" in seconds. They **cannot** edit or delete documents, ensuring the integrity of the clinical record.

---

## 4. Background Processes (The "Invisible" Work)
The FastAPI Backend acts as the traffic controller and enforcer.

### A. Security Enforcement (Middleware)
- **Token Validation:** Every request checks for a valid session token.
- **Scope Checking:** When a Site Director requests `GET /clients/5/documents`, the server invisibly checks: *Is Client #5 assigned to the same Location ID as this Site Director?* If not, it returns a 403 error before even querying the database.

### B. The "Never-Overwrite" Rule (revisions)
- When a Director edits a document to update a phone number:
    1.  The Server **does not update** the existing row.
    2.  It marks the old row as `is_current = FALSE`.
    3.  It creates a **new row** with the new data, `is_current = TRUE`, and a new timestamp.
- **Why?** This creates an unalterable **Audit Trail**. We can replay exactly what the document looked like 6 months ago, which is critical for legal and state audits.

### C. Expiration Logic
- The server doesn't "run" a nightly job to find expired documents.
- Instead, it calculates it **on-demand**. When the Dashboard asks for specific stats:
    - Query: "Find the latest version of every document."
    - Calculation: `Due Date = (Last Review Date) + (Template Revision Interval)`.
    - Filter: "Return only those where Due Date < Today."
- This ensures the "Expired" badges are live-to-the-second accurate.

---

## 5. Security & RBAC Matrix in the Management Portal

| Feature | Admin / Director | Site Director | DSP |
| :--- | :---: | :---: | :---: |
| **View Documents** | ✅ | ✅ (Own Location Only) | ✅ (Own Clients Only) |
| **Create/Edit Documents** | ✅ | ✅ (Own Location Only) | ❌ |
| **Review Documents** | ✅ | ✅ (Own Location Only) | ❌ |
| **Create/Edit Templates** | ✅ | ❌ (Hidden in UI) | ❌ |
| **Archive Templates** | ✅ | ❌ | ❌ |
