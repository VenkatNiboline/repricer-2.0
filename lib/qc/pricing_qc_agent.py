"""QC agent for sales-to-pricing signals."""

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from supabase_store import get_client, is_configured, insert_qc_findings


def run_pricing_qc(*, qc_run_id: int) -> List[Dict[str, Any]]:
    if not is_configured():
        return []

    findings: List[Dict[str, Any]] = []
    client = get_client()

    features = (
        client.table("pricing_features_daily")
        .select("*")
        .eq("feature_id", "signal_underpriced_high_demand")
        .order("computed_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )
    for row in features:
        if row.get("feature_value") and float(row["feature_value"]) > 0:
            findings.append(
                {
                    "qc_run_id": qc_run_id,
                    "agent_name": "pricing_qc",
                    "check_id": "signal_underpriced",
                    "severity": "info",
                    "sku": row.get("sku"),
                    "country": row.get("country"),
                    "message": f"High demand signal for {row.get('sku')} — consider price review",
                    "metadata": row,
                }
            )

    if findings:
        insert_qc_findings(findings)
    return findings
