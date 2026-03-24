from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


# ============================================================
# 08_make_article_tables.py
# Genera tablas de artículo y suplementarias para el análisis
# estación vs proxies espectrales Sentinel-2.
# ============================================================


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "data" / "processed"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "article_tables"
FALLBACK_INPUT_DIR = BASE_DIR
FALLBACK_OUTPUT_DIR = BASE_DIR / "article_tables"


# =========================
# Etiquetas de publicación
# =========================
TARGET_LABELS = {
    "et_base_out_mm_d": "ET diaria (mismo día)",
    "et_base_out_mm_d_w1_mean": "ET media 1 día",
    "et_base_out_mm_d_w3_mean": "ET media móvil 3 días (incluye día satelital)",
    "et_base_out_mm_d_w5_mean": "ET media móvil 5 días (incluye día satelital)",
    "et_base_out_mm_d_w7_mean": "ET media móvil 7 días (incluye día satelital)",
    "et_base_out_mm_d_w1_sum": "ET acumulada 1 día",
    "et_base_out_mm_d_w3_sum": "ET acumulada 3 días (incluye día satelital)",
    "et_base_out_mm_d_w5_sum": "ET acumulada 5 días (incluye día satelital)",
    "et_base_out_mm_d_w7_sum": "ET acumulada 7 días (incluye día satelital)",
}

TARGET_GROUPS = {
    "et_base_out_mm_d": "mismo_dia",
    "et_base_out_mm_d_w1_mean": "media_movil",
    "et_base_out_mm_d_w3_mean": "media_movil",
    "et_base_out_mm_d_w5_mean": "media_movil",
    "et_base_out_mm_d_w7_mean": "media_movil",
    "et_base_out_mm_d_w1_sum": "acumulada",
    "et_base_out_mm_d_w3_sum": "acumulada",
    "et_base_out_mm_d_w5_sum": "acumulada",
    "et_base_out_mm_d_w7_sum": "acumulada",
}

PREDICTOR_LABELS = {
    "NDVI_mean": "NDVI",
    "EVI_mean": "EVI",
    "SAVI_mean": "SAVI",
    "NDRE_mean": "NDRE",
}

PREDICTOR_ORDER = {
    "SAVI_mean": 1,
    "NDVI_mean": 2,
    "EVI_mean": 3,
    "NDRE_mean": 4,
}

ROUND_3_COLS = [
    "intercept",
    "slope",
    "r2",
    "rmse",
    "mae",
    "bias",
    "pearson_r",
    "spearman_rho",
    "value",
]


# =========================
# Utilidades
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
INPUT_CORR = INPUT_DIR / "station_sentinel_correlations.csv"
INPUT_REG = INPUT_DIR / "station_sentinel_simple_regressions.csv"
INPUT_BEST = INPUT_DIR / "station_sentinel_best_models.csv"

OUT_TABLE_BEST = OUTPUT_DIR / "table_01_best_models_article.csv"
OUT_TABLE_REGS = OUTPUT_DIR / "table_02_all_regressions_supplement.csv"
OUT_TABLE_CORRS = OUTPUT_DIR / "table_03_all_correlations_supplement.csv"
OUT_TABLE_DATASET = OUTPUT_DIR / "table_04_dataset_description.csv"


# =========================
# Lectura
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def load_csv(path: Path, parse_dates: bool = False) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)
    if parse_dates and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def round_numeric_columns(df: pd.DataFrame, cols: list[str], decimals: int = 3) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(decimals)
    return out


def add_publication_labels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "target" in out.columns:
        out["target_label"] = out["target"].map(TARGET_LABELS).fillna(out["target"])
        out["target_group"] = out["target"].map(TARGET_GROUPS).fillna("otra")

    if "predictor" in out.columns:
        out["predictor_label"] = out["predictor"].map(PREDICTOR_LABELS).fillna(out["predictor"])
        out["predictor_order"] = out["predictor"].map(PREDICTOR_ORDER).fillna(999)

    return out


def build_equation(intercept: float, slope: float, predictor_label: str) -> str:
    if pd.isna(intercept) or pd.isna(slope):
        return ""
    sign = "+" if slope >= 0 else "-"
    return f"ET = {intercept:.3f} {sign} {abs(slope):.3f} × {predictor_label}"


# =========================
# Tablas de artículo
# =========================
def build_best_models_table(best: pd.DataFrame) -> pd.DataFrame:
    out = add_publication_labels(best)
    out = out.sort_values(["r2", "rmse", "predictor_order"], ascending=[False, True, True]).reset_index(drop=True)
    out["article_rank"] = np.arange(1, len(out) + 1)
    out["equation"] = out.apply(
        lambda row: build_equation(row.get("intercept"), row.get("slope"), row.get("predictor_label", "x")),
        axis=1,
    )

    keep_cols = [
        "article_rank",
        "target",
        "target_label",
        "target_group",
        "predictor",
        "predictor_label",
        "n",
        "pearson_r",
        "spearman_rho",
        "r2",
        "rmse",
        "mae",
        "bias",
        "slope",
        "intercept",
        "equation",
        "interpretation_note",
    ]
    keep_cols = [c for c in keep_cols if c in out.columns]
    out = out[keep_cols]
    out = round_numeric_columns(out, ROUND_3_COLS, decimals=3)
    return out


