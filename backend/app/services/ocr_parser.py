"""
Deterministic clinical-field parser for OCR text (no LLM, no I/O).

Looks only for the fields in `routers/ocr.py` FIELD_CATALOG. It is deliberately
conservative: a field is returned only when exactly one value is stated
unambiguously; conflicting mentions, ranges, comparators, equivocal results and
vague wording produce no field at all, never a guess. Nothing here is a clinical
judgement - every result still needs clinician verification before it can touch
a patient record.

Each result carries the character span of its *value* in the input text so the
caller can attach the real OCR confidence of exactly those words (or none, for
text that came from a PDF text layer). The parser itself never produces a
confidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

I = re.IGNORECASE


@dataclass(frozen=True)
class ParsedField:
    field: str
    value: str
    start: int  # span of the value in the parsed text
    end: int


_NUM = r"\d+(?:[.,]\d+)?"


def _f(x: float) -> str:
    return f"{round(x, 2):g}"


def _pick(field: str, cands: list[tuple[str, int, int]]) -> list[ParsedField]:
    """One field only when every mention agrees; conflicting mentions are ambiguous -> nothing."""
    if not cands or len({v for v, _, _ in cands}) != 1:
        return []
    v, s, e = cands[0]
    return [ParsedField(field, v, s, e)]


# --- tumour size ------------------------------------------------------------------------
_SIZE = re.compile(
    rf"\b(?:tumou?r|lesion|mass|nodule)(?:\s+size)?\s*(?:measur(?:es|ing|ed)|of|is|was|:|=|-)?\s*(?:approximately\s+|about\s+|~\s*)?"
    rf"(?P<v>(?P<n>{_NUM})\s*(?P<u>mm|cm))\b(?!\s*[x×*]\s*\d)",
    I,
)


def _tumor_size(text: str) -> list[ParsedField]:
    c = []
    for m in _SIZE.finditer(text):
        n = float(m["n"].replace(",", "."))
        mm = n * 10 if m["u"].lower() == "cm" else n
        if 0 < mm <= 300:
            c.append((_f(mm), m.start("v"), m.end("v")))
    return _pick("tumor_size_mm", c)


# --- receptors --------------------------------------------------------------------------
_STATUS = r"(?P<v>positive|negative|pos|neg)\b(?!\s*/)"


def _receptor(text: str, field: str, label: str) -> list[ParsedField]:
    rx = re.compile(rf"{label}(?:\s*\(\s*(?-i:[A-Z]{{2}})\s*\))?\s*(?:status|receptor)?\s*[:=\-]?\s*(?:is\s+)?{_STATUS}", I)
    c = []
    for m in rx.finditer(text):
        c.append(("Positive" if m["v"].lower().startswith("pos") else "Negative", m.start("v"), m.end("v")))
    return _pick(field, c)


_ER = r"(?<![/&])(?<!and )(?:(?-i:\bER\b)|\bestrogen\s+receptors?)"
_PR = r"(?<![/&])(?<!and )(?:(?-i:\bPR\b)|\bprogesterone\s+receptors?)"

# HER2: 0/1+ negative, 3+ positive, 2+ (or the words equivocal/borderline) is NOT classified.
_HER2_NAME = r"(?:(?-i:\bHER)[\s\-]?2(?:\s*/\s*neu)?|\bHER-?2\s*/\s*neu)"
_HER2_WORD = re.compile(rf"{_HER2_NAME}(?:\s*(?:status|receptor))?\s*[:=\-]?\s*(?:is\s+)?{_STATUS}", I)
_HER2_SCORE = re.compile(rf"{_HER2_NAME}\s*(?:IHC\s*)?(?:score\s*)?[:=\-]?\s*(?P<v>[0-3]\s*\+|0)(?![\d.])", I)
_HER2_EQUIVOCAL = re.compile(rf"{_HER2_NAME}[^.\n]{{0,60}}?\b(?:equivocal|borderline|indeterminate)\b", I)


def _her2(text: str) -> list[ParsedField]:
    if _HER2_EQUIVOCAL.search(text):
        return []
    c = []
    for m in _HER2_WORD.finditer(text):
        c.append(("Positive" if m["v"].lower().startswith("pos") else "Negative", m.start("v"), m.end("v")))
    for m in _HER2_SCORE.finditer(text):
        score = m["v"].replace(" ", "")
        if score == "2+":
            return []  # equivocal IHC: never read as positive or negative
        c.append(("Positive" if score == "3+" else "Negative", m.start("v"), m.end("v")))
    return _pick("her2_status", c)


# --- Ki-67 ------------------------------------------------------------------------------
_KI67 = re.compile(
    rf"\b(?:ki[\s\-]?67(?:\s*(?:labell?ing\s+)?(?:index|proliferation(?:\s+index)?|expression|score))?|proliferation\s+index)"
    rf"\s*(?:is|of|at|was|:|=|-)?\s*(?:approximately\s+|about\s+|~\s*)?(?P<v>(?P<n>{_NUM})\s*%)",
    I,
)


def _ki67(text: str) -> list[ParsedField]:
    c = []
    for m in _KI67.finditer(text):
        n = float(m["n"].replace(",", "."))
        if 0 <= n <= 100:
            c.append((_f(n), m.start("v"), m.end("v")))
    return _pick("ki67", c)


# --- grade ------------------------------------------------------------------------------
_ROMAN = {"i": "1", "ii": "2", "iii": "3"}
_GRADE = re.compile(
    r"\bgrade\s*[:=\-]?\s*(?:is\s+)?(?:G\s*)?(?P<v>[123]|III|II|I)\b(?!\s*[-–/]\s*(?:[123]|III|II|I)\b)(?!\s*(?:\.|,)?\d)",
    I,
)


def _grade(text: str) -> list[ParsedField]:
    c = []
    for m in _GRADE.finditer(text):
        before = text[max(0, m.start() - 12) : m.start()].lower()
        if re.search(r"(nuclear|nucleolar|architectural|nuclei)\s*$", before):
            continue  # DCIS nuclear grade etc. is not the tumour (Nottingham) grade
        v = m["v"]
        c.append((_ROMAN.get(v.lower(), v), m.start("v"), m.end("v")))
    return _pick("grade", c)


# --- positive lymph nodes ---------------------------------------------------------------
_NODE_KIND = r"(?:sentinel\s+|axillary\s+|regional\s+)*(?:lymph\s+)?nodes?\b"
_NODES = [
    # "0/12 nodes", "2/15 lymph nodes positive"  (positive / examined)
    re.compile(rf"(?<![\d/])(?P<v>\d{{1,2}})\s*/\s*(?P<d>\d{{1,2}})\s*{_NODE_KIND}", I),
    # "3 positive nodes"
    re.compile(rf"(?<![\d/])(?P<v>\d{{1,2}})\s+(?:positive|metastatic|involved)\s+{_NODE_KIND}", I),
    # "nodes involved: 3", "positive lymph nodes = 3"
    re.compile(rf"\b(?:{_NODE_KIND}\s+(?:involved|positive)|(?:positive|involved)\s+{_NODE_KIND})\s*[:=]\s*(?P<v>\d{{1,2}})(?!\s*/|\d)", I),
]


def _nodes(text: str) -> list[ParsedField]:
    c = []
    for rx in _NODES:
        for m in rx.finditer(text):
            if "d" in rx.groupindex and int(m["v"]) > int(m["d"]):
                continue  # "positive/examined" cannot have more positive than examined
            c.append((str(int(m["v"])), m.start("v"), m.end("v")))
    return _pick("nodes_involved", c)


# --- stage ------------------------------------------------------------------------------
_STAGE_ROMAN = {"0": "0", "1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}
_STAGE = re.compile(r"\bstage\s*(?:group)?\s*[:=\-]?\s*(?P<v>IV|III|II|I|[0-4])(?:[ABC][1-3]?)?\b(?!\s*[-–/]\s*(?:IV|III|II|I|[0-4])\b)", I)
_TNM = re.compile(
    r"(?<![A-Za-z])(?P<pre>[pc])T(?P<t>is|0|1mi|1[abc]?|2|3|4[abcd]?)\s*[,;]?\s*[pc]?N(?P<n>0|1mi|1|2|3)[abc]?(?:\(\w+\))?"
    r"(?:\s*[,;]?\s*[pc]?M(?P<m>[01]))?\b"
)


def _stage_from_tnm(t: str, n: str, m: str | None) -> str | None:
    """AJCC anatomic stage group from T/N/M. Only with an explicit M category - never assumes M0."""
    if m is None:
        return None
    if m == "1":
        return "IV"
    t0 = "is" if t == "is" else t[0]
    if t0 == "is":
        return "0" if n == "0" else None
    if n == "3":
        return "III"
    if t0 == "4":
        return "III"
    if t0 == "3":
        return "II" if n == "0" else "III"
    if t0 == "2":
        return "II" if n in ("0", "1") else "III"
    if t0 in ("0", "1"):
        if n == "0":
            return "I" if t0 == "1" else None
        if n == "1mi":
            return "I"
        return "II" if n == "1" else "III"
    return None


def _stage(text: str) -> list[ParsedField]:
    c = []
    for m in _STAGE.finditer(text):
        c.append((_STAGE_ROMAN[m["v"].upper()], m.start("v"), m.end("v")))
    for m in _TNM.finditer(text):
        if text[max(0, m.start() - 1) : m.start()].lower() == "y":
            continue  # post-neoadjuvant (yp) staging is not the diagnostic stage
        s = _stage_from_tnm(m["t"].lower(), m["n"].lower(), m["m"])
        if s:
            c.append((s, m.start(), m.end()))
    return _pick("stage", c)


# --- diagnosis date (only when explicitly tied to diagnosis) ----------------------------
_MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
_DX = r"(?:date\s+of\s+(?:initial\s+)?diagnosis|(?:initial\s+)?diagnosis\s+date|diagnosed\s+on|dx\s+date|date\s+of\s+dx)"
_DATE = (
    r"(?P<v>(?P<iso>\d{4})-(?P<im>\d{2})-(?P<id>\d{2})"
    r"|(?P<d1>\d{1,2})[/.\-](?P<m1>\d{1,2})[/.\-](?P<y1>\d{4})"
    r"|(?P<d2>\d{1,2})(?:st|nd|rd|th)?[\s\-]+(?P<mn2>[A-Za-z]{3,9})\.?,?[\s\-]+(?P<y2>\d{4})"
    r"|(?P<mn3>[A-Za-z]{3,9})\.?\s+(?P<d3>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y3>\d{4}))"
)
_DX_DATE = re.compile(rf"\b{_DX}\s*[:=\-]?\s*{_DATE}\b", I)


def _month(name: str) -> int | None:
    return _MONTHS.get(name[:3].lower()) if name[:3].lower() in _MONTHS else None


def _iso(m: re.Match[str]) -> str | None:
    try:
        if m["iso"]:
            y, mo, d = int(m["iso"]), int(m["im"]), int(m["id"])
        elif m["d1"]:
            a, b, y = int(m["d1"]), int(m["m1"]), int(m["y1"])
            if a > 12 or a == b:
                d, mo = a, b
            elif b > 12:
                d, mo = b, a
            else:
                return None  # 03/04/2024: day-first vs month-first cannot be told apart
        elif m["d2"]:
            d, y, mo = int(m["d2"]), int(m["y2"]), _month(m["mn2"])
        else:
            d, y, mo = int(m["d3"]), int(m["y3"]), _month(m["mn3"])
        if mo is None:
            return None
        v = date(y, mo, d)
    except ValueError:
        return None
    return v.isoformat() if date(1990, 1, 1) <= v <= date.today() else None


def _diagnosed_on(text: str) -> list[ParsedField]:
    c = []
    for m in _DX_DATE.finditer(text):
        iso = _iso(m)
        if iso:
            c.append((iso, m.start("v"), m.end("v")))
    return _pick("diagnosed_on", c)


def parse_clinical_fields(text: str) -> list[ParsedField]:
    """All catalogue fields that `text` states unambiguously, in a stable order."""
    if not text or not text.strip():
        return []
    return [
        *_tumor_size(text),
        *_receptor(text, "er_status", _ER),
        *_receptor(text, "pr_status", _PR),
        *_her2(text),
        *_ki67(text),
        *_grade(text),
        *_nodes(text),
        *_stage(text),
        *_diagnosed_on(text),
    ]
