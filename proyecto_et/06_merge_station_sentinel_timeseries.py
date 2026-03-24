from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_STATION = BASE_DIR / "data" / "processed" / "station_daily_exterior_ready.csv"
INPUT_S2 = BASE_DIR / "data" / "processed" / "sentinel2_daily_series.csv"

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_MERGED_DAILY = OUTPUT_DIR / "station_sentinel_daily_merged.csv"
OUT_MERGED_ANALYSIS = OUTPUT_DIR / "station_sentinel_analysis_ready.csv"
OUT_MERGED_SUMMARY = OUTPUT_DIR / "station_sentinel_merge_summary.csv"


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def to_numeric_if_exists(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


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
    ]
    df = to_numeric_if_exists(df, numeric_cols)

    if "is_valid_day_analysis" in df.columns:
        df["is_valid_day_analysis"] = (
            df["is_valid_day_analysis"].astype(str).str.lower().map({"true": True, "false": False})
        )
    else:
        df["is_valid_day_analysis"] = True

    return df.sort_values("date").reset_index(drop=True)


def load_sentinel(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError("La tabla satelital no tiene columna 'date'.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    numeric_cols = [
        "cloudy_pixel_percentage",
        "valid_pixel_pct",
        "NDVI_mean", "NDVI_median", "NDVI_stdDev",
        "EVI_mean", "EVI_median", "EVI_stdDev",
        "SAVI_mean", "SAVI_median", "SAVI_stdDev",
        "NDRE_mean", "NDRE_median", "NDRE_stdDev",
    ]
    df = to_numeric_if_exists(df, numeric_cols)

    if "is_valid_satellite_obs" in df.columns:
        df["is_valid_satellite_obs"] = (
            df["is_valid_satellite_obs"].astype(str).str.lower().map({"true": True, "false": False})
        )
    else:
        df["is_valid_satellite_obs"] = True

    return df.sort_values("date").reset_index(drop=True)


# =========================
# Merge base
# =========================
def build_daily_merge(station: pd.DataFrame, s2: pd.DataFrame) -> pd.DataFrame:
    merged = station.merge(
        s2,
        on="date",
        how="left",
        suffixes=("_station", "_s2"),
    )

    merged["has_satellite_obs"] = merged["NDVI_mean"].notna() if "NDVI_mean" in merged.columns else False
    merged["is_merge_ready"] = merged["is_valid_day_analysis"].fillna(False) & merged["is_valid_satellite_obs"].fillna(False)

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
# Ventanas móviles previas a la fecha satelital
# =========================
def add_antecedent_windows(df: pd.DataFrame) -> pd.DataFrame:
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

        # día actual
        out[f"{col}_w1_mean"] = out[col]
        out[f"{col}_w1_sum"] = out[col] if col == "et_base_out_mm_d" else np.nan

        # ventanas hacia atrás incluyendo fecha actual
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

    # Variables auxiliares para análisis rápidos
    if "NDVI_mean" in analysis.columns and "et_base_out_mm_d" in analysis.columns:
        analysis["et_ndvi_ratio"] = analysis["et_base_out_mm_d"] / analysis["NDVI_mean"].replace(0, np.nan)

    if "EVI_mean" in analysis.columns and "et_base_out_mm_d" in analysis.columns:
        analysis["et_evi_ratio"] = analysis["et_base_out_mm_d"] / analysis["EVI_mean"].replace(0, np.nan)

    if "SAVI_mean" in analysis.columns and "et_base_out_mm_d" in analysis.columns:
        analysis["et_savi_ratio"] = analysis["et_base_out_mm_d"] / analysis["SAVI_mean"].replace(0, np.nan)

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
        "cloudy_pixel_percentage",
        "valid_pixel_pct",
        "selected_from_duplicates",

        "NDVI_mean", "NDVI_median", "NDVI_stdDev",
        "EVI_mean", "EVI_median", "EVI_stdDev",
        "SAVI_mean", "SAVI_median", "SAVI_stdDev",
        "NDRE_mean", "NDRE_median", "NDRE_stdDev",

        "et_ndvi_ratio",
        "et_evi_ratio",
        "et_savi_ratio",
    ]
    ordered_cols = [c for c in ordered_cols if c in analysis.columns]

    return analysis[ordered_cols].sort_values("date").reset_index(drop=True)


