"""Iter103 — CSV lead import.

Tenant-scoped CSV upload that streams rows through the existing
`_normalize_and_capture` pipeline so dedup + scoring + event-log are
identical to webhook inbound.

Endpoints:
  POST /api/leads/import-csv/preview  → returns columns + first 5 rows
                                        + a suggested field-mapping
  POST /api/leads/import-csv           → actually imports, given user-confirmed
                                        column→field mapping
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from routes.tenants import require_tenant_role

router = APIRouter(prefix="/api/leads/import-csv", tags=["leads-csv"])


MAX_CSV_BYTES = 8 * 1024 * 1024  # 8MB
MAX_ROWS = 5000

# Field names the lead-capture pipeline understands. Anything else gets
# dropped (we don't carry custom columns into the lead doc — keeps schema
# clean).
ARIA_FIELDS = (
    "first_name", "last_name", "email", "phone", "company",
    "job_title", "linkedin_url", "country", "industry", "message",
    "utm_source", "utm_campaign", "utm_medium",
)

# Header-keyword → aria-field auto-mapping table. Lowercased substring match.
HEADER_HINTS = {
    "first_name":   ("first name", "firstname", "fname", "given"),
    "last_name":    ("last name", "lastname", "lname", "surname", "family"),
    "email":        ("email", "e-mail", "mail"),
    "phone":        ("phone", "mobile", "tel", "cell"),
    "company":      ("company", "organization", "org", "employer", "account"),
    "job_title":    ("title", "job", "role", "position"),
    "linkedin_url": ("linkedin", "li url", "li profile"),
    "country":      ("country", "region"),
    "industry":     ("industry", "sector", "vertical"),
    "message":      ("message", "notes", "comment", "reason"),
    "utm_source":   ("source", "utm_source", "utmsource"),
    "utm_campaign": ("campaign", "utm_campaign"),
    "utm_medium":   ("medium", "utm_medium"),
}


def _auto_map(headers: List[str]) -> Dict[str, str]:
    """Return {csv_header: aria_field} best-effort mapping."""
    mapping: Dict[str, str] = {}
    used = set()
    for h in headers:
        hl = h.lower().strip()
        for aria, hints in HEADER_HINTS.items():
            if aria in used:
                continue
            if any(hint in hl for hint in hints):
                mapping[h] = aria
                used.add(aria)
                break
    return mapping


def _read_csv(content: bytes) -> tuple[List[str], List[Dict[str, str]]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    rows = []
    for i, row in enumerate(reader):
        if i >= MAX_ROWS:
            break
        rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
    return headers, rows


@router.post("/preview")
async def preview_csv(
    file: UploadFile = File(...),
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Step 1 — caller uploads the CSV, gets back columns + 5-row sample +
    suggested mapping. UI displays the mapping form for confirmation.
    """
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file.")
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(413, f"CSV too large (max {MAX_CSV_BYTES // (1024*1024)}MB).")
    try:
        headers, rows = _read_csv(content)
    except Exception as e:
        raise HTTPException(400, f"CSV parse failed: {str(e)[:160]}")
    if not headers:
        raise HTTPException(400, "CSV has no header row.")
    return {
        "ok": True,
        "headers": headers,
        "row_count": len(rows),
        "preview_rows": rows[:5],
        "suggested_mapping": _auto_map(headers),
        "supported_aria_fields": list(ARIA_FIELDS),
    }


class ImportPayload(BaseModel):
    # JSON string carried in form-data because we also need the file. The UI
    # serializes the user-confirmed mapping into this field.
    mapping_json: str
    default_utm_source: Optional[str] = "csv_import"


@router.post("")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    default_utm_source: str = Form("csv_import"),
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Step 2 — actually run the import. Streams every row through
    `_normalize_and_capture` so dedup + scoring + event-log match
    webhook inbound.
    """
    import json
    try:
        mapping: Dict[str, str] = json.loads(mapping_json or "{}")
    except Exception:
        raise HTTPException(400, "mapping_json must be valid JSON")

    # Only allow mappings whose target is a real aria field.
    mapping = {k: v for k, v in mapping.items() if v in ARIA_FIELDS}
    if "email" not in mapping.values() and "phone" not in mapping.values():
        raise HTTPException(400, "At least one column must map to 'email' or 'phone'.")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file.")
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(413, "CSV too large.")
    try:
        _, rows = _read_csv(content)
    except Exception as e:
        raise HTTPException(400, f"CSV parse failed: {str(e)[:160]}")

    # Defer import to avoid circular at module load.
    from routes.integrations_hub import _normalize_and_capture

    imported = 0
    deduped = 0
    failed = 0
    sample_failures: List[str] = []

    for row in rows:
        raw: Dict[str, Any] = {"utm_source": default_utm_source}
        for csv_h, aria_f in mapping.items():
            v = row.get(csv_h)
            if v:
                raw[aria_f] = v
        # Skip rows that have no contact handle at all
        if not raw.get("email") and not raw.get("phone"):
            failed += 1
            continue
        try:
            res = await _normalize_and_capture(tenant["id"], raw, "csv_import", request)
            if res.get("deduplicated"):
                deduped += 1
            else:
                imported += 1
        except Exception as e:
            failed += 1
            if len(sample_failures) < 5:
                sample_failures.append(f"{(raw.get('email') or raw.get('phone'))}: {str(e)[:120]}")

    return {
        "ok": True,
        "rows_processed":   len(rows),
        "imported":         imported,
        "deduplicated":     deduped,
        "failed":           failed,
        "sample_failures":  sample_failures,
        "completed_at":     datetime.now(timezone.utc).isoformat(),
    }
