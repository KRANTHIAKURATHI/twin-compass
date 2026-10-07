"""Survival metrics: concordance, time-dependent AUC and integrated Brier score."""
from __future__ import annotations

import numpy as np
from sksurv.metrics import concordance_index_censored, cumulative_dynamic_auc, integrated_brier_score
from sksurv.util import Surv


def make_y(event: np.ndarray, time: np.ndarray):
    return Surv.from_arrays(event=event.astype(bool), time=time.astype(float))


def c_index(event: np.ndarray, time: np.ndarray, risk: np.ndarray) -> float:
    return float(concordance_index_censored(event.astype(bool), time, risk)[0])


def evaluation_times(y_test, n: int = 8) -> np.ndarray:
    """Evenly spaced times inside the test follow-up (10th-80th percentile of
    observed event times), the range where IPCW metrics are well defined."""
    event_times = y_test["time"][y_test["event"]]
    return np.unique(np.percentile(event_times, np.linspace(10, 80, n)).round(1))


def time_dependent_auc(y_train, y_test, risk: np.ndarray, times: np.ndarray) -> dict[str, object]:
    auc, mean_auc = cumulative_dynamic_auc(y_train, y_test, risk, times)
    return {"times_months": times.tolist(), "auc": [float(a) for a in auc], "mean_auc": float(mean_auc)}


def brier(model, X_test, y_train, y_test, times: np.ndarray) -> float:
    """Integrated Brier score of the model's predicted survival curves."""
    surv = np.asarray([[fn(t) for t in times] for fn in model.predict_survival_function(X_test)])
    return float(integrated_brier_score(y_train, y_test, surv, times))


def safe(metric_fn, *args) -> tuple[object, str | None]:
    """(value, None) or (None, reason): a metric that cannot be computed is
    reported as unavailable, never filled in."""
    try:
        return metric_fn(*args), None
    except Exception as exc:  # noqa: BLE001 - recorded verbatim in the report
        return None, f"{type(exc).__name__}: {exc}"
