"""Orchestrate QC agent loops."""

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from qc.data_qc_agent import run_data_qc
from qc.pricing_qc_agent import run_pricing_qc
from qc.repricing_qc_agent import run_repricing_qc
from supabase_store import complete_qc_run, insert_qc_run, is_configured


def run_all_qc(agents: List[str] | None = None) -> List[Dict[str, Any]]:
    if not is_configured():
        return []

    selected = agents or ["repricing_qc", "data_qc", "pricing_qc"]
    results: List[Dict[str, Any]] = []

    runners = {
        "repricing_qc": run_repricing_qc,
        "data_qc": run_data_qc,
        "pricing_qc": run_pricing_qc,
    }

    for name in selected:
        runner = runners.get(name)
        if not runner:
            continue
        run_id = insert_qc_run(name)
        try:
            findings = runner(qc_run_id=run_id)
            complete_qc_run(
                run_id,
                status="completed",
                summary=f"{len(findings)} findings",
                findings_count=len(findings),
            )
            results.append({"agent": name, "run_id": run_id, "findings": len(findings)})
        except Exception as exc:
            complete_qc_run(
                run_id,
                status="failed",
                summary=str(exc),
                findings_count=0,
            )
            results.append({"agent": name, "run_id": run_id, "error": str(exc)})

    return results


def run_after_repricing() -> Dict[str, Any]:
    from price_reflection import verify_pending_reflections

    verified = verify_pending_reflections()
    qc = run_all_qc(["repricing_qc"])
    return {"verified": len(verified), "qc": qc}
