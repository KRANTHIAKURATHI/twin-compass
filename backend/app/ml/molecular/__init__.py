"""METABRIC molecular survival experiment (offline research; not part of any API).

Research model - not clinically validated. Prognostic only: it is not treatment-response prediction.
"""
from pathlib import Path

RESEARCH_STATEMENT = "Research model — not clinically validated"
ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "molecular_survival"
EXPRESSION_SOURCE = "METABRIC Illumina microarray mRNA z-scores (diploid-reference samples), cBioPortal"
