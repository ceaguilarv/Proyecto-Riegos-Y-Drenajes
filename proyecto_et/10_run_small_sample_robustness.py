from __future__ import annotations

from pathlib import Path
from math import sqrt

import numpy as np
import pandas as pd


# ============================================================
# 10_run_small_sample_robustness.py
# Evalúa robustez del mejor modelo estación vs Sentinel-2 con:
# - leave-one-out
# - bootstrap
# - permutation test
# ============================================================


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "data" / "processed"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "processed"
FALLBACK_INPUT_DIR = BASE_DIR
FALLBACK_OUTPUT_DIR = BASE_DIR

PRIORITIZE_SAME_DAY_TARGET = True
SAME_DAY_TARGET = "et_base_out_mm_d"
N_BOOTSTRAP = 5000
N_PERMUTATIONS = 10000
RANDOM_SEED = 42


# =========================
# Rutas
# =========================
def resolve_input_output_dirs() -> tuple[Path, Path]:
    if DEFAULT_INPUT_DIR.exists():
        input_dir = DEFAULT_INPUT_DIR
        output_dir = DEFAULT_OUTPUT_DIR
    else:
        input_dir = FALLBACK_INPUT_DIR
        output_dir = FALLBACK_OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir


INPUT_DIR, OUTPUT_DIR = resolve_input_output_dirs()

INPUT_ANALYSIS = INPUT_DIR / "station_sentinel_analysis_ready.csv"
INPUT_BEST = INPUT_DIR / "station_sentinel_best_models.csv"

OUT_LOO = OUTPUT_DIR / "robustness_leave_one_out.csv"
OUT_BOOT = OUTPUT_DIR / "robustness_bootstrap_coefficients.csv"
OUT_BOOT_SUMMARY = OUTPUT_DIR / "robustness_bootstrap_summary.csv"
OUT_PERM = OUTPUT_DIR / "robustness_permutation_test.csv"
OUT_PERM_SUMMARY = OUTPUT_DIR / "robustness_permutation_summary.csv"
OUT_SUMMARY = OUTPUT_DIR / "robustness_summary.csv"


# =========================
# Utilidades numéricas
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def rankdata_average(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a)
    sorter = np.argsort(a, kind="mergesort")
    inv = np.empty(len(a), dtype=int)
    inv[sorter] = np.arange(len(a))
    a_sorted = a[sorter]

    obs = np.r_[True, a_sorted[1:] != a_sorted[:-1]]
    dense_rank = obs.cumsum() - 1

    counts = np.bincount(dense_rank)
    cumulative = np.cumsum(counts)
    starts = cumulative - counts
    avg_ranks = (starts + cumulative - 1) / 2.0 + 1.0

    return avg_ranks[dense_rank][inv]


def pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2:
        return np.nan
    x_std = np.std(x, ddof=0)
    y_std = np.std(y, ddof=0)
    if x_std == 0 or y_std == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2:
        return np.nan
    rx = rankdata_average(x)
    ry = rankdata_average(y)
    return pearson_r(rx, ry)


def fit_simple_linear_regression(x: np.ndarray, y: np.ndarray) -> dict:
    if len(x) < 2:
        return {
            "intercept": np.nan,
            "slope": np.nan,
            "r2": np.nan,
            "rmse": np.nan,
            "mae": np.nan,
            "bias": np.nan,
        }

    x_mean = np.mean(x)
    y_mean = np.mean(y)

    denom = np.sum((x - x_mean) ** 2)
    if denom == 0:
        return {
            "intercept": np.nan,
            "slope": np.nan,
            "r2": np.nan,
            "rmse": np.nan,
            "mae": np.nan,
            "bias": np.nan,
        }

    slope = np.sum((x - x_mean) * (y - y_mean)) / denom
    intercept = y_mean - slope * x_mean

    y_pred = intercept + slope * x
    residuals = y - y_pred

    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)

    r2 = np.nan if ss_tot == 0 else 1 - (ss_res / ss_tot)
    rmse = sqrt(np.mean((y - y_pred) ** 2))
    mae = np.mean(np.abs(y - y_pred))
    bias = np.mean(y_pred - y)

    return {
        "intercept": float(intercept),
        "slope": float(slope),
        "r2": float(r2),
        "rmse": float(rmse),
        "mae": float(mae),
        "bias": float(bias),
    }


