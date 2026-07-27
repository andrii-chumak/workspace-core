# Model Card — Project Completion Date Forecasting

## Overview
Predicts how many days remain until a project finishes, given its current state.
Used to compute `predictedCompletionDate` for the `Prediction` entity.

- **Task type:** regression
- **Target:** `remaining_days` (days from "now" until the project actually completes)
- **Best algorithm (as of last training run):** LinearRegression
- **Trained:** 2026-07-27
- **Model version:** v1

## Validation metrics (holdout split)
| Model | MAE | RMSE | MAPE | R² |
|---|---|---|---|---|
| **LinearRegression (selected)** | 2.48 | 6.74 | **4.15%** | 0.981 |
| XGBoost | 4.48 | 7.74 | 9.39% | 0.975 |
| CatBoost | 5.08 | 8.27 | 11.50% | 0.972 |
| RandomForest | 6.02 | 9.30 | 13.19% | 0.964 |

Acceptance target (SMART-13): MAPE ≤ 15% or R² ≥ 0.8 — met by all four candidates.

## Input features (in this exact order)
1. `total_tasks` — total tasks known in the project as of now
2. `closed_tasks` — tasks already completed
3. `velocity` — tasks completed in the last 7 days
4. `num_developers` — distinct assignees on the project
5. `avg_task_duration_days` — average cycle time of completed tasks
6. `num_critical_tasks_open` — open tasks with priority Critical/High
7. `deadline_days_remaining` — days left until the planned deadline
8. `efficiency_index` — 0–1 process-quality score (default 0.5 if not tracked yet)
9. `historical_similar_avg_duration` — auto-computed by the model wrapper via a
   nearest-neighbour lookup on (`total_tasks`, `num_developers`); **do not pass this in manually**

## Training data
- Real: Kaggle *Agile Project Dataset 2024* (200 rows, project-level efficiency signal)
- Real: Mendeley Jira task log (~1200 rows, task duration / throughput calibration)
- Synthetic: ~4200 simulated project snapshots calibrated on the two real datasets above,
  including randomized capacity regime shifts and scope-creep events

## Known limitations
- Trained on synthetic/calibrated data, **not** on this team's own historical projects yet.
  Accuracy on real usage should be re-validated once real completed projects are available.
- Predictions are biased toward the mean on unusually long projects (>250 days).
- `efficiency_index` has no real data source yet in the app — currently a placeholder.

## Retraining
Source notebook: `notebooks/completion_date_forecasting.ipynb`.
Re-run end to end, then overwrite `models/completion_date/completion_date_model.joblib`
and update this card's metrics table and "Trained" date.
