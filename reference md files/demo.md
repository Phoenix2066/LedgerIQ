# LedgerIQ — End-to-End Demo & Testing Guide

This guide provides a step-by-step walkthrough to test and demonstrate the **LedgerIQ AI Finance Controller** prototype end-to-end.

---

## 🚀 1. Services & Verification Status

Ensure both backend and frontend servers are running:

| Component | URL / Port | Technology | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend** | `http://localhost:3000` | Vanilla HTML5 / CSS3 / JS + Three.js | SPA Dashboard & 3D Landing Page |
| **Backend** | `http://localhost:8000` | FastAPI + SQLAlchemy + SQLite / PostgreSQL | Core Reconciler, Forecaster, Audit, LLM |

### Starting the Servers (if not already running)

**Terminal 1 (Backend):**
```bash
cd backend
source .venv/bin/activate
python run.py
```

**Terminal 2 (Frontend):**
```bash
cd frontend
python3 -m http.server 3000
```

### Quick Health Verification
Test backend health and LLM configuration:
```bash
curl -s http://localhost:8000/health
```
Expected output:
```json
{"status":"ok","service":"ai-finance-controller","db":"connected","db_error":null,"llm_configured":true,"llm_model":"kimi-k2-0711-preview"}
```

---

## 🎬 2. Step-by-Step Demo Script

Follow these steps sequentially during live presentations, jury evaluations, or video recordings:

---

### Step 1: The Landing Page Experience
1. Open your browser and navigate to **`http://localhost:3000`**.
2. **Key highlights:**
   - **Interactive 3D WebGL Particle Network**: Dynamic node connections representing multi-source financial data feeds (Bank, Gateway, ERP). Move the mouse to interact with the particle field.
   - **Sequential Title Animation**: The **LedgerIQ** brand title renders smoothly with letter-by-letter gradient animations.
   - **Dark / Light Theme Toggle**: Click the 🌓 icon in the top right to demonstrate dynamic theme adaptability (particles and UI switch palettes).
3. Click the **`⚡ Explore How It Works`** button:
   - The **"How LedgerIQ Works"** architecture modal opens immediately in front of the page.
   - Walk through the 5 autonomous stages:
     1. **Multi-Source Ingestion** (Bank Feeds, Razorpay Settlements, ERP Invoices)
     2. **3-Tier Cascade Reconciler** (Exact SQL → Subset-Sum Aggregator → RapidFuzz Composite)
     3. **AI Root-Cause Diagnostics** (LLM explaining root causes with confidence scores)
     4. **30-Day Forward Cash Forecaster** (Stress testing & liquidity runway)
     5. **Immutable SHA-256 Audit Trail** (Tamper-evident cryptographic ledger)
   - Click **"Got It"** or the close button (`✕`) to dismiss.

---

### Step 2: Enter Dashboard & Check System Health
1. Click **`Enter LedgerIQ Dashboard →`**.
2. **Key UI features to highlight:**
   - **System Health Pill** (top-right header): Shows live status (`● DB Connected | LLM Active`). Click it anytime to trigger an active ping to `/health`.
   - **Navigation Brand Logo**: Click the top-left **`⚡ LedgerIQ`** logo at any point to seamlessly route back to the 3D landing page, and click "Enter LedgerIQ Dashboard" to resume your session.

---

### Step 3: Multi-Source Data Ingestion (Synthetic Batch Generation)
1. You are on the **📊 Overview** tab.
2. In the top action bar, click **`Generate Synthetic Batch (50+ records)`**.
3. **What happens:**
   - The backend creates realistic cross-system transaction records (Bank statement rows, Razorpay settlement gateway events, and ERP invoices).
   - Pre-seeded real-world anomalies are generated (gateway fee deductions, timing delays, split payouts, and invoice discrepancies).
   - The **Batch Selector** automatically switches to the new batch ID, and the summary metric cards update with ingested volume and record counts.

---