def summarize_xy(x: np.ndarray, y: np.ndarray) -> dict:
    reg = fit_simple_linear_regression(x, y)
    return {
        "n": int(len(x)),
        "intercept": reg["intercept"],
        "slope": reg["slope"],
        "r2": reg["r2"],
        "rmse": reg["rmse"],
        "mae": reg["mae"],
        "bias": reg["bias"],
        "pearson_r": pearson_r(x, y),
        "spearman_rho": spearman_rho(x, y),
    }


# =========================
# Lectura
# =========================
def load_analysis_table(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)

    if "date" not in df.columns:
        raise ValueError("El archivo no tiene columna 'date'.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    numeric_cols = [
        "et_base_out_mm_d",
        "et_base_out_mm_d_w1_mean",
        "et_base_out_mm_d_w3_mean",
        "et_base_out_mm_d_w5_mean",
        "et_base_out_mm_d_w7_mean",
        "et_base_out_mm_d_w1_sum",
        "et_base_out_mm_d_w3_sum",
        "et_base_out_mm_d_w5_sum",
        "et_base_out_mm_d_w7_sum",
        "NDVI_mean",
        "EVI_mean",
        "SAVI_mean",
        "NDRE_mean",
        "valid_pixel_pct",
        "cloudy_pixel_percentage",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values("date").reset_index(drop=True)


def load_best_models(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)

    numeric_cols = [
        "n", "intercept", "slope", "r2", "rmse", "mae", "bias", "pearson_r", "spearman_rho"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# =========================
# Selección del modelo focal
# =========================
def select_focal_model(best: pd.DataFrame) -> pd.Series:
    if best.empty:
        raise ValueError("station_sentinel_best_models.csv está vacío.")

    candidates = best.copy()
    if PRIORITIZE_SAME_DAY_TARGET and "target" in candidates.columns:
        same_day = candidates.loc[candidates["target"] == SAME_DAY_TARGET].copy()
        if not same_day.empty:
            candidates = same_day

    candidates = candidates.sort_values(["r2", "rmse"], ascending=[False, True]).reset_index(drop=True)
    return candidates.iloc[0]


def build_model_dataframe(analysis: pd.DataFrame, target: str, predictor: str) -> pd.DataFrame:
    needed = ["date", target, predictor]
    missing = [c for c in needed if c not in analysis.columns]
    if missing:
        raise ValueError(f"Faltan columnas en analysis_ready: {missing}")

    sub = analysis[needed].dropna().copy()
    if len(sub) < 3:
        raise ValueError("No hay suficientes observaciones válidas para robustez (n < 3).")

    return sub.sort_values("date").reset_index(drop=True)


# =========================
# Robustez
# =========================
def run_leave_one_out(df_model: pd.DataFrame, target: str, predictor: str) -> pd.DataFrame:
    rows = []
    x_all = df_model[predictor].to_numpy(dtype=float)
    y_all = df_model[target].to_numpy(dtype=float)
    full_stats = summarize_xy(x_all, y_all)

    for i in range(len(df_model)):
        sub = df_model.drop(index=i).reset_index(drop=True)
        x = sub[predictor].to_numpy(dtype=float)
        y = sub[target].to_numpy(dtype=float)
        stats = summarize_xy(x, y)

        rows.append(
            {
                "target": target,
                "predictor": predictor,
                "omitted_index": int(i),
                "omitted_date": pd.to_datetime(df_model.loc[i, "date"]).strftime("%Y-%m-%d"),
                "omitted_x": float(df_model.loc[i, predictor]),
                "omitted_y": float(df_model.loc[i, target]),
                "n_refit": int(stats["n"]),
                "intercept": stats["intercept"],
                "slope": stats["slope"],
                "r2": stats["r2"],
                "rmse": stats["rmse"],
                "mae": stats["mae"],
                "bias": stats["bias"],
                "pearson_r": stats["pearson_r"],
                "spearman_rho": stats["spearman_rho"],
                "delta_r2_vs_full": stats["r2"] - full_stats["r2"],
                "delta_pearson_r_vs_full": stats["pearson_r"] - full_stats["pearson_r"],
                "delta_slope_vs_full": stats["slope"] - full_stats["slope"],
                "abs_delta_r2_vs_full": abs(stats["r2"] - full_stats["r2"]),
                "abs_delta_pearson_r_vs_full": abs(stats["pearson_r"] - full_stats["pearson_r"]),
                "abs_delta_slope_vs_full": abs(stats["slope"] - full_stats["slope"]),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["abs_delta_r2_vs_full", "abs_delta_pearson_r_vs_full"], ascending=[False, False])
    return out.reset_index(drop=True)


def run_bootstrap(df_model: pd.DataFrame, target: str, predictor: str, n_boot: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(df_model)
    x_all = df_model[predictor].to_numpy(dtype=float)
    y_all = df_model[target].to_numpy(dtype=float)

    rows = []
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        x = x_all[idx]
        y = y_all[idx]
        stats = summarize_xy(x, y)
        stats.update(
            {
                "target": target,
                "predictor": predictor,
                "iteration": i + 1,
                "unique_obs_in_resample": int(np.unique(idx).size),
            }
        )
        rows.append(stats)

    return pd.DataFrame(rows)


def summarize_bootstrap(boot: pd.DataFrame) -> pd.DataFrame:
    metrics = ["intercept", "slope", "r2", "rmse", "mae", "bias", "pearson_r", "spearman_rho"]
    rows = []
    for metric in metrics:
        if metric not in boot.columns:
            continue
        s = pd.to_numeric(boot[metric], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append(
            {
                "metric": metric,
                "n_boot_valid": int(s.size),
                "mean": float(s.mean()),
                "std": float(s.std(ddof=1)) if s.size > 1 else np.nan,
                "median": float(s.median()),
                "p02_5": float(np.quantile(s, 0.025)),
                "p05": float(np.quantile(s, 0.05)),
                "p25": float(np.quantile(s, 0.25)),
                "p75": float(np.quantile(s, 0.75)),
                "p95": float(np.quantile(s, 0.95)),
                "p97_5": float(np.quantile(s, 0.975)),
            }
        )

    return pd.DataFrame(rows)


def run_permutation_test(
    df_model: pd.DataFrame,
    target: str,
    predictor: str,
    n_perm: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    x = df_model[predictor].to_numpy(dtype=float)
    y = df_model[target].to_numpy(dtype=float)

    observed_r = pearson_r(x, y)
    observed_abs_r = abs(observed_r)
    observed_r2 = observed_r ** 2 if pd.notna(observed_r) else np.nan

    rows = []
    extreme_count = 0
    for i in range(n_perm):
        y_perm = rng.permutation(y)
        r_perm = pearson_r(x, y_perm)
        r2_perm = r_perm ** 2 if pd.notna(r_perm) else np.nan
        abs_r_perm = abs(r_perm) if pd.notna(r_perm) else np.nan

        if pd.notna(abs_r_perm) and abs_r_perm >= observed_abs_r:
            extreme_count += 1

        rows.append(
            {
                "target": target,
                "predictor": predictor,
                "iteration": i + 1,
                "pearson_r_perm": r_perm,
                "abs_pearson_r_perm": abs_r_perm,
                "r2_perm": r2_perm,
            }
        )

    perm_df = pd.DataFrame(rows)
    p_empirical = (extreme_count + 1) / (n_perm + 1)

    summary = pd.DataFrame(
        [
            {
                "target": target,
                "predictor": predictor,
                "n": len(df_model),
                "n_permutations": n_perm,
                "observed_pearson_r": observed_r,
                "observed_abs_pearson_r": observed_abs_r,
                "observed_r2_from_r": observed_r2,
                "null_mean_abs_r": float(perm_df["abs_pearson_r_perm"].mean()),
                "null_p95_abs_r": float(np.quantile(perm_df["abs_pearson_r_perm"].dropna(), 0.95)),
                "null_p99_abs_r": float(np.quantile(perm_df["abs_pearson_r_perm"].dropna(), 0.99)),
                "empirical_p_two_sided": float(p_empirical),
            }
        ]
    )
    return perm_df, summary


# =========================
# Resumen integrado
# =========================
def build_summary_table(
    focal_model: pd.Series,
    df_model: pd.DataFrame,
    full_stats: dict,
    loo: pd.DataFrame,
    boot_summary: pd.DataFrame,
    perm_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    def add(metric: str, value) -> None:
        rows.append({"metric": metric, "value": value})

    add("target", focal_model.get("target", ""))
    add("predictor", focal_model.get("predictor", ""))
    add("n_full", int(len(df_model)))
    add("date_start", df_model["date"].min().strftime("%Y-%m-%d"))
    add("date_end", df_model["date"].max().strftime("%Y-%m-%d"))
    add("full_intercept", full_stats["intercept"])
    add("full_slope", full_stats["slope"])
    add("full_r2", full_stats["r2"])
    add("full_rmse", full_stats["rmse"])
    add("full_mae", full_stats["mae"])
    add("full_bias", full_stats["bias"])
    add("full_pearson_r", full_stats["pearson_r"])
    add("full_spearman_rho", full_stats["spearman_rho"])

    if not loo.empty:
        add("loo_min_r2", loo["r2"].min())
        add("loo_max_r2", loo["r2"].max())
        add("loo_min_pearson_r", loo["pearson_r"].min())
        add("loo_max_pearson_r", loo["pearson_r"].max())
        add("loo_max_abs_delta_r2", loo["abs_delta_r2_vs_full"].max())
        add("loo_max_abs_delta_pearson_r", loo["abs_delta_pearson_r_vs_full"].max())
        most_influential = loo.iloc[0]
        add("loo_most_influential_date", most_influential["omitted_date"])
        add("loo_most_influential_abs_delta_r2", most_influential["abs_delta_r2_vs_full"])
        add("loo_most_influential_abs_delta_r", most_influential["abs_delta_pearson_r_vs_full"])

    if not boot_summary.empty:
        for metric in ["slope", "r2", "pearson_r"]:
            sub = boot_summary.loc[boot_summary["metric"] == metric]
            if not sub.empty:
                row = sub.iloc[0]
                add(f"bootstrap_{metric}_mean", row["mean"])
                add(f"bootstrap_{metric}_p02_5", row["p02_5"])
                add(f"bootstrap_{metric}_p97_5", row["p97_5"])

    if not perm_summary.empty:
        row = perm_summary.iloc[0]
        add("permutation_observed_abs_r", row["observed_abs_pearson_r"])
        add("permutation_null_mean_abs_r", row["null_mean_abs_r"])
        add("permutation_null_p95_abs_r", row["null_p95_abs_r"])
        add("permutation_empirical_p_two_sided", row["empirical_p_two_sided"])

    return pd.DataFrame(rows)


# =========================
# Reporte
# =========================
def print_report(
    focal_model: pd.Series,
    full_stats: dict,
    loo: pd.DataFrame,
    boot_summary: pd.DataFrame,
    perm_summary: pd.DataFrame,
) -> None:
    print("\n=== ROBUSTEZ PARA MUESTRA PEQUEÑA ===")
    print(f"Modelo focal: {focal_model['target']} ~ {focal_model['predictor']}")
    print(f"n = {full_stats['n']}")
    print(
        f"Modelo completo -> r = {full_stats['pearson_r']:.3f}, "
        f"R² = {full_stats['r2']:.3f}, pendiente = {full_stats['slope']:.3f}, "
        f"RMSE = {full_stats['rmse']:.3f}"
    )

    if not loo.empty:
        print(
            f"Leave-one-out -> r en [{loo['pearson_r'].min():.3f}, {loo['pearson_r'].max():.3f}], "
            f"R² en [{loo['r2'].min():.3f}, {loo['r2'].max():.3f}]"
        )
        top = loo.iloc[0]
        print(
            f"Fecha más influyente: {top['omitted_date']} "
            f"(ΔR² abs = {top['abs_delta_r2_vs_full']:.3f}, "
            f"Δr abs = {top['abs_delta_pearson_r_vs_full']:.3f})"
        )

    if not boot_summary.empty:
        for metric in ["slope", "r2", "pearson_r"]:
            sub = boot_summary.loc[boot_summary["metric"] == metric]
            if not sub.empty:
                row = sub.iloc[0]
                print(
                    f"Bootstrap {metric} -> media = {row['mean']:.3f}, "
                    f"IC percentil 95% = [{row['p02_5']:.3f}, {row['p97_5']:.3f}]"
                )

    if not perm_summary.empty:
        row = perm_summary.iloc[0]
        print(
            f"Permutation test -> p empírico bilateral = {row['empirical_p_two_sided']:.4f}, "
            f"|r| observado = {row['observed_abs_pearson_r']:.3f}, "
            f"p95 nulo = {row['null_p95_abs_r']:.3f}"
        )

    print("\nArchivos generados:")
    print(f"- {OUT_LOO}")
    print(f"- {OUT_BOOT}")
    print(f"- {OUT_BOOT_SUMMARY}")
    print(f"- {OUT_PERM}")
    print(f"- {OUT_PERM_SUMMARY}")
    print(f"- {OUT_SUMMARY}")


# =========================
# Main
# =========================
def main() -> None:
    analysis = load_analysis_table(INPUT_ANALYSIS)
    best = load_best_models(INPUT_BEST)
    focal_model = select_focal_model(best)

    target = str(focal_model["target"])
    predictor = str(focal_model["predictor"])

    df_model = build_model_dataframe(analysis, target, predictor)
    x = df_model[predictor].to_numpy(dtype=float)
    y = df_model[target].to_numpy(dtype=float)
    full_stats = summarize_xy(x, y)

    loo = run_leave_one_out(df_model, target, predictor)
    boot = run_bootstrap(df_model, target, predictor, n_boot=N_BOOTSTRAP, seed=RANDOM_SEED)
    boot_summary = summarize_bootstrap(boot)
    perm, perm_summary = run_permutation_test(
        df_model,
        target,
        predictor,
        n_perm=N_PERMUTATIONS,
        seed=RANDOM_SEED,
    )
    summary = build_summary_table(focal_model, df_model, full_stats, loo, boot_summary, perm_summary)

    loo.to_csv(OUT_LOO, index=False, encoding="utf-8")
    boot.to_csv(OUT_BOOT, index=False, encoding="utf-8")
    boot_summary.to_csv(OUT_BOOT_SUMMARY, index=False, encoding="utf-8")
    perm.to_csv(OUT_PERM, index=False, encoding="utf-8")
    perm_summary.to_csv(OUT_PERM_SUMMARY, index=False, encoding="utf-8")
    summary.to_csv(OUT_SUMMARY, index=False, encoding="utf-8")

    print_report(focal_model, full_stats, loo, boot_summary, perm_summary)


if __name__ == "__main__":
    main()