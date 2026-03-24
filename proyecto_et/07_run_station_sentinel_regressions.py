from __future__ import annotations

from pathlib import Path
from math import sqrt

import numpy as np
import pandas as pd


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_ANALYSIS = BASE_DIR / "data" / "processed" / "station_sentinel_analysis_ready.csv"

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CORRELATIONS = OUTPUT_DIR / "station_sentinel_correlations.csv"
OUT_REGRESSIONS = OUTPUT_DIR / "station_sentinel_simple_regressions.csv"
OUT_BEST_MODELS = OUTPUT_DIR / "station_sentinel_best_models.csv"


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def rankdata_average(a: np.ndarray) -> np.ndarray:
    """
    Ranking con promedio para empates, estilo Spearman.
    """
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
    """
    Ajusta y = a + b*x
    """
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
        "temp_out_mean_w1_mean",
        "temp_out_mean_w3_mean",
        "temp_out_mean_w5_mean",
        "temp_out_mean_w7_mean",
        "rh_out_mean_w1_mean",
        "rh_out_mean_w3_mean",
        "rh_out_mean_w5_mean",
        "rh_out_mean_w7_mean",
        "rad_out_mean_w1_mean",
        "rad_out_mean_w3_mean",
        "rad_out_mean_w5_mean",
        "rad_out_mean_w7_mean",
        "vpd_out_mean_w1_mean",
        "vpd_out_mean_w3_mean",
        "vpd_out_mean_w5_mean",
        "vpd_out_mean_w7_mean",
        "NDVI_mean",
        "EVI_mean",
        "SAVI_mean",
        "NDRE_mean",
        "valid_pixel_pct",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values("date").reset_index(drop=True)


# =========================
# Diseño del análisis
# =========================
def build_candidate_pairs() -> list[tuple[str, str, str]]:
    """
    Devuelve tuplas:
    (target_station, predictor_satellite, family_name)
    """
    targets = [
        "et_base_out_mm_d",
        "et_base_out_mm_d_w3_mean",
        "et_base_out_mm_d_w5_mean",
        "et_base_out_mm_d_w7_mean",
        "et_base_out_mm_d_w3_sum",
        "et_base_out_mm_d_w5_sum",
        "et_base_out_mm_d_w7_sum",
    ]

    predictors = [
        "NDVI_mean",
        "EVI_mean",
        "SAVI_mean",
        "NDRE_mean",
    ]

    pairs = []
    for t in targets:
        for p in predictors:
            pairs.append((t, p, "station_vs_satellite"))
    return pairs


# =========================
# Correlaciones
# =========================
def run_correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for target, predictor, family in build_candidate_pairs():
        if target not in df.columns or predictor not in df.columns:
            continue

        sub = df[[target, predictor]].dropna().copy()
        n = len(sub)
        if n < 3:
            continue

        x = sub[predictor].to_numpy(dtype=float)
        y = sub[target].to_numpy(dtype=float)

        rows.append(
            {
                "family": family,
                "target": target,
                "predictor": predictor,
                "n": n,
                "pearson_r": pearson_r(x, y),
                "spearman_rho": spearman_rho(x, y),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(
            ["target", "pearson_r"],
            ascending=[True, False]
        ).reset_index(drop=True)
    return out


# =========================
# Regresiones simples
# =========================
def run_simple_regressions(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for target, predictor, family in build_candidate_pairs():
        if target not in df.columns or predictor not in df.columns:
            continue

        sub = df[[target, predictor]].dropna().copy()
        n = len(sub)
        if n < 3:
            continue

        x = sub[predictor].to_numpy(dtype=float)
        y = sub[target].to_numpy(dtype=float)

        stats = fit_simple_linear_regression(x, y)

        rows.append(
            {
                "family": family,
                "target": target,
                "predictor": predictor,
                "n": n,
                "intercept": stats["intercept"],
                "slope": stats["slope"],
                "r2": stats["r2"],
                "rmse": stats["rmse"],
                "mae": stats["mae"],
                "bias": stats["bias"],
                "pearson_r": pearson_r(x, y),
                "spearman_rho": spearman_rho(x, y),
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(
            ["target", "r2", "rmse"],
            ascending=[True, False, True]
        ).reset_index(drop=True)
    return out


# =========================
# Mejores modelos
# =========================
def select_best_models(regs: pd.DataFrame) -> pd.DataFrame:
    if regs.empty:
        return regs

    best = (
        regs.sort_values(["target", "r2", "rmse"], ascending=[True, False, True])
        .groupby("target", as_index=False)
        .first()
    )

    best["interpretation_note"] = np.where(
        best["r2"] >= 0.50,
        "relacion relativamente fuerte",
        np.where(
            best["r2"] >= 0.25,
            "relacion moderada",
            "relacion debil o exploratoria",
        ),
    )

    return best.sort_values("r2", ascending=False).reset_index(drop=True)


# =========================
# Reporte
# =========================
def print_report(corrs: pd.DataFrame, regs: pd.DataFrame, best: pd.DataFrame) -> None:
    print("\n=== ANÁLISIS ESTACIÓN vs PROXIES SATELITALES ===")

    print(f"Correlaciones calculadas:    {len(corrs)}")
    print(f"Regresiones calculadas:      {len(regs)}")
    print(f"Mejores modelos seleccionados: {len(best)}")

    if not best.empty:
        print("\nTop 10 mejores modelos por R²:")
        show_cols = [
            "target",
            "predictor",
            "n",
            "slope",
            "r2",
            "rmse",
            "mae",
            "pearson_r",
            "spearman_rho",
            "interpretation_note",
        ]
        show_cols = [c for c in show_cols if c in best.columns]
        print(best[show_cols].head(10).to_string(index=False))

    if not corrs.empty:
        print("\nTop 10 correlaciones por Pearson:")
        top_corrs = corrs.sort_values("pearson_r", ascending=False).head(10)
        show_cols = ["target", "predictor", "n", "pearson_r", "spearman_rho"]
        show_cols = [c for c in show_cols if c in top_corrs.columns]
        print(top_corrs[show_cols].to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    df = load_analysis_table(INPUT_ANALYSIS)

    corrs = run_correlations(df)
    regs = run_simple_regressions(df)
    best = select_best_models(regs)

    corrs.to_csv(OUT_CORRELATIONS, index=False, encoding="utf-8")
    regs.to_csv(OUT_REGRESSIONS, index=False, encoding="utf-8")
    best.to_csv(OUT_BEST_MODELS, index=False, encoding="utf-8")

    print_report(corrs, regs, best)

    print("\nArchivos generados:")
    print(f"- {OUT_CORRELATIONS}")
    print(f"- {OUT_REGRESSIONS}")
    print(f"- {OUT_BEST_MODELS}")


if __name__ == "__main__":
    main()