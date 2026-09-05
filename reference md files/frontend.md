Design a complete modern fintech/AI frontend for this project called **LedgerIQ — AI Finance Controller**.

Tagline:

**Reconcile. Resolve. Forecast.**

The application should look like a polished enterprise finance-operations product, with a clean premium UI, responsive layout, professional data visualizations, subtle animations, and both **light and dark themes**.

Do not invent additional features or pages. The frontend should follow this exact structure:

## 1. Landing Page

Create a visually impressive landing page for LedgerIQ.

Include:

* Animated **LedgerIQ** title, with letters appearing sequentially using a fade + upward motion animation.
* Tagline: **Reconcile. Resolve. Forecast.**
* Short supporting description.
* `Enter LedgerIQ` primary button.
* `Explore How It Works` secondary button.
* Light/dark `Theme Toggle`.

The background must contain a subtle **3D WebGL/Three.js visualization** directly inside the HTML using JavaScript. Create a finance/AI-inspired animated network of connected nodes/particles rather than a simple cube. Keep it subtle so the text remains readable.

`Enter LedgerIQ` should take the user to the Overview dashboard.

`Explore How It Works` should reveal a short explanation of:

**Ingest → Reconcile → Resolve → Forecast → Audit**

---

# 2. Main Application

Use a persistent header containing:

* LedgerIQ logo/name
* `Overview`
* `Reconciliation`
* `Exceptions`
* `Forecast`
* `Audit`
* `Active Batch Selector`
* `Refresh System Health`
* `Open AI Copilot`
* `Theme Toggle`

Use SPA-style navigation so these sections switch without a full page reload.

---

# 3. Overview Dashboard

Create an executive dashboard showing:

* Total Records
* Matched Records
* Match Rate
* Exceptions
* High Risk
* Resolved

Also include:

### Reconciliation Summary

Show Tier 1, Tier 2 and Tier 3 matching results.

### Risk Summary

Show HIGH / MEDIUM / LOW exception counts.

### Cash Health

Show:

* Current Cash
* 30-Day Projected Cash
* Days to Zero
* Liquidity Health

### Recent Activity

Show recent reconciliation, exception, AI, forecast and audit events.

Include:

`Generate & Ingest Synthetic Batch`

`View Cash Forecast`

---

# 4. Reconciliation Page

Create a dedicated **Reconciliation Center**.

Include:

### Batch Controls

`Generate & Ingest Synthetic Batch`

`Run Reconciliation Cascade`

`Refresh Summary Metrics`

### Source Cards

* Bank Feeds
* Razorpay Gateway
* ERP Invoices

### Source Filters

`All`

`Bank Feeds`

`Razorpay Gateway`

`ERP Invoices`

### Records Table

Include:

* Entity
* Source
* Reference
* Amount
* Date
* Status
* Action

Include:

`Search Records`

and per-record:

`View Raw JSON / Metadata`

Clicking this opens a JSON/metadata modal.

### Reconciliation Cascade

Visually display:

**Tier 1 — Exact Match → Tier 2 — Subset-Sum Match → Tier 3 — Fuzzy Match**

Each tier should have an informational tooltip/popover.

---

# 5. Exceptions Page

Create an **Exception Workbench**.

Show summary counts for:

`All Exceptions`

`HIGH Risk`

`MEDIUM Risk`

`LOW Risk`

Include:

`Diagnose All with AI`

Create an exception table containing:

* Exception ID
* Entity
* Amount
* Risk
* Issue
* AI Diagnosis
* Recommended Action
* Status
* Actions

Each exception should provide:

`Preview Journal Entry`

`Approve & Synthesize Rule`

`Reject`

Clicking an exception should open a detailed drawer/modal containing:

* Exception details
* Risk
* AI diagnosis
* Recommended action
* Confidence
* Draft Journal Entry

Include pagination:

`Previous`

`Next`

`Page Size`

---

# 6. Forecast Page

