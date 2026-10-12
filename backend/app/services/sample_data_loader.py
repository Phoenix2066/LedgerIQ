"""
app/services/sample_data_loader.py
==================================
Service for loading pre-packaged CFO.AI sample financial datasets into DB.
"""

import json
import uuid
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReconciliationBatch, FinancialRecord
from app.services.normalizer import normalize_batch
from app.neatlogs import neatlogs


def get_sample_data_path() -> Path:
    """Find sample_data directory relative to project root or backend directory."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_root = backend_dir.parent
    
    candidates = [
        project_root / "data" / "sample_data",
        backend_dir / "data" / "sample_data",
        Path("data/sample_data"),
        Path("../data/sample_data"),
    ]
    
    for path in candidates:
        if path.exists() and path.is_dir():
            return path
            
    raise FileNotFoundError("Could not locate sample_data directory.")


async def load_sample_batch(db: AsyncSession) -> Dict[str, Any]:
    """Load JSON sample files from data/sample_data/ into DB as a new batch."""
    neatlogs.info("SampleDataLoader", "Locating sample data directory...")
    sample_dir = get_sample_data_path()
    
    bank_file = sample_dir / "bank_statements.json"
    gateway_file = sample_dir / "gateway_settlements.json"
    erp_file = sample_dir / "erp_invoices.json"
    
    records_data = []
    
    # Load bank
    if bank_file.exists():
        with open(bank_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                records_data.append({
                    "source_type": "BANK",
                    "raw_entity_name": item["raw_entity_name"],
                    "amount": float(item["amount"]),
                    "reference_code": item.get("reference_code"),
                    "transaction_date": date.fromisoformat(item["transaction_date"]),
                    "metadata_json": item.get("metadata", {}),
                })
                
    # Load gateway
    if gateway_file.exists():
        with open(gateway_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                records_data.append({
                    "source_type": "GATEWAY",
                    "raw_entity_name": item["raw_entity_name"],
                    "amount": float(item["amount"]),
                    "reference_code": item.get("reference_code"),
                    "transaction_date": date.fromisoformat(item["transaction_date"]),
                    "metadata_json": item.get("metadata", {}),
                })
                
    # Load ERP
    if erp_file.exists():
        with open(erp_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                records_data.append({
                    "source_type": "INVOICE",
                    "raw_entity_name": item["raw_entity_name"],
                    "amount": float(item["amount"]),
                    "reference_code": item.get("reference_code"),
                    "transaction_date": date.fromisoformat(item["transaction_date"]),
                    "metadata_json": item.get("metadata", {}),
                })

    neatlogs.info("SampleDataLoader", f"Loaded {len(records_data)} raw records from sample JSON files.")

    # Concurrently normalize entity names
    raw_names = [r["raw_entity_name"] for r in records_data]
    normalized_names = await normalize_batch(raw_names)
    
    batch_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    # Persist Batch
    batch = ReconciliationBatch(
        batch_id=batch_id,
        total_records=len(records_data),
        matched_count=0,
        exception_count=0,
        match_rate=0.0,
        created_at=now,
    )
    db.add(batch)
    await db.flush()

    # Persist Financial Records
    orm_records = []
    for rec, norm_name in zip(records_data, normalized_names):
        rec["record_id"] = uuid.uuid4()
        rec["batch_id"] = batch_id
        rec["normalized_entity_name"] = norm_name
        rec["status"] = "UNMATCHED"
        orm_records.append(FinancialRecord(**rec))

    db.add_all(orm_records)
    await db.commit()

    neatlogs.success("SampleDataLoader", f"Successfully created Sample Data ReconciliationBatch {batch_id} with {len(orm_records)} records.")
    
    bank_cnt = sum(1 for r in records_data if r["source_type"] == "BANK")
    gateway_cnt = sum(1 for r in records_data if r["source_type"] == "GATEWAY")
    invoice_cnt = sum(1 for r in records_data if r["source_type"] == "INVOICE")

    return {
        "batch_id": str(batch_id),
        "total_records": len(records_data),
        "bank_count": bank_cnt,
        "gateway_count": gateway_cnt,
        "invoice_count": invoice_cnt,
        "created_at": now.isoformat(),
        "source": "sample_data_loader"
    }
