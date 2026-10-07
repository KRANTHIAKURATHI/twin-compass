"""GSE163882 neoadjuvant taxane-based chemotherapy pCR research model (offline; not connected to any API)."""
from pathlib import Path

MODEL_NAME = "GSE163882 neoadjuvant chemotherapy pCR prediction model"
STATUS = "Research model — not clinically validated"
TARGET = "Target: pathological complete response (pCR) vs residual disease (RD)"
TREATMENT_CONTEXT = "Treatment context: neoadjuvant taxane-based chemotherapy"
CLAIM = (
    "This model predicts pCR in the GSE163882 neoadjuvant taxane-based chemotherapy cohort. It does not "
    "estimate causal treatment effects and should not be interpreted as a clinical treatment recommendation."
)
ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "treatment_response"
SEED = 42
