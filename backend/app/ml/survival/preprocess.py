"""Preprocessing for the survival models, fitted on the training split only."""
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import CATEGORICAL_FEATURES, NUMERIC_FEATURES

UNKNOWN = "Unknown"


def build_preprocessor() -> ColumnTransformer:
    """Unfitted transformer. Calling `.fit` on the training rows alone learns the
    medians, scaling and category levels; the test rows are only ever passed
    through `.transform`.

    Numeric: median imputation, then standardisation (keeps Cox coefficients
    comparable). Categorical: missing becomes an explicit "Unknown" level, then
    one-hot; a level never seen in training encodes as all zeros.
    """
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="constant", fill_value=UNKNOWN)),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        [("num", numeric, NUMERIC_FEATURES), ("cat", categorical, CATEGORICAL_FEATURES)],
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")
