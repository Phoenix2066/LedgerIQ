The architecture of this backend relies on a decoupled, pipeline-based system: FastAPI orchestrates the workflows, Neon PostgreSQL handles persistent relational storage and trigram searches (`pg_trgm`), Python with RapidFuzz handles fuzzy/subset-sum matching, and local Ollama (`phi4-mini`/`llama3.2`) paired with cloud LLMs (`kimi-k2.6:cloud`) perform fast extraction and deep reasoning.

---

## Phase 1: Database Schema & Data Ingestion Pipeline

### 1. Database Setup (Neon PostgreSQL)

Enable `pg_trgm` for native DB-level fuzzy text searching alongside relational integrity:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Primary Batch Runs
CREATE TABLE reconciliation_batches (
    batch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    total_records INT NOT NULL,
    matched_count INT DEFAULT 0,
    exception_count INT DEFAULT 0,
    match_rate NUMERIC(5,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ingested Financial Records (Bank Logs, Gateways, Invoices)
CREATE TABLE financial_records (
    record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID REFERENCES reconciliation_batches(batch_id),
    source_type VARCHAR(20) NOT NULL, -- 'BANK', 'GATEWAY', 'INVOICE'
    raw_entity_name TEXT NOT NULL,
    normalized_entity_name TEXT,
    amount NUMERIC(12,2) NOT NULL,
    reference_code VARCHAR(100),
    transaction_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'UNMATCHED' -- 'MATCHED', 'EXCEPTION', 'RESOLVED'
);

-- Matched Pairs & Diagnostic Audit Logs
CREATE TABLE record_matches (
    match_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID REFERENCES reconciliation_batches(batch_id),
    record_a_id UUID REFERENCES financial_records(record_id),
    record_b_id UUID REFERENCES financial_records(record_id),
    confidence_score NUMERIC(3,2) NOT NULL,
    match_type VARCHAR(30) NOT NULL, -- 'EXACT', 'FUZZY', 'ONE_TO_MANY'
    reasoning_trace TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Exception Queue & Human-in-the-Loop Actions
CREATE TABLE exceptions (
    exception_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID REFERENCES reconciliation_batches(batch_id),
    record_id UUID REFERENCES financial_records(record_id),
    risk_score VARCHAR(10) NOT NULL, -- 'HIGH', 'MEDIUM', 'LOW'
    ai_diagnosis TEXT,
    recommended_action TEXT,
    drafted_journal_entry JSONB,
    status VARCHAR(20) DEFAULT 'PENDING', -- 'PENDING', 'APPROVED', 'REJECTED'
    resolved_by VARCHAR(50),
    resolved_at TIMESTAMP
);

```

### 2. Ingestion & Local LLM Data Normalizer (`phi4-mini` / `llama3.2`)

* Create a synthetic generator outputting 50+ record triplets (Bank feeds, Razorpay settlement logs, ERP invoices) with timing lags, missing reference IDs, and 2% gateway fee breaks.
* Route un-normalized merchant names through Ollama (`phi4-mini`) using structured JSON output to extract clean ticker names (e.g., `"RZP*ACME-TECH-BLR"` $\rightarrow$ `"Acme Tech"`).

---

## Phase 2: Hybrid Reconciliation Engine & Risk Matrix

### 1. Deterministic & Fuzzy Matching Cascade

The reconciliation engine executes a 3-tier cascade:

```text
Incoming Batch Records
         │
         ├──► Tier 1: Exact SQL Match (Ref Code + Amount + Date ±1 day)
         │       └─► Match Confidence: 1.00
         │
         ├──► Tier 2: Subset-Sum Aggregator (One-to-Many Payouts)
         │       └─► Matches 1 Lump Deposit to N Invoices - 2% Gateway Fee
         │
         └──► Tier 3: RapidFuzz Semantic Match (Token Set Ratio)
                 └─► Matches entity strings with score > 85/100

```

### 2. Multi-Attribute Confidence Scoring Formula

Calculate match confidence ($C$) dynamically:

$$C = (W_{amount} \cdot S_{amount}) + (W_{ref} \cdot S_{ref}) + (W_{name} \cdot S_{name}) + (W_{date} \cdot S_{date})$$

* $W_{amount} = 0.40$, $W_{ref} = 0.30$, $W_{name} = 0.20$, $W_{date} = 0.10$
* $S_{name}$ is derived directly from `rapidfuzz.fuzz.token_set_ratio(name1, name2) / 100.0`.

### 3. Financial Risk Triage Module

Flag unmatched records into an exception pool and assign risk:

* **High Risk:** Amount $> \text{₹25,000}$ OR aging $> 7 \text{ days}$.
* **Medium Risk:** Amount between $\text{₹5,000}$ and $\text{₹25,000}$ OR fee discrepancies $> 2\%$.
* **Low Risk:** Rounding discrepancies $< \text{₹100}$.

---

## Phase 3: Agentic Reasoning & Copilot Engine (`kimi-k2.6:cloud`)

### 1. Root-Cause Diagnostic Agent

For every record tagged as an `EXCEPTION`, invoke `kimi-k2.6:cloud` to construct an explicit audit trace and draft a accounting adjustment:

```python
# Agent Prompt Contract
SYSTEM_PROMPT = """You are a Lead Financial Controller AI. 
Analyze the unmatched transaction pair and determine the root cause.
Return a valid JSON object with:
1. diagnosis: Clear 1-2 sentence explanation of why the match failed.
2. recommended_action: Short actionable resolution name.
3. drafted_journal_entry: { debit_account, credit_account, amount }
"""

```

### 2. Conversational Finance Copilot Endpoint

Implement a `/api/copilot/chat` route using stream-processing over the full batch context:

* Loads current batch state, match rates, high-risk exception queues, and cash forecasts into system memory.
* Answers natural language queries (e.g., *"Which vendor caused the largest fee discrepancy in this batch?"*).

### 3. Adaptive Rule Synthesis Module

When a human controller approves an exception in the DB:

1. Extract pattern (e.g., `"Vendor prefix 'PAY-' map to 'Accounts Payable'"`).
2. Save pattern into a `dynamic_rules` PostgreSQL table.
3. Automatically execute the synthesized rule on incoming batches prior to Tier 1 matching.

---

## Phase 4: Cash Forecasting, What-If Simulator & Audit Engine

### 1. Dynamic Cash Runway Engine

Compute forward cash runway based on reconciled vs. flagged exception data:

$$\text{Projected Cash} = \text{Current Bank Balance} + \sum (\text{Matched Inflows}) + \sum (\text{Low-Risk Unmatched Receivables} \times 0.85)$$

### 2. What-If Scenario Simulator

API route `/api/forecast/simulate` takes user inputs:

* `delay_days` (integer): Shifts uncollected receivable dates forward.
* `default_rate` (float): Reduces total expected inflow volume.
* Returns updated forward cash plot data over a 30-day projection.

### 3. Tamper-Proof Audit Logger

Every manual override, AI match, or resolution triggers an append-only insert to `audit_logs` tracking `user_id`, `previous_state`, `new_state`, `confidence_score`, and `timestamp`.

---

## Phase 5: FastAPI REST Layer

Define clear API endpoints that will seamlessly map to your HTML/CSS frontend components:

| Endpoint | Method | Purpose | Frontend Target Component |
| --- | --- | --- | --- |
| `/api/batch/upload` | `POST` | Ingests CSV/JSON, triggers normalization & reconciliation pipeline. | File Upload / Drag-and-Drop Zone |
| `/api/batch/summary` | `GET` | Returns match rate %, exception count, total value processed. | Executive KPI Summary Cards & Match Gauge |
| `/api/exceptions` | `GET` | Fetches categorized exceptions sorted by Financial Risk Score. | Exception Workbench Table |
| `/api/exceptions/{id}/action` | `POST` | Accepts `APPROVE`, `REJECT`, or custom adjustment override. | 1-Click Action Buttons |
| `/api/copilot/chat` | `POST` | Streams response for natural language data queries. | Copilot Chat Drawer / Sidebar |
| `/api/forecast/simulate` | `POST` | Calculates dynamic cash runway based on custom risk sliders. | Forward Cash Runway Chart |
| `/api/audit/export` | `GET` | Generates a clean JSON/CSV summary audit report. | Export Audit Package Button |

---

### Verification Strategy

To prove performance for Track 04 judging criteria (*"Throughput + measured accuracy + honest exception list"*):

1. Benchmarking script verifying $50+$ records processed under **3 seconds**.
2. Automated evaluation script measuring precision/recall on synthetic breaks.
3. Verification that zero un-reconciled breaks fail silently (100% categorised into either Matched or Exception tables).


Building Phase 3 now. Starting with the DB model, config, and schemas, then services, then API layer.

Edited models.py
Edited config.py
Edited .env

Now create all the schemas and services:

Created diagnostic.py
Created copilot.py
Created diagnostic_agent.py
Created copilot.py
Created rule_synthesizer.py

Now create the API routers:

Created copilot.py
Created exceptions.py

Now add the pre-Tier-1 DynamicRule hook to `reconciler.py` and register new routers in `main.py`:

Viewed reconciler.py:1-30
Viewed reconciler.py:27-60
Viewed reconciler.py:60-130
Viewed reconciler.py:155-220
Viewed reconciler.py:220-265

Now I have what I need. Add the pre-Tier-1 hook and update imports:

Edited reconciler.py

Now register the 2 new routers in `main.py`:

Edited main.py

Now run the full verification:

Ran command: `cd /Users/abhi/Documents/Projects/ai_finance_controller/backend && source .venv/bin/activate && python3 -c "
import ast, pathlib, sys

# 1. Syntax check all files
errors = []
for f in pathlib.Path('.').rglob('*.py'):
    if '.venv' in f.parts:
        continue
    try:
        ast.parse(f.read_text())
    except SyntaxError as e:
        errors.append(f'{f}: {e}')
if errors:
    for e in errors: print('SYNTAX ERROR:', e)
    sys.exit(1)
print('✅ All files: syntax OK')

# 2. Full import chain
from app.config import settings
print(f'✅ Config: KIMI_MODEL={settings.KIMI_MODEL}, KIMI_BASE_URL={settings.KIMI_BASE_URL}')

from app.db.models import DynamicRule
print('✅ DynamicRule model imported')

from app.schemas.diagnostic import DiagnosticLLMResponse, JournalEntrySchema, DiagnosticOut, ExceptionActionRequest, ExceptionActionOut, BatchDiagnosticOut
from app.schemas.copilot import CopilotRequest, CopilotResponse, CopilotSource
print('✅ All Phase 3 schemas imported')

from app.services.diagnostic_agent import diagnose_exception, diagnose_batch_exceptions, _heuristic_diagnosis
from app.services.copilot import chat, _build_batch_context, _fallback_reply
from app.services.rule_synthesizer import synthesize_and_save, extract_pattern
from app.api.copilot import router as copilot_router
from app.api.exceptions import router as exceptions_router
from app.services.reconciler import ReconciliationEngine  # check hook import
print('✅ All Phase 3 services + API imported')

# 3. Verify OpenAPI schema has all 9 endpoints
from main import app
schema = app.openapi()
paths = sorted(schema.get('paths', {}).keys())
print('\\nRegistered API paths:')
for p in paths:
    print(f'  {p}')

expected = [
    '/api/batch/generate-synthetic',
    '/api/batch/{batch_id}/records',
    '/api/reconciliation/run/{batch_id}',
    '/api/reconciliation/summary/{batch_id}',
    '/api/reconciliation/exceptions/{batch_id}',
    '/api/copilot/chat',
    '/api/exceptions/{exception_id}/action',
    '/api/exceptions/diagnose/{batch_id}',
    '/health',
]
for ep in expected:
    assert ep in paths, f'MISSING: {ep}'
print(f'\\n✅ All {len(expected)} expected endpoints present')

# 4. Smoke test Pydantic schemas
import json
good_json = json.loads('{\"diagnosis\":\"Test\",\"recommended_action\":\"Test action\",\"drafted_journal_entry\":{\"debit_account\":\"Cash\",\"credit_account\":\"Revenue\",\"amount\":1000.0,\"memo\":\"Test\"}}')
result = DiagnosticLLMResponse.model_validate(good_json)
assert result.diagnosis == 'Test'
assert result.drafted_journal_entry.amount == 1000.0
print('✅ DiagnosticLLMResponse: strict parse OK')

bad_json = json.loads('{\"random_field\":\"garbage\"}')
fallback = DiagnosticLLMResponse.model_validate(bad_json)
assert 'manual review' in fallback.diagnosis.lower()
print('✅ DiagnosticLLMResponse: graceful fallback defaults OK')

# 5. Test rule extractor
from app.db.models import FinancialRecord, ExceptionItem
from datetime import date
import uuid

# Mock objects to test extract_pattern
class MockRecord:
    record_id = uuid.uuid4()
    source_type = 'GATEWAY'
    raw_entity_name = 'RZP*ACME-TECH-BLR'
    normalized_entity_name = 'Acme Tech'
    amount = 9800.0
    transaction_date = date.today()
    metadata_json = {'anomaly_type': 'fee_discrepancy_gt_2pct', 'gross_amount': 10000.0, 'gateway_fee': 250.0}

class MockException:
    exception_id = uuid.uuid4()
    risk_score = 'MEDIUM'

from app.services.rule_synthesizer import extract_pattern
result = extract_pattern(MockRecord(), MockException())
assert result is not None, 'Expected a rule to be extracted'
rule_type, pattern, payload = result
print(f'✅ Rule synthesis: extracted {rule_type} pattern=\"{pattern}\" from RZP* entity')

print()
print('🎉 Phase 3: All checks passed.')
"
`

All 9 endpoints live, all checks green. Update the task tracker and walkthrough:

Edited walkthrough.md

## ✅ Phase 3 Complete — 9/9 endpoints, all checks passed

### What was built (12 files created/modified)

**New files:**

| File | Purpose |
|---|---|
| [`schemas/diagnostic.py`](file:///Users/abhi/Documents/Projects/ai_finance_controller/backend/app/schemas/diagnostic.py) | Strict Pydantic v2 with safe fallback defaults |
| [`schemas/copilot.py`](file:///Users/abhi/Documents/Projects/ai_finance_controller/backend/app/schemas/copilot.py) | Chat request/response + source citations |
| [`services/diagnostic_agent.py`](file:///Users/abhi/Documents/Projects/ai_finance_controller/backend/app/services/diagnostic_agent.py) | kimi-k2.6 JSON agent + anomaly-aware heuristic fallback |
| [`services/copilot.py`](file:///Users/abhi/Documents/Projects/ai_finance_controller/backend/app/services/copilot.py) | Full batch context → NL Q&A + keyword fallback |
| [`services/rule_synthesizer.py`](file:///Users/abhi/Documents/Projects/ai_finance_controller/backend/app/services/rule_synthesizer.py) | Extracts REGEX_STRIP / VENDOR_MAP / FEE_TOLERANCE rules |
| [`api/copilot.py`](file:///Users/abhi/Documents/Projects/ai_finance_controller/backend/app/api/copilot.py) | `POST /api/copilot/chat` |
| [`api/exceptions.py`](file:///Users/abhi/Documents/Projects/ai_finance_controller/backend/app/api/exceptions.py) | Diagnose batch + approve/reject with atomic DB update |

**Modified:** `models.py` (DynamicRule), `config.py` (kimi settings), `reconciler.py` (pre-Tier-1 hook), `main.py` (2 new routers)

### Smoke tests
```
✅ All 9 endpoints in OpenAPI schema
✅ DiagnosticLLMResponse: strict parse OK
✅ Graceful fallback (malformed JSON → safe defaults, no crash)
✅ Rule synthesis: RZP*ACME-TECH-BLR → REGEX_STRIP pattern='^RZP\*'
```

> **To enable kimi:** Add your `KIMI_API_KEY` to `backend/.env`. Without it, the system falls back to anomaly-aware heuristic diagnosis automatically — zero silent failures.

Ready for **Phase 4: Cash Forecasting + What-If Simulator + Audit Logger** when you are.