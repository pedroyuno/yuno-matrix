"""
Pré-Check Report generator for MATRIX.

Transforms execution results into a structured report grouped by operation
category (AUTH, CAPTURE, CANCEL, REFUND, TOKEN, STATUS, ERR) with severity
levels (P0/P1/P2), test types (auto/semi_auto), and SKIPPED cascading when
a P0 test fails.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.models import TestSuite


# ── Constants ─────────────────────────────────────────────────────────────────

OPERATION_TO_CATEGORY: Dict[str, str] = {
    "authorize": "AUTH",
    "purchase": "AUTH",
    "capture": "CAPTURE",
    "partial_capture": "CAPTURE",
    "cancel": "CANCEL",
    "void": "CANCEL",
    "refund": "REFUND",
    "partial_refund": "REFUND",
    "tokenize": "TOKEN",
    "verify": "STATUS",
    "e2e_payment": "AUTH",
}

SEMI_AUTO_PAYMENT_METHODS = {"PIX", "BOLETO", "NUPAY", "OXXO", "EFECTY", "PSE"}

CATEGORY_ORDER = ["AUTH", "CAPTURE", "CANCEL", "REFUND", "TOKEN", "STATUS", "ERR"]


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class ReportRow:
    """A single row in the Pré-Check Report table."""
    pre_check_id: str          # e.g. "AUTH-CARD-BR-001"
    test_case_id: str          # original tc id for tracing
    step_id: int               # which step within the test case
    name: str                  # human-readable description
    category: str              # AUTH, CAPTURE, etc.
    payment_method: str        # CARD, PIX, BOLETO...
    country: str               # BR, MX, CO...
    severity: str              # P0, P1, P2
    test_type: str             # auto, semi_auto
    status: str                # PASSED, FAILED, ERROR, SKIPPED
    reason: Optional[str]      # error message / skip reason


@dataclass
class CategorySection:
    """A section of the report, e.g. ## AUTH."""
    category: str
    rows: List[ReportRow] = field(default_factory=list)


@dataclass
class ReportMeta:
    """Report header metadata."""
    run_id: str          # run-YYYYMMDD-HHMMSS
    merchant_name: str   # derived from suite name
    ambiente: str        # SANDBOX or PRODUCTION
    modo: str            # DRY-RUN or LIVE
    execution_id: str    # raw execution_id from SSE start event


