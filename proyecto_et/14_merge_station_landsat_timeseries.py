from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd


# ============================================================
# 14_merge_station_landsat_timeseries.py
# Cruza la serie diaria de estación con la serie diaria Landsat
# térmica y genera:
# - station_landsat_merged_daily.csv
# - station_landsat_analysis_ready.csv
# - station_landsat_merge_summary.csv
# ============================================================


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

DEFAULT_INPUT_DIR = BASE_DIR / "data" / "processed"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "processed"

FALLBACK_INPUT_DIR = BASE_DIR
FALLBACK_OUTPUT_DIR = BASE_DIR

INPUT_STATION_NAME = "station_daily_exterior_ready.csv"
INPUT_LANDSAT_NAME = "landsat_lst_daily_series.csv"

OUT_MERGED_DAILY_NAME = "station_landsat_merged_daily.csv"
OUT_ANALYSIS_NAME = "station_landsat_analysis_ready.csv"
OUT_SUMMARY_NAME = "station_landsat_merge_summary.csv"


# =========================
# Rutas
# =========================
def resolve_dirs() -> tuple[Path, Path]:
    if DEFAULT_INPUT_DIR.exists():
        input_dir = DEFAULT_INPUT_DIR
        output_dir = DEFAULT_OUTPUT_DIR
    else:
        input_dir = FALLBACK_INPUT_DIR
        output_dir = FALLBACK_OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir


INPUT_DIR, OUTPUT_DIR = resolve_dirs()

INPUT_STATION = INPUT_DIR / INPUT_STATION_NAME
INPUT_LANDSAT = INPUT_DIR / INPUT_LANDSAT_NAME

OUT_MERGED_DAILY = OUTPUT_DIR / OUT_MERGED_DAILY_NAME
OUT_ANALYSIS = OUTPUT_DIR / OUT_ANALYSIS_NAME
OUT_SUMMARY = OUTPUT_DIR / OUT_SUMMARY_NAME


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def to_numeric_if_exists(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def parse_bool_series(series: pd.Series, default: bool = False) -> pd.Series:
    mapped = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )
    return mapped.fillna(default)


# =========================
# Lectura
# =========================
def load_station(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)

    if "date" not in df.columns:
        raise ValueError("La tabla de estación no tiene columna 'date'.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    numeric_cols = [
        "pct_day_records",
        "et_base_out_mm_d",
        "et_out_daily",
        "temp_out_mean",
        "temp_out_min",
        "temp_out_max",
        "rh_out_mean",
        "rh_out_min",
        "rh_out_max",
        "rad_out_mean",
        "rad_out_max",
        "rad_acc_out_daily_max",
        "par_out_mean",
        "dli_out_max",
        "vpd_out_mean",
        "vpd_out_max",
        "dewpoint_out_mean",
        "et_rad_ratio",
    ]
    df = to_numeric_if_exists(df, numeric_cols)

    if "is_valid_day_analysis" in df.columns:
        df["is_valid_day_analysis"] = parse_bool_series(df["is_valid_day_analysis"], default=False)
    else:
        warnings.warn("No se encontró 'is_valid_day_analysis'. Se asumirá True para todos los días.")
        df["is_valid_day_analysis"] = True

    return df.sort_values("date").reset_index(drop=True)


def load_landsat(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)

    if "date" not in df.columns:
        raise ValueError("La tabla Landsat no tiene columna 'date'.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "datetime_utc" in df.columns:
        df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], errors="coerce")

    df = df.dropna(subset=["date"]).copy()

    numeric_cols = [
        "valid_pixel_pct",
        "wrs_path",
        "wrs_row",
        "n_obs_same_date",
        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "LST_C_mean_minus_median",
        "LST_C_cv_pct",
        "LST_K_mean",
        "LST_K_median",
        "LST_K_stdDev",
    ]
    df = to_numeric_if_exists(df, numeric_cols)

    if "is_valid_satellite_obs" in df.columns:
        df["is_valid_satellite_obs"] = parse_bool_series(df["is_valid_satellite_obs"], default=False)
    else:
        warnings.warn("No se encontró 'is_valid_satellite_obs'. Se asumirá True cuando LST_C_mean no sea NaN.")
        df["is_valid_satellite_obs"] = df["LST_C_mean"].notna()

    if "selected_from_duplicates" in df.columns:
        df["selected_from_duplicates"] = parse_bool_series(df["selected_from_duplicates"], default=False)
    else:
        df["selected_from_duplicates"] = False

    # Tomar solo columnas satelitales relevantes para evitar colisiones
    keep_cols = [
        "date",
        "datetime_utc",
        "image_id",
        "sensor_label",
        "spacecraft_id",
        "wrs_path",
        "wrs_row",
        "valid_pixel_pct",
        "is_valid_satellite_obs",
        "n_obs_same_date",
        "selected_from_duplicates",
        "selection_rule",
        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "LST_C_mean_minus_median",
        "LST_C_cv_pct",
        "LST_K_mean",
        "LST_K_median",
        "LST_K_stdDev",
    ]
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols].copy()

    return df.sort_values("date").reset_index(drop=True)