Create a **30-Day Cash Forecast & What-If Simulator**.

Show KPI cards:

* Current Cash
* 30-Day Projected Cash
* Minimum Projected Cash
* Days to Zero
* Liquidity Health

Include:

`Compute Baseline 30-Day Runway`

Display a large 30-day cash runway chart.

Create a **What-If Stress Simulator** containing:

### `Receivables Collection Delay`

Slider: 0–30 days

### `Customer Default / Loss Rate`

Slider: 0–50%

### `Gateway Fee Surge`

Slider: 0–5%

Buttons:

`Run Stress Simulation`

`Reset Simulation Parameters`

Also include:

`Forecast Start Date`

After simulation, visually compare:

**Baseline Runway vs Stress Runway**

and show:

* Net Cash Variance
* Minimum Cash
* Days to Zero
* Scenario Insight

---

# 7. Audit Page

Create an **Immutable Audit Trail** page.

Show:

* Total Events
* System Actions
* Human Actions
* AI Actions

Include:

`Load Audit Trail`

and an `Audit Action Type` dropdown with:

* All
* AUTO_MATCH
* EXCEPTION_FLAGGED
* HUMAN_APPROVED
* RULE_SYNTHESIZED
* FORECAST_GENERATED
* SIMULATION_RUN

Display a chronological audit timeline/table containing:

* Timestamp
* Event Type
* Actor
* Confidence
* Reasoning
* State Change

Each event should have:

`View State Diff / Reasoning`

which opens a detail drawer/modal showing **Before → Action → After**.

Include:

`Export Audit Package (JSON)`

`Export Audit Package (CSV)`

---

# 8. Persistent AI Finance Copilot

Create a right-side drawer accessible from every application page.

Button:

`Open AI Copilot`

Drawer title:

**LedgerIQ Copilot**

Subtitle:

**Your AI Finance Controller**

Input:

`Ask about this batch...`

Button:

`Send Message`

Quick prompt chips:

`Show Top Fee Discrepancies`

`Why Did ACME Tech Fail?`

`What Is Our Day 15 Cash Balance?`

`List All HIGH Risk Items`

Button:

`Clear Chat History`

Close control:

`Close AI Copilot`

The Copilot should visually indicate that it is operating on the currently selected Active Batch.

---

# 9. Interaction Requirements

Use clear, identifiable HTML IDs/classes for every interactive element so the generated code can later be connected to JavaScript event listeners.

The important events are:

* `DOMContentLoaded` — initialize application and health status.
* `click` — buttons, navigation, filters, modals, actions.
* `change` — batch selector, dropdowns, sliders/date input.
* `input` — search field and sliders.
* `keydown` — Enter key in Copilot.
* `mouseenter` — optional methodology tooltips.

Do not implement fake backend logic.

The UI should only be designed with clear placeholders/state containers for backend data.

---

# 10. Backend Wiring Compatibility

The eventual frontend will be connected to these existing endpoints, so design the UI around them without changing their names:

* `GET /health`
* `POST /api/batch/generate-synthetic`
* `GET /api/batch/{batch_id}/records`
* `POST /api/reconciliation/run/{batch_id}`
* `GET /api/reconciliation/summary/{batch_id}`
* `GET /api/reconciliation/exceptions/{batch_id}`
* `POST /api/exceptions/diagnose/{batch_id}`
* `POST /api/exceptions/{exception_id}/action`
* `GET /api/forecast/runway/{batch_id}`
* `POST /api/forecast/simulate`
* `GET /api/audit/trail/{batch_id}`
* `GET /api/audit/export/{batch_id}`
* `POST /api/copilot/chat`

Google Stitch is being used primarily for **UI design**. Do not invent new APIs or backend functionality.

The final design should communicate the complete LedgerIQ workflow:

**Ingest → Reconcile → Detect Exceptions → AI Diagnose → Human Resolve → Forecast → Audit**

Make it look like a real production-grade AI finance controller rather than a generic student dashboard.