# =========================
# Resumen
# =========================
def build_summary(station: pd.DataFrame, s2: pd.DataFrame, merged: pd.DataFrame, analysis: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame(
        {
            "metric": [
                "n_station_days",
                "n_sentinel_days",
                "n_merged_days",
                "n_days_with_satellite_obs",
                "n_analysis_ready_days",
                "mean_et_analysis",
                "mean_ndvi_analysis",
                "mean_evi_analysis",
                "mean_savi_analysis",
                "mean_ndre_analysis",
                "mean_valid_pixel_pct_analysis",
            ],
            "value": [
                len(station),
                len(s2),
                len(merged),
                merged["has_satellite_obs"].sum() if "has_satellite_obs" in merged.columns else np.nan,
                len(analysis),
                analysis["et_base_out_mm_d"].mean() if "et_base_out_mm_d" in analysis.columns and not analysis.empty else np.nan,
                analysis["NDVI_mean"].mean() if "NDVI_mean" in analysis.columns and not analysis.empty else np.nan,
                analysis["EVI_mean"].mean() if "EVI_mean" in analysis.columns and not analysis.empty else np.nan,
                analysis["SAVI_mean"].mean() if "SAVI_mean" in analysis.columns and not analysis.empty else np.nan,
                analysis["NDRE_mean"].mean() if "NDRE_mean" in analysis.columns and not analysis.empty else np.nan,
                analysis["valid_pixel_pct"].mean() if "valid_pixel_pct" in analysis.columns and not analysis.empty else np.nan,
            ],
        }
    )
    return summary


# =========================
# Reporte
# =========================
def print_report(merged: pd.DataFrame, analysis: pd.DataFrame) -> None:
    print("\n=== MERGE ESTACIÓN + SENTINEL-2 ===")
    print(f"Días en tabla merged:             {len(merged)}")
    print(f"Días con observación satelital:   {int(merged['has_satellite_obs'].sum())}")
    print(f"Días listos para análisis:        {len(analysis)}")

    if not analysis.empty:
        print(f"ET media análisis:                {analysis['et_base_out_mm_d'].mean():.2f} mm/d")
        if "NDVI_mean" in analysis.columns:
            print(f"NDVI medio análisis:              {analysis['NDVI_mean'].mean():.4f}")
        if "EVI_mean" in analysis.columns:
            print(f"EVI medio análisis:               {analysis['EVI_mean'].mean():.4f}")
        if "valid_pixel_pct" in analysis.columns:
            print(f"% píxeles válidos medio:          {analysis['valid_pixel_pct'].mean():.2f}")

        print("\nPrimeras 10 filas análisis:")
        show_cols = [
            "date",
            "et_base_out_mm_d",
            "et_base_out_mm_d_w3_sum",
            "et_base_out_mm_d_w7_sum",
            "temp_out_mean_w3_mean",
            "rad_out_mean_w3_mean",
            "vpd_out_mean_w3_mean",
            "NDVI_mean",
            "EVI_mean",
            "SAVI_mean",
            "NDRE_mean",
        ]
        show_cols = [c for c in show_cols if c in analysis.columns]
        print(analysis[show_cols].head(10).to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    station = load_station(INPUT_STATION)
    s2 = load_sentinel(INPUT_S2)

    merged = build_daily_merge(station, s2)
    merged = add_antecedent_windows(merged)
    analysis = build_analysis_table(merged)
    summary = build_summary(station, s2, merged, analysis)

    merged.to_csv(OUT_MERGED_DAILY, index=False, encoding="utf-8")
    analysis.to_csv(OUT_MERGED_ANALYSIS, index=False, encoding="utf-8")
    summary.to_csv(OUT_MERGED_SUMMARY, index=False, encoding="utf-8")

    print_report(merged, analysis)

    print("\nArchivos generados:")
    print(f"- {OUT_MERGED_DAILY}")
    print(f"- {OUT_MERGED_ANALYSIS}")
    print(f"- {OUT_MERGED_SUMMARY}")


if __name__ == "__main__":
    main()