@dataclass
class PreCheckReport:
    """Complete Pré-Check Report."""
    meta: ReportMeta
    sections: List[CategorySection] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_report(
    test_suite: TestSuite,
    test_results: Dict[str, Any],
    hierarchy: List[Dict],
    execution_id: str,
    placeholder_mode: bool = False,
    selected_test_case_ids: Optional[List[str]] = None,
) -> PreCheckReport:
    """
    Transform a test suite and its execution results into a PreCheckReport.

    Args:
        test_suite: The full test suite (all test cases).
        test_results: Dict of {tc_id: result_dict} from the SSE stream.
                      Each result_dict has: status, steps (list), error_message.
        hierarchy: Hierarchy list stored at upload time; used to look up
                   payment_method and country per test case id.
        execution_id: Raw execution id, e.g. "20260227_191515".
        placeholder_mode: If True, mode is DRY-RUN; otherwise LIVE.
        selected_test_case_ids: IDs of the test cases the user selected to run.
                                When provided, only these test cases appear in
                                the report. When None, all test cases are included.

    Returns:
        Populated PreCheckReport.
    """
    meta = _build_meta(execution_id, test_suite, placeholder_mode)
    tc_context = _build_tc_context(hierarchy)

    # Restrict to selected test cases only (if provided)
    if selected_test_case_ids is not None:
        selected_set = set(selected_test_case_ids)
        test_cases = [tc for tc in test_suite.test_cases if tc.id in selected_set]
    else:
        test_cases = list(test_suite.test_cases)

    # Phase 1: build flat list of (pre-)rows with provisional status
    rows: List[ReportRow] = []
    counters: Dict[tuple, int] = {}  # (category, pm, country) -> count
    first_in_group: Dict[tuple, bool] = {}  # track if this is the first row per group

    for tc in test_cases:
        result = test_results.get(tc.id)
        ctx = tc_context.get(tc.id, {"payment_method": "UNKNOWN", "country": "BR"})
        pm = ctx["payment_method"].upper()
        country = ctx["country"].upper()

        # Build step_id -> step_result lookup
        step_results_by_id: Dict[int, Dict] = {}
        if result and result.get("steps"):
            for sr in result["steps"]:
                step_results_by_id[sr["step_id"]] = sr

        for step in tc.steps:
            category = OPERATION_TO_CATEGORY.get(step.operation.lower(), "ERR")
            group_key = (category, pm, country)

            # Determine if this is the first occurrence of this group
            is_first = group_key not in first_in_group
            if is_first:
                first_in_group[group_key] = True

            # Increment counter and build pre-check ID
            counters[group_key] = counters.get(group_key, 0) + 1
            seq = counters[group_key]
            pre_check_id = f"{category}-{pm}-{country}-{seq:03d}"

            # Assign severity
            if category == "STATUS":
                severity = "P2"
            elif is_first:
                severity = "P0"
            else:
                severity = "P1"

            # Assign test type
            test_type = "semi_auto" if pm in SEMI_AUTO_PAYMENT_METHODS else "auto"

            # Determine status
            if result is None:
                # Test case was not selected / not run
                status = "SKIPPED"
                reason: Optional[str] = "Not executed"
            else:
                sr = step_results_by_id.get(step.step_id)
                if sr is None:
                    # Step was not reached (earlier step in same tc failed)
                    status = "SKIPPED"
                    reason = "Halted by earlier step failure in test case"
                elif sr["status"] == "success":
                    status = "PASSED"
                    reason = None
                else:
                    status = "FAILED"
                    reason = _extract_reason(sr)

            rows.append(ReportRow(
                pre_check_id=pre_check_id,
                test_case_id=tc.id,
                step_id=step.step_id,
                name=step.description,
                category=category,
                payment_method=pm,
                country=country,
                severity=severity,
                test_type=test_type,
                status=status,
                reason=reason,
            ))

    # Phase 2: P0 cascade — when a P0 row FAILS, mark all subsequent rows
    # for the same (pm, country) as SKIPPED.
    p0_failed_pm_country: set = set()
    final_rows: List[ReportRow] = []

    for row in rows:
        pm_country = (row.payment_method, row.country)

        if row.severity == "P0" and row.status == "FAILED":
            p0_failed_pm_country.add(pm_country)

        if pm_country in p0_failed_pm_country and row.status not in ("PASSED", "FAILED"):
            row.status = "SKIPPED"
            row.reason = "Halted due to P0 failure"

        final_rows.append(row)

    # Phase 3: group into CategorySections in CATEGORY_ORDER
    sections_map: Dict[str, CategorySection] = {c: CategorySection(category=c) for c in CATEGORY_ORDER}

    for row in final_rows:
        cat = row.category if row.category in sections_map else "ERR"
        sections_map[cat].rows.append(row)

    sections = [s for c in CATEGORY_ORDER for s in [sections_map[c]] if s.rows]

    # Phase 4: compute totals
    total = len(final_rows)
    passed = sum(1 for r in final_rows if r.status == "PASSED")
    failed = sum(1 for r in final_rows if r.status in ("FAILED", "ERROR"))
    skipped = sum(1 for r in final_rows if r.status == "SKIPPED")

    return PreCheckReport(
        meta=meta,
        sections=sections,
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_meta(
    execution_id: str,
    test_suite: TestSuite,
    placeholder_mode: bool,
) -> ReportMeta:
    """Build ReportMeta from execution context."""
    run_id = "run-" + execution_id.replace("_", "-")

    suite_name = test_suite.metadata.test_suite_name
    merchant_name = suite_name.removeprefix("Generated Test Suite - ").strip() or suite_name

    ambiente = test_suite.metadata.environment.upper()
    modo = "DRY-RUN (sem baseline real)" if placeholder_mode else "LIVE"

    return ReportMeta(
        run_id=run_id,
        merchant_name=merchant_name,
        ambiente=ambiente,
        modo=modo,
        execution_id=execution_id,
    )


def _build_tc_context(hierarchy: List[Dict]) -> Dict[str, Dict]:
    """
    Walk the hierarchy list and build {tc_id: {payment_method, country}} lookup.

    Hierarchy structure: [{id, name, providers: [{id, name, integration_id,
    test_cases: [{id, ...}], country?}]}]
    """
    ctx: Dict[str, Dict] = {}
    for pm in hierarchy:
        pm_name = pm.get("name", "UNKNOWN").upper()
        for provider in pm.get("providers", []):
            # Extract country from integration_id suffix (e.g. "REDE_CARD_BR" → "BR")
            integration_id = provider.get("integration_id", "")
            parts = integration_id.split("_")
            # Last segment is country if it's a 2-letter code
            country = parts[-1] if len(parts) > 2 and len(parts[-1]) == 2 else "BR"

            # Also check explicit country field if present
            if provider.get("country"):
                country = str(provider["country"]).upper()

            for tc in provider.get("test_cases", []):
                ctx[tc["id"]] = {
                    "payment_method": pm_name,
                    "country": country,
                    "provider": provider.get("name", ""),
                }
    return ctx


def _extract_reason(step_result: Dict) -> str:
    """Extract a concise failure reason from a step result dict."""
    if step_result.get("error_message"):
        msg = str(step_result["error_message"])
        return msg[:150] if len(msg) > 150 else msg

    parts = []
    if step_result.get("http_status_code"):
        parts.append(f"HTTP {step_result['http_status_code']}")
    if step_result.get("response_status"):
        parts.append(f"status={step_result['response_status']}")
    if parts:
        return ", ".join(parts)

    return "Unknown failure"


# ── Serialization ──────────────────────────────────────────────────────────────

def report_to_dict(report: PreCheckReport) -> Dict:
    """Serialize PreCheckReport to a JSON-safe dict."""
    return {
        "meta": {
            "run_id": report.meta.run_id,
            "merchant_name": report.meta.merchant_name,
            "ambiente": report.meta.ambiente,
            "modo": report.meta.modo,
            "execution_id": report.meta.execution_id,
        },
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "skipped": report.skipped,
        "sections": [
            {
                "category": section.category,
                "rows": [
                    {
                        "pre_check_id": row.pre_check_id,
                        "test_case_id": row.test_case_id,
                        "step_id": row.step_id,
                        "name": row.name,
                        "category": row.category,
                        "payment_method": row.payment_method,
                        "country": row.country,
                        "severity": row.severity,
                        "test_type": row.test_type,
                        "status": row.status,
                        "reason": row.reason,
                    }
                    for row in section.rows
                ],
            }
            for section in report.sections
        ],
    }


def report_from_dict(data: Dict) -> PreCheckReport:
    """Deserialize a PreCheckReport from a saved JSON dict."""
    meta_data = data["meta"]
    meta = ReportMeta(
        run_id=meta_data["run_id"],
        merchant_name=meta_data["merchant_name"],
        ambiente=meta_data["ambiente"],
        modo=meta_data["modo"],
        execution_id=meta_data["execution_id"],
    )
    sections = []
    for s in data.get("sections", []):
        rows = [
            ReportRow(
                pre_check_id=r["pre_check_id"],
                test_case_id=r["test_case_id"],
                step_id=r["step_id"],
                name=r["name"],
                category=r["category"],
                payment_method=r["payment_method"],
                country=r["country"],
                severity=r["severity"],
                test_type=r["test_type"],
                status=r["status"],
                reason=r.get("reason"),
            )
            for r in s.get("rows", [])
        ]
        sections.append(CategorySection(category=s["category"], rows=rows))

    return PreCheckReport(
        meta=meta,
        sections=sections,
        total=data.get("total", 0),
        passed=data.get("passed", 0),
        failed=data.get("failed", 0),
        skipped=data.get("skipped", 0),
    )
