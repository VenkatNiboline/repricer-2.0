"""QC agent for repricing and price reflection health."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from supabase_store import get_client, is_configured, insert_qc_findings


def run_repricing_qc(*, qc_run_id: int) -> List[Dict[str, Any]]:
    if not is_configured():
        return []

    findings: List[Dict[str, Any]] = []
    client = get_client()

    pending = (
        client.table("price_history")
        .select("id, sku, country, new_price, verified_price, created_at, reflection_status")
        .eq("reflection_status", "pending")
        .eq("pushed", True)
        .execute()
        .data
        or []
    )
    for row in pending:
        created = row.get("created_at")
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
        except Exception:
            continue
        if age_min > 30:
            findings.append(
                _finding(
                    qc_run_id,
                    "reflection_pending_stale",
                    "warning",
                    row,
                    f"Price change for {row['sku']} still pending reflection after {int(age_min)} minutes",
                )
            )

    mismatches = (
        client.table("price_history")
        .select("id, sku, country, new_price, verified_price, reflection_status")
        .eq("reflection_status", "mismatch")
        .limit(50)
        .execute()
        .data
        or []
    )
    for row in mismatches:
        findings.append(
            _finding(
                qc_run_id,
                "reflection_mismatch",
                "critical",
                row,
                f"Amazon price mismatch for {row['sku']}: target {row['new_price']}, verified {row.get('verified_price')}",
            )
        )

    timeouts = (
        client.table("price_history")
        .select("id, sku, country, new_price, reflection_status")
        .eq("reflection_status", "timeout")
        .limit(50)
        .execute()
        .data
        or []
    )
    for row in timeouts:
        findings.append(
            _finding(
                qc_run_id,
                "reflection_timeout",
                "warning",
                row,
                f"Price reflection timed out for {row['sku']}",
            )
        )

    failed = (
        client.table("price_history")
        .select("id, sku, country, error, pushed, dry_run")
        .eq("pushed", False)
        .eq("dry_run", False)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    for row in failed:
        findings.append(
            _finding(
                qc_run_id,
                "push_failed",
                "critical",
                row,
                f"Push failed for {row['sku']}: {row.get('error') or 'unknown error'}",
            )
        )

    if findings:
        insert_qc_findings(findings)
    return findings


def _finding(
    qc_run_id: int,
    check_id: str,
    severity: str,
    row: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    return {
        "qc_run_id": qc_run_id,
        "agent_name": "repricing_qc",
        "check_id": check_id,
        "severity": severity,
        "sku": row.get("sku"),
        "country": row.get("country"),
        "message": message,
        "metadata": {"history_id": row.get("id")},
    }
