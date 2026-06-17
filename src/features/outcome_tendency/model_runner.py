"""Model benchmark runner for outcome tendency classification."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import LabelEncoder


@dataclass
class BenchmarkResult:
    """Single model benchmark output."""

    model: str
    macro_f1: float
    accuracy: float
    brier: float | None
    classes: list[str]


class OutcomeModelRunner:
    """Trains and compares lightweight classifiers for tendency analysis."""

    def benchmark(
        self,
        rows: list[dict[str, Any]],
        targets: list[str],
    ) -> dict[str, Any]:
        """Train benchmark models and return aggregate metrics."""
        if len(rows) < 80:
            return {
                "status": "insufficient_data",
                "message": "Need at least 80 labeled examples for benchmark training.",
                "sample_size": len(rows),
            }

        vec = DictVectorizer(sparse=False)
        X = vec.fit_transform(rows)
        enc = LabelEncoder()
        y = enc.fit_transform(targets)

        class_counts = Counter(targets)
        if min(class_counts.values()) < 3:
            return {
                "status": "insufficient_class_support",
                "message": "Each target class needs at least 3 examples for robust split.",
                "sample_size": len(rows),
                "class_distribution": dict(class_counts),
            }

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y,
        )

        results: list[BenchmarkResult] = []

        lr = LogisticRegression(max_iter=800, class_weight="balanced")
        results.append(
            self._evaluate_model(
                "logistic_regression", lr, X_train, X_test, y_train, y_test, enc
            )
        )

        rf = RandomForestClassifier(
            n_estimators=250,
            random_state=42,
            class_weight="balanced_subsample",
            min_samples_leaf=2,
        )
        results.append(
            self._evaluate_model(
                "random_forest", rf, X_train, X_test, y_train, y_test, enc
            )
        )

        cal_lr = CalibratedClassifierCV(
            estimator=LogisticRegression(max_iter=600, class_weight="balanced"),
            method="sigmoid",
            cv=3,
        )
        results.append(
            self._evaluate_model(
                "calibrated_logreg", cal_lr, X_train, X_test, y_train, y_test, enc
            )
        )

        xgb_result = self._try_xgboost(X_train, X_test, y_train, y_test, enc)
        if xgb_result is not None:
            results.append(xgb_result)

        return {
            "status": "ok",
            "sample_size": len(rows),
            "feature_count": len(vec.get_feature_names_out()),
            "class_distribution": dict(class_counts),
            "results": [
                {
                    "model": item.model,
                    "macro_f1": round(item.macro_f1, 4),
                    "accuracy": round(item.accuracy, 4),
                    "brier": round(item.brier, 4) if item.brier is not None else None,
                    "classes": item.classes,
                }
                for item in results
            ],
        }

    def _evaluate_model(
        self,
        name: str,
        model,
        X_train,
        X_test,
        y_train,
        y_test,
        enc: LabelEncoder,
    ) -> BenchmarkResult:
        model.fit(X_train, y_train)
        pred = model.predict(X_test)

        macro_f1 = f1_score(y_test, pred, average="macro")
        acc = accuracy_score(y_test, pred)
        brier = self._compute_multiclass_brier(model, X_test, y_test)

        return BenchmarkResult(
            model=name,
            macro_f1=float(macro_f1),
            accuracy=float(acc),
            brier=brier,
            classes=list(enc.classes_),
        )

    def _compute_multiclass_brier(self, model, X_test, y_test) -> float | None:
        if not hasattr(model, "predict_proba"):
            return None

        probs = model.predict_proba(X_test)
        if probs is None:
            return None

        # Handle binary or multiclass cases consistently.
        if isinstance(probs, list):
            return None

        brier_values = []
        class_count = probs.shape[1]
        for class_idx in range(class_count):
            true_binary = (y_test == class_idx).astype(int)
            brier_values.append(brier_score_loss(true_binary, probs[:, class_idx]))
        if not brier_values:
            return None
        return float(sum(brier_values) / len(brier_values))

    def _try_xgboost(
        self,
        X_train,
        X_test,
        y_train,
        y_test,
        enc: LabelEncoder,
    ) -> BenchmarkResult | None:
        try:
            from xgboost import XGBClassifier  # type: ignore
        except Exception:
            return None

        xgb = XGBClassifier(
            n_estimators=250,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob",
            eval_metric="mlogloss",
            random_state=42,
        )
        return self._evaluate_model(
            "xgboost", xgb, X_train, X_test, y_train, y_test, enc
        )