# =========================
# Merge base
# =========================
def build_daily_merge(station: pd.DataFrame, landsat: pd.DataFrame) -> pd.DataFrame:
    merged = station.merge(
        landsat,
        on="date",
        how="left",
        suffixes=("_station", "_landsat"),
    )

    merged["has_satellite_obs"] = merged["LST_C_mean"].notna() if "LST_C_mean" in merged.columns else False
    merged["is_merge_ready"] = (
        merged["is_valid_day_analysis"].fillna(False)
        & merged["is_valid_satellite_obs"].fillna(False)
    )

    merged["year"] = merged["date"].dt.year
    merged["month"] = merged["date"].dt.month
    merged["day"] = merged["date"].dt.day
    merged["year_month"] = merged["date"].dt.to_period("M").astype(str)
    merged["doy"] = merged["date"].dt.dayofyear
    merged["iso_year"] = merged["date"].dt.isocalendar().year.astype(int)
    merged["iso_week"] = merged["date"].dt.isocalendar().week.astype(int)
    merged["week_id"] = merged["iso_year"].astype(str) + "-W" + merged["iso_week"].astype(str).str.zfill(2)

    return merged.sort_values("date").reset_index(drop=True)


# =========================
# Ventanas móviles
# =========================
def add_antecedent_windows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replica la lógica del 06:
    ventanas hacia atrás incluyendo la fecha actual.
    """
    out = df.copy().sort_values("date").reset_index(drop=True)

    base_cols = [
        "et_base_out_mm_d",
        "temp_out_mean",
        "rh_out_mean",
        "rad_out_mean",
        "vpd_out_mean",
    ]

    for col in base_cols:
        if col not in out.columns:
            continue

        out[f"{col}_w1_mean"] = out[col]
        out[f"{col}_w1_sum"] = out[col] if col == "et_base_out_mm_d" else np.nan

        out[f"{col}_w3_mean"] = out[col].rolling(window=3, min_periods=1).mean()
        out[f"{col}_w5_mean"] = out[col].rolling(window=5, min_periods=1).mean()
        out[f"{col}_w7_mean"] = out[col].rolling(window=7, min_periods=1).mean()

        if col == "et_base_out_mm_d":
            out[f"{col}_w3_sum"] = out[col].rolling(window=3, min_periods=1).sum()
            out[f"{col}_w5_sum"] = out[col].rolling(window=5, min_periods=1).sum()
            out[f"{col}_w7_sum"] = out[col].rolling(window=7, min_periods=1).sum()

    return out


# =========================
# Tabla analítica final
# =========================
def build_analysis_table(merged_with_windows: pd.DataFrame) -> pd.DataFrame:
    df = merged_with_windows.copy()
    analysis = df.loc[df["is_merge_ready"]].copy()

    # Variables auxiliares térmicas
    if "LST_C_mean" in analysis.columns and "temp_out_mean" in analysis.columns:
        analysis["lst_minus_ta_mean_c"] = analysis["LST_C_mean"] - analysis["temp_out_mean"]

    if "LST_C_median" in analysis.columns and "temp_out_mean" in analysis.columns:
        analysis["lst_median_minus_ta_mean_c"] = analysis["LST_C_median"] - analysis["temp_out_mean"]

    if "et_base_out_mm_d" in analysis.columns and "LST_C_mean" in analysis.columns:
        analysis["et_lst_ratio"] = analysis["et_base_out_mm_d"] / analysis["LST_C_mean"].replace(0, np.nan)

    if "et_base_out_mm_d" in analysis.columns and "LST_C_median" in analysis.columns:
        analysis["et_lst_median_ratio"] = analysis["et_base_out_mm_d"] / analysis["LST_C_median"].replace(0, np.nan)

    ordered_cols = [
        "date",
        "year",
        "month",
        "day",
        "year_month",
        "doy",
        "iso_year",
        "iso_week",
        "week_id",

        "is_valid_day_analysis",
        "is_valid_satellite_obs",
        "has_satellite_obs",
        "is_merge_ready",

        "pct_day_records",
        "et_base_out_mm_d",
        "temp_out_mean",
        "rh_out_mean",
        "rad_out_mean",
        "vpd_out_mean",

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

        "image_id",
        "datetime_utc",
        "sensor_label",
        "spacecraft_id",
        "wrs_path",
        "wrs_row",
        "valid_pixel_pct",
        "selected_from_duplicates",
        "n_obs_same_date",

        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "LST_C_mean_minus_median",
        "LST_C_cv_pct",

        "LST_K_mean",
        "LST_K_median",
        "LST_K_stdDev",

        "lst_minus_ta_mean_c",
        "lst_median_minus_ta_mean_c",
        "et_lst_ratio",
        "et_lst_median_ratio",
    ]
    ordered_cols = [c for c in ordered_cols if c in analysis.columns]

    return analysis[ordered_cols].sort_values("date").reset_index(drop=True)


# =========================
# Resumen
# =========================
def build_summary(
    station: pd.DataFrame,
    landsat: pd.DataFrame,
    merged: pd.DataFrame,
    analysis: pd.DataFrame,
) -> pd.DataFrame:
    summary = pd.DataFrame(
        {
            "metric": [
                "n_station_days",
                "n_landsat_days",
                "n_merged_days",
                "n_days_with_satellite_obs",
                "n_analysis_ready_days",
                "mean_et_analysis",
                "mean_temp_analysis",
                "mean_vpd_analysis",
                "mean_lst_c_analysis",
                "median_lst_c_analysis",
                "mean_lst_minus_ta_analysis",
                "mean_valid_pixel_pct_analysis",
            ],
            "value": [
                len(station),
                len(landsat),
                len(merged),
                merged["has_satellite_obs"].sum() if "has_satellite_obs" in merged.columns else np.nan,
                len(analysis),
                analysis["et_base_out_mm_d"].mean() if "et_base_out_mm_d" in analysis.columns and not analysis.empty else np.nan,
                analysis["temp_out_mean"].mean() if "temp_out_mean" in analysis.columns and not analysis.empty else np.nan,
                analysis["vpd_out_mean"].mean() if "vpd_out_mean" in analysis.columns and not analysis.empty else np.nan,
                analysis["LST_C_mean"].mean() if "LST_C_mean" in analysis.columns and not analysis.empty else np.nan,
                analysis["LST_C_median"].median() if "LST_C_median" in analysis.columns and not analysis.empty else np.nan,
                analysis["lst_minus_ta_mean_c"].mean() if "lst_minus_ta_mean_c" in analysis.columns and not analysis.empty else np.nan,
                analysis["valid_pixel_pct"].mean() if "valid_pixel_pct" in analysis.columns and not analysis.empty else np.nan,
            ],
        }
    )
    return summary


# =========================
# Reporte
# =========================
def print_report(merged: pd.DataFrame, analysis: pd.DataFrame) -> None:
    print("\n=== MERGE ESTACIÓN + LANDSAT LST ===")
    print(f"Días totales de estación:        {len(merged)}")
    print(f"Días con observación satelital:  {int(merged['has_satellite_obs'].sum()) if 'has_satellite_obs' in merged.columns else 0}")
    print(f"Días listos para análisis:       {len(analysis)}")

    if not analysis.empty:
        if "et_base_out_mm_d" in analysis.columns:
            print(f"ET media en análisis:            {analysis['et_base_out_mm_d'].mean():.3f} mm/día")
        if "LST_C_mean" in analysis.columns:
            print(f"LST_C_mean media:                {analysis['LST_C_mean'].mean():.3f} °C")
        if "lst_minus_ta_mean_c" in analysis.columns:
            print(f"LST - Ta media:                  {analysis['lst_minus_ta_mean_c'].mean():.3f} °C")
        if "valid_pixel_pct" in analysis.columns:
            print(f"% píxeles válidos medio:         {analysis['valid_pixel_pct'].mean():.2f}")

        print("\nPrimeras 10 filas listas para análisis:")
        show_cols = [
            "date",
            "et_base_out_mm_d",
            "temp_out_mean",
            "vpd_out_mean",
            "valid_pixel_pct",
            "LST_C_mean",
            "LST_C_median",
            "LST_C_stdDev",
            "lst_minus_ta_mean_c",
        ]
        show_cols = [c for c in show_cols if c in analysis.columns]
        print(analysis[show_cols].head(10).to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    station = load_station(INPUT_STATION)
    landsat = load_landsat(INPUT_LANDSAT)

    merged = build_daily_merge(station, landsat)
    merged = add_antecedent_windows(merged)
    analysis = build_analysis_table(merged)
    summary = build_summary(station, landsat, merged, analysis)

    merged.to_csv(OUT_MERGED_DAILY, index=False, encoding="utf-8")
    analysis.to_csv(OUT_ANALYSIS, index=False, encoding="utf-8")
    summary.to_csv(OUT_SUMMARY, index=False, encoding="utf-8")

    print_report(merged, analysis)

    print("\nArchivos generados:")
    print(f"- {OUT_MERGED_DAILY}")
    print(f"- {OUT_ANALYSIS}")
    print(f"- {OUT_SUMMARY}")


if __name__ == "__main__":
    main()