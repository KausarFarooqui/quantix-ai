"""AutoML agent node — the one agent type that trains real models rather
than reasoning in text. The LLM's only job here is picking the target
column from the user's request (a small, tool-forced call); everything
after that — feature preparation, candidate model training,
cross-validation, model selection, feature importances — is deterministic
scikit-learn, not an LLM guess.

Deliberately modest in scope for this milestone: numeric + low-cardinality
categorical features only, two candidate model families, k-fold
cross-validation for model selection. Real AutoML platforms (proper
feature engineering, hyperparameter search, more model families) are a
tracked follow-up — see ADR-0004.
"""

from __future__ import annotations

import json
import time

import anyio
import numpy as np
import pandas as pd

from quantix_api.application.interfaces.agent_graph import (
    AgentRunContext,
    AgentRunResult,
    AgentState,
)
from quantix_api.application.interfaces.llm_client import LLMClient, LLMMessage, ToolSpec
from quantix_api.domain.entities.agent_run import AgentRunStatus, AgentType

MAX_CATEGORICAL_CARDINALITY = 15
MAX_TRAINING_ROWS = 5000
CV_FOLDS = 5


class InsufficientDataError(ValueError):
    pass


class AutoMLAgentNode:
    def __init__(self, *, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def run(self, *, state: AgentState, context: AgentRunContext) -> AgentRunResult:
        started = time.monotonic()
        dataset = context.dataset
        if dataset is None or not dataset.storage_uri:
            return AgentRunResult(
                agent_type=AgentType.AUTOML,
                status=AgentRunStatus.FAILED,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_message="No dataset is attached to this conversation to train a model on.",
            )

        try:
            table = await anyio.to_thread.run_sync(
                lambda: context.dataset_storage.read_preview(
                    storage_uri=dataset.storage_uri, limit=MAX_TRAINING_ROWS
                )
            )
            dataframe = table.to_pandas()

            target_column, prompt_tokens, completion_tokens = await self._select_target_column(
                state=state, columns=list(dataframe.columns)
            )
            summary = await anyio.to_thread.run_sync(lambda: _train(dataframe, target_column))
        except Exception as exc:  # noqa: BLE001 — converted to a FAILED AgentRunResult
            return AgentRunResult(
                agent_type=AgentType.AUTOML,
                status=AgentRunStatus.FAILED,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_message=str(exc),
            )

        return AgentRunResult(
            agent_type=AgentType.AUTOML,
            status=AgentRunStatus.SUCCEEDED,
            output_summary=summary,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def _select_target_column(
        self, *, state: AgentState, columns: list[str]
    ) -> tuple[str, int, int]:
        last_user_turn = next((t.content for t in reversed(state.history) if t.role == "user"), "")
        tool = ToolSpec(
            name="select_target_column",
            description="Choose which dataset column should be predicted.",
            parameters={
                "type": "object",
                "properties": {"column": {"type": "string", "enum": columns}},
                "required": ["column"],
            },
        )
        response = await self._llm_client.complete(
            messages=[
                LLMMessage(
                    role="user",
                    content=f"Available columns: {', '.join(columns)}\n\nUser request: {last_user_turn}",
                )
            ],
            system="You select which column of a tabular dataset a predictive model should "
            "target, based on the user's request. Pick the column the user most plausibly wants "
            "to predict or understand the drivers of.",
            tools=[tool],
            tool_choice="any",
            max_tokens=256,
        )
        if not response.tool_calls:
            raise InsufficientDataError("Could not determine a target column from the request.")
        column = response.tool_calls[0].arguments.get("column")
        if column not in columns:
            raise InsufficientDataError(f"'{column}' is not a column in this dataset.")
        return column, response.usage.prompt_tokens, response.usage.completion_tokens


def _train(dataframe: pd.DataFrame, target_column: str) -> str:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import LabelEncoder

    working = dataframe.dropna(subset=[target_column]).copy()
    if len(working) < CV_FOLDS * 2:
        raise InsufficientDataError(
            f"Only {len(working)} rows have a non-null '{target_column}' — too few to train on."
        )

    target = working.pop(target_column)
    is_classification = target.dtype == object or target.nunique() <= 20

    feature_frame = _prepare_features(working)
    if feature_frame.shape[1] == 0:
        raise InsufficientDataError("No usable numeric/categorical feature columns remain.")

    if is_classification:
        target_encoded = LabelEncoder().fit_transform(target.astype(str))
        candidates = {
            "logistic_regression": LogisticRegression(max_iter=1000),
            "random_forest": RandomForestClassifier(n_estimators=100, random_state=42),
        }
        scoring = "accuracy"
    else:
        target_encoded = target.to_numpy(dtype=float)
        candidates = {
            "linear_regression": LinearRegression(),
            "random_forest": RandomForestRegressor(n_estimators=100, random_state=42),
        }
        scoring = "r2"

    folds = min(CV_FOLDS, len(working) // 2)
    scores: dict[str, float] = {}
    for name, model in candidates.items():
        cv_scores = cross_val_score(model, feature_frame, target_encoded, cv=folds, scoring=scoring)
        scores[name] = float(np.mean(cv_scores))

    best_name = max(scores, key=scores.get)
    best_model = candidates[best_name]
    best_model.fit(feature_frame, target_encoded)

    importances = _feature_importances(best_model, feature_frame.columns)
    top_features = sorted(importances.items(), key=lambda kv: abs(kv[1]), reverse=True)[:8]

    problem_type = "classification" if is_classification else "regression"
    lines = [
        f"Trained {problem_type} models predicting '{target_column}' on {len(working)} rows.",
        f"Best model: {best_name} ({scoring}={scores[best_name]:.3f}, {CV_FOLDS}-fold CV).",
        "Candidate scores: " + ", ".join(f"{name}={score:.3f}" for name, score in scores.items()),
        "Top features by importance: " + ", ".join(f"{name} ({value:.3f})" for name, value in top_features),
    ]
    structured = {
        "target_column": target_column,
        "problem_type": problem_type,
        "best_model": best_name,
        "scoring_metric": scoring,
        "scores": scores,
        "feature_importances": dict(top_features),
    }
    lines.append(f"structured_result={json.dumps(structured)}")
    return "\n".join(lines)


def _prepare_features(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame.select_dtypes(include=["number", "bool"]).copy()
    numeric = numeric.fillna(numeric.median(numeric_only=True))

    categorical_columns = [
        column
        for column in frame.select_dtypes(include=["object", "category"]).columns
        if frame[column].nunique() <= MAX_CATEGORICAL_CARDINALITY
    ]
    if categorical_columns:
        dummies = pd.get_dummies(frame[categorical_columns].astype(str), dummy_na=False)
        return pd.concat([numeric, dummies], axis=1)
    return numeric


def _feature_importances(model, feature_names) -> dict[str, float]:  # noqa: ANN001
    if hasattr(model, "feature_importances_"):
        return dict(zip(feature_names, (float(v) for v in model.feature_importances_), strict=True))
    if hasattr(model, "coef_"):
        coefficients = np.ravel(model.coef_)
        return dict(zip(feature_names, (float(v) for v in coefficients), strict=True))
    return {}