### Step 4: 3-Tier Automated Reconciliation Cascade
1. Click the **`⚡ Reconciliation`** tab in the top header.
2. **Highlight the Visual Cascade Stepper:**
   - **Tier 1 (Exact SQL Match):** Matches exact reference numbers, amounts, and dates (Confidence: 1.00).
   - **Tier 2 (Subset-Sum Aggregator):** Matches 1 lump-sum deposit against $N$ unpaid invoices minus gateway fees (Confidence: 0.92).
   - **Tier 3 (RapidFuzz Composite):** Uses fuzzy semantic matching across dates, customer names, and invoice references (Confidence $\ge$ 0.75).
3. Click the primary button **`Run 3-Tier Reconciliation Cascade`**.
4. **Inspect the results:**
   - The KPI summary updates with **Match Rate (%)**, total matched amount, and flagged exceptions.
   - Filter the matched table by **All**, **Tier 1**, **Tier 2**, or **Tier 3** to demonstrate how each tier catches different transaction patterns.

---

### Step 5: AI Root-Cause Diagnostics & Human-in-the-Loop Resolution
1. Click the **`🚨 Exceptions`** tab.
2. Review the table of flagged anomalies and discrepancies.
3. Click **`Run AI Root-Cause Diagnostics`** (or click **"Diagnose"** on any individual exception row).
4. **Demonstrate the AI output:**
   - The LLM analyzes the raw transaction JSON payloads across the bank, gateway, and ERP.
   - It outputs:
     - **Confidence Score**
     - **Plain-English Root Cause Explanation** (e.g., *"Razorpay 2.0% gateway MDR fee deducted prior to bank settlement"* or *"Timing delay across weekend settlement cutoff"*).
     - **Recommended Action** (e.g., *"Auto-post ₹120 fee variance to 5010-Payment Gateway Fees"*).
5. Click **`Take Action`** on an exception:
   - Select **Accept Resolution** or **Reject / Manual Adjust**, add an optional audit note, and submit.
   - The exception status transitions to **Resolved**.

---

### Step 6: 30-Day Cash Forecaster & What-If Stress Simulator
1. Click the **`📈 Forecast & Simulator`** tab.
2. Point out the **30-Day Baseline Runway Chart** (showing opening balance, projected inflows, recurring expenses, and liquidity burn).
3. Under the **"What-If Stress Simulator"** panel:
   - Adjust the scenario controls:
     - **Gateway Settlement Delay**: e.g., set to `+5 Days`
     - **Refund Surge Spike**: e.g., set to `+20%`
     - **Expense Acceleration**: e.g., set to `+15%`
4. Click **`Run Stress Simulation`**.
5. **Notice the real-time simulation:**
   - The chart overlays the dashed **Simulated Stress Curve** against the solid baseline.
   - The KPI metrics update dynamically with the new lowest cash point, runway days remaining, and liquidity risk status.

---

### Step 7: Cryptographic SHA-256 Audit Trail
1. Click the **`🛡️ Audit Trail`** tab.
2. Every lifecycle event (batch generation, reconciliation match, LLM diagnostic run, and human resolution) is recorded chronologically.
3. Point out the **Cryptographic Chaining**:
   - Each event row displays its `event_hash` and `prev_hash`.
   - Click any event row to open the **Hash Inspector Modal** verifying the SHA-256 signature and state diff payload.
4. Click **`Export Audit Trail`** to download a CSV or JSON report for compliance auditors.

---

### Step 8: LedgerIQ AI Copilot
1. Click the **`🤖 Copilot`** button in the header or the bottom-right floating badge.
2. Ask natural language financial questions:
   - *"What is our reconciliation match rate for this batch?"*
   - *"Explain the largest exception found."*
   - *"What is our projected cash runway under current conditions?"*
3. The Copilot answers with contextually grounded data from the active batch and backend controller.

---

## 💡 3. Quick Tips for Demo Delivery
- **Start Fresh Anytime:** Generate a new synthetic batch using the **"Generate Synthetic Batch"** button. Each batch is completely isolated with its own unique batch ID.
- **Switching Themes:** Use the theme toggle button in the header during the forecast or reconciliation view to highlight that all charts and visualizers are fully reactive to dark/light modes.
- **Returning to Landing Page:** Click the **`⚡ LedgerIQ`** brand logo in the top-left corner at any time to return to the 3D particle hero view.
