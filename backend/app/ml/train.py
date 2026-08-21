"""
Trains the tumor-malignancy risk model used by the predictions/simulations
routers. Run once (or whenever you want to retrain) with:

    python -m app.ml.train

Dataset: the scikit-learn "Wisconsin Diagnostic Breast Cancer" dataset
(569 samples, 30 numeric features derived from digitized FNA images,
target: malignant/benign). This is a real, publicly documented dataset
bundled with scikit-learn (`sklearn.datasets.load_breast_cancer`) — no
network download required, no synthetic labels.

The trained artifact (classifier + scaler + class centroids + metrics) is
written to app/ml/artifacts/model.joblib and app/ml/artifacts/metrics.json.
The metrics file is what seeds the Research pages (TrainingRun,
ModelVersion, PerformancePoint) with real evaluation numbers instead of
placeholders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler

ARTIFACT_DIR = Path(__file__).parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "model.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"

MODEL_NAME = "OncoTwin Malignancy Risk Model"
MODEL_VERSION = "v1.0.0"


def train() -> dict:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    data = load_breast_cancer()
    X, y = data.data, data.target  # y: 0 = malignant, 1 = benign
    feature_names = list(data.feature_names)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    scaler = StandardScaler().fit(X_train)
    X_train_s = scaler.transform(X_train)
    X_test_s = scaler.transform(X_test)

    clf = RandomForestClassifier(
        n_estimators=300, max_depth=6, min_samples_leaf=3, random_state=42
    )
    clf.fit(X_train_s, y_train)

    y_pred = clf.predict(X_test_s)
    y_proba = clf.predict_proba(X_test_s)[:, 1]  # P(benign)

    accuracy = float(accuracy_score(y_test, y_pred))
    precision = float(precision_score(y_test, y_pred))
    recall = float(recall_score(y_test, y_pred))
    auc = float(roc_auc_score(y_test, y_proba))

    # 5-fold CV AUC curve (used to populate the performance-over-time chart
    # with real numbers rather than a single point).
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fold_aucs = []
    fold_accuracies = []
    fold_precisions = []
    fold_recalls = []
    for train_idx, val_idx in skf.split(X, y):
        fold_scaler = StandardScaler().fit(X[train_idx])
        fold_clf = RandomForestClassifier(
            n_estimators=300, max_depth=6, min_samples_leaf=3, random_state=42
        ).fit(fold_scaler.transform(X[train_idx]), y[train_idx])
        fold_proba = fold_clf.predict_proba(fold_scaler.transform(X[val_idx]))[:, 1]
        fold_pred = fold_clf.predict(fold_scaler.transform(X[val_idx]))
        fold_aucs.append(float(roc_auc_score(y[val_idx], fold_proba)))
        fold_accuracies.append(float(accuracy_score(y[val_idx], fold_pred)))
        fold_precisions.append(float(precision_score(y[val_idx], fold_pred)))
        fold_recalls.append(float(recall_score(y[val_idx], fold_pred)))

    centroid_malignant = X[y == 0].mean(axis=0)
    centroid_benign = X[y == 1].mean(axis=0)
    feature_std = X.std(axis=0)

    bundle = {
        "model": clf,
        "scaler": scaler,
        "feature_names": feature_names,
        "centroid_malignant": centroid_malignant,
        "centroid_benign": centroid_benign,
        "feature_std": feature_std,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
    }
    joblib.dump(bundle, MODEL_PATH)

    metrics = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "dataset_name": "Wisconsin Diagnostic Breast Cancer (sklearn)",
        "dataset_records": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "auc": auc,
        "fold_aucs": fold_aucs,
        "fold_accuracies": fold_accuracies,
        "fold_precisions": fold_precisions,
        "fold_recalls": fold_recalls,
        "n_estimators": clf.n_estimators,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    m = train()
    print(json.dumps(m, indent=2))
