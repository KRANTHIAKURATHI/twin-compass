"""Required clinical inputs of the WDBC severity mapping (`app.ml.model.clinical_factors`).

That mapping has a silent default for each of its nine inputs, so a missing value would be scored as if a typical one
had been recorded (a missing ER/PR status as "positive", a missing HER2 as "negative"). Every caller that reaches it
must therefore supply all nine, inside the range the mapping is defined for. Nothing here defaults, corrects or
estimates a value; stage and receptor status only get their canonical spelling.
"""
from __future__ import annotations

import math
from typing import Any

_STAGES = {"0": "0", "i": "I", "ii": "II", "iii": "III", "iv": "IV"}
_STATUSES = {"positive": "Positive", "negative": "Negative"}


def _num(value: object) -> bool:
    try:
        return math.isfinite(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


# patients column: (model input name, validity check)
WDBC_RULES: dict[str, tuple[str, Any]] = {
    "age": ("age", lambda v: _num(v) and 0 < float(v) <= 120),
    "tumor_size_mm": ("tumorSizeMm", lambda v: _num(v) and 0 < float(v) <= 1000),
    "nodes_involved": ("nodesInvolved", lambda v: _num(v) and 0 <= float(v) <= 200),
    "grade": ("grade", lambda v: _num(v) and float(v) in (1.0, 2.0, 3.0)),
    "ki67": ("ki67", lambda v: _num(v) and 0 <= float(v) <= 100),
    "stage": ("stage", lambda v: str(v).strip().lower() in _STAGES),
    "er_status": ("erStatus", lambda v: str(v).strip().lower() in _STATUSES),
    "pr_status": ("prStatus", lambda v: str(v).strip().lower() in _STATUSES),
    "her2_status": ("her2Status", lambda v: str(v).strip().lower() in _STATUSES),
}


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def check_patient_columns(patient: dict[str, Any]) -> tuple[dict[str, object], list[str], list[str]]:
    """(model inputs, missing columns, invalid columns) for a patient row keyed by `patients` column."""
    fields: dict[str, object] = {}
    missing: list[str] = []
    invalid: list[str] = []
    for column, (name, ok) in WDBC_RULES.items():
        value = patient.get(column)
        if _blank(value):
            missing.append(column)
        elif not ok(value):
            invalid.append(column)
        else:
            fields[name] = (
                _STAGES[str(value).strip().lower()] if column == "stage"
                else _STATUSES[str(value).strip().lower()] if column.endswith("_status")
                # Already validated as exactly 1, 2 or 3; "2.0" (a numeric stored as text) becomes the integer 2.
                else int(float(value)) if column == "grade"
                else value
            )
    return fields, missing, invalid


def require_model_fields(fields: dict[str, Any]) -> None:
    """Raise ValueError unless a camelCase model input dict holds all nine inputs, valid (no defaults, no correction)."""
    by_name = {name: column for column, (name, _) in WDBC_RULES.items()}
    _, missing, invalid = check_patient_columns({by_name[k]: v for k, v in fields.items() if k in by_name})
    if missing or invalid:
        raise ValueError(
            "the WDBC severity mapping needs every clinical input recorded; "
            + "; ".join(p for p in (
                "missing: " + ", ".join(WDBC_RULES[c][0] for c in missing) if missing else "",
                "invalid: " + ", ".join(WDBC_RULES[c][0] for c in invalid) if invalid else "") if p)
        )