def build_regression_supplement(regs: pd.DataFrame) -> pd.DataFrame:
    out = add_publication_labels(regs)
    out = out.sort_values(
        ["target", "r2", "rmse", "predictor_order"],
        ascending=[True, False, True, True]
    ).reset_index(drop=True)
    out["rank_within_target"] = out.groupby("target").cumcount() + 1
    out["equation"] = out.apply(
        lambda row: build_equation(row.get("intercept"), row.get("slope"), row.get("predictor_label", "x")),
        axis=1,
    )

    keep_cols = [
        "target",
        "target_label",
        "target_group",
        "rank_within_target",
        "predictor",
        "predictor_label",
        "n",
        "pearson_r",
        "spearman_rho",
        "r2",
        "rmse",
        "mae",
        "bias",
        "slope",
        "intercept",
        "equation",
    ]
    keep_cols = [c for c in keep_cols if c in out.columns]
    out = out[keep_cols]
    out = round_numeric_columns(out, ROUND_3_COLS, decimals=3)
    return out


def build_correlation_supplement(corrs: pd.DataFrame) -> pd.DataFrame:
    out = add_publication_labels(corrs)
    out = out.sort_values(
        ["target", "pearson_r", "predictor_order"],
        ascending=[True, False, True]
    ).reset_index(drop=True)
    out["rank_within_target"] = out.groupby("target").cumcount() + 1

    keep_cols = [
        "target",
        "target_label",
        "target_group",
        "rank_within_target",
        "predictor",
        "predictor_label",
        "n",
        "pearson_r",
        "spearman_rho",
    ]
    keep_cols = [c for c in keep_cols if c in out.columns]
    out = out[keep_cols]
    out = round_numeric_columns(out, ["pearson_r", "spearman_rho"], decimals=3)
    return out


def build_dataset_description(
    analysis: pd.DataFrame,
    corrs: pd.DataFrame,
    regs: pd.DataFrame,
    best: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict] = []

    date_min = analysis["date"].min() if "date" in analysis.columns and not analysis.empty else pd.NaT
    date_max = analysis["date"].max() if "date" in analysis.columns and not analysis.empty else pd.NaT

    def add_metric(metric: str, value) -> None:
        rows.append({"metric": metric, "value": value})

    add_metric("n_obs_analysis_ready", len(analysis))
    add_metric("date_start", date_min.strftime("%Y-%m-%d") if pd.notna(date_min) else "")
    add_metric("date_end", date_max.strftime("%Y-%m-%d") if pd.notna(date_max) else "")
    add_metric("n_correlations", len(corrs))
    add_metric("n_regressions", len(regs))
    add_metric("n_best_models", len(best))
    add_metric("n_predictors_tested", regs["predictor"].nunique() if "predictor" in regs.columns else np.nan)
    add_metric("n_targets_tested", regs["target"].nunique() if "target" in regs.columns else np.nan)

    numeric_summary_cols = [
        "et_base_out_mm_d",
        "NDVI_mean",
        "EVI_mean",
        "SAVI_mean",
        "NDRE_mean",
        "valid_pixel_pct",
        "cloudy_pixel_percentage",
    ]

    for col in numeric_summary_cols:
        if col not in analysis.columns:
            continue
        series = pd.to_numeric(analysis[col], errors="coerce")
        add_metric(f"{col}_mean", series.mean())
        add_metric(f"{col}_std", series.std(ddof=1))
        add_metric(f"{col}_min", series.min())
        add_metric(f"{col}_max", series.max())

    if "selected_from_duplicates" in analysis.columns:
        series = analysis["selected_from_duplicates"].fillna(False).astype(bool)
        add_metric("n_selected_from_duplicates_true", int(series.sum()))
        add_metric("n_selected_from_duplicates_false", int((~series).sum()))

    out = pd.DataFrame(rows)
    out = round_numeric_columns(out, ["value"], decimals=3)
    return out


# =========================
# Reporte
# =========================
def print_report(
    best_table: pd.DataFrame,
    regs_table: pd.DataFrame,
    corrs_table: pd.DataFrame,
    dataset_table: pd.DataFrame
) -> None:
    print("\n=== TABLAS DE ARTÍCULO: ESTACIÓN vs PROXIES SENTINEL-2 ===")
    print(f"Tabla principal (mejores modelos): {len(best_table)} filas")
    print(f"Tabla suplementaria regresiones:   {len(regs_table)} filas")
    print(f"Tabla suplementaria correlaciones: {len(corrs_table)} filas")
    print(f"Tabla descriptiva dataset:         {len(dataset_table)} filas")

    if not best_table.empty:
        show_cols = [
            "article_rank",
            "target_label",
            "predictor_label",
            "n",
            "pearson_r",
            "r2",
            "rmse",
            "interpretation_note",
        ]
        show_cols = [c for c in show_cols if c in best_table.columns]
        print("\nVista previa de mejores modelos:")
        print(best_table[show_cols].to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    analysis = load_csv(INPUT_ANALYSIS, parse_dates=True)
    corrs = load_csv(INPUT_CORR)
    regs = load_csv(INPUT_REG)
    best = load_csv(INPUT_BEST)

    best_table = build_best_models_table(best)
    regs_table = build_regression_supplement(regs)
    corrs_table = build_correlation_supplement(corrs)
    dataset_table = build_dataset_description(analysis, corrs, regs, best)

    best_table.to_csv(OUT_TABLE_BEST, index=False, encoding="utf-8")
    regs_table.to_csv(OUT_TABLE_REGS, index=False, encoding="utf-8")
    corrs_table.to_csv(OUT_TABLE_CORRS, index=False, encoding="utf-8")
    dataset_table.to_csv(OUT_TABLE_DATASET, index=False, encoding="utf-8")

    print_report(best_table, regs_table, corrs_table, dataset_table)

    print("\nArchivos generados:")
    print(f"- {OUT_TABLE_BEST}")
    print(f"- {OUT_TABLE_REGS}")
    print(f"- {OUT_TABLE_CORRS}")
    print(f"- {OUT_TABLE_DATASET}")


if __name__ == "__main__":
    main()