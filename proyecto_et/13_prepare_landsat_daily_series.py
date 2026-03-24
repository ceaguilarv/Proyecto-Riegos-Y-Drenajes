from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd


# ============================================================
# 13_prepare_landsat_daily_series.py
# Depura la serie térmica Landsat por imagen y deja una sola
# observación por fecha para análisis posterior.
# ============================================================


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

DEFAULT_INPUT_DIR = BASE_DIR / "data" / "processed"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "processed"

FALLBACK_INPUT_DIR = BASE_DIR
FALLBACK_OUTPUT_DIR = BASE_DIR

MIN_VALID_PIXEL_PCT = 30.0


# =========================
# Resolución de rutas
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

INPUT_LST_TIMESERIES = INPUT_DIR / "landsat_lst_roi_timeseries.csv"

OUT_DUPLICATES_REVIEW = OUTPUT_DIR / "landsat_lst_duplicate_dates_review.csv"
OUT_DAILY_SERIES = OUTPUT_DIR / "landsat_lst_daily_series.csv"
OUT_DAILY_SUMMARY = OUTPUT_DIR / "landsat_lst_daily_summary.csv"


# =========================
# Lectura y limpieza
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def load_lst_timeseries(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)

    if "date" not in df.columns:
        raise ValueError("El archivo de entrada no contiene la columna 'date'.")

    if "datetime_utc" in df.columns:
        df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], errors="coerce")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    numeric_cols = [
        "valid_pixel_pct",
        "wrs_path",
        "wrs_row",
        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "LST_K_mean",
        "LST_K_median",
        "LST_K_stdDev",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "is_valid_satellite_obs" in df.columns:
        df["is_valid_satellite_obs"] = (
            df["is_valid_satellite_obs"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({"true": True, "false": False})
        )
    else:
        warnings.warn(
            "No se encontró 'is_valid_satellite_obs'. "
            "Se recalculará usando valid_pixel_pct >= 30.0"
        )
        df["is_valid_satellite_obs"] = df["valid_pixel_pct"] >= MIN_VALID_PIXEL_PCT

    df = df.dropna(subset=["date"]).copy()

    sort_cols = [c for c in ["date", "datetime_utc"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    return df


# =========================
# Revisión de duplicados
# =========================
def build_duplicates_review(df: pd.DataFrame) -> pd.DataFrame:
    counts = df.groupby("date").size().reset_index(name="n_obs_date")
    dup_dates = counts.loc[counts["n_obs_date"] > 1, "date"]

    review = df[df["date"].isin(dup_dates)].copy()
    if review.empty:
        return review

    review["valid_rank"] = review["is_valid_satellite_obs"].fillna(False).astype(int)

    if "LST_C_stdDev" not in review.columns:
        review["LST_C_stdDev"] = np.nan
    if "datetime_utc" not in review.columns:
        review["datetime_utc"] = pd.NaT

    review = review.sort_values(
        ["date", "valid_rank", "valid_pixel_pct", "LST_C_stdDev", "datetime_utc"],
        ascending=[True, False, False, True, True]
    ).reset_index(drop=True)

    review["candidate_rank"] = review.groupby("date").cumcount() + 1
    review["selection_rule"] = (
        "1=observación válida, 2=mayor valid_pixel_pct, "
        "3=menor LST_C_stdDev, 4=menor datetime_utc"
    )

    return review


# =========================
# Selección de una fila por fecha
# =========================
def select_best_observation_per_date(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    if "LST_C_stdDev" not in work.columns:
        work["LST_C_stdDev"] = np.nan
    if "datetime_utc" not in work.columns:
        work["datetime_utc"] = pd.NaT

    work["valid_rank"] = work["is_valid_satellite_obs"].fillna(False).astype(int)

    work = work.sort_values(
        ["date", "valid_rank", "valid_pixel_pct", "LST_C_stdDev", "datetime_utc"],
        ascending=[True, False, False, True, True]
    ).reset_index(drop=True)

    best = work.groupby("date", as_index=False).first()

    counts = df.groupby("date").size().rename("n_obs_same_date").reset_index()
    best = best.merge(counts, on="date", how="left")

    best["selected_from_duplicates"] = best["n_obs_same_date"] > 1

    best["selection_rule"] = (
        "1=observación válida, 2=mayor valid_pixel_pct, "
        "3=menor LST_C_stdDev, 4=menor datetime_utc"
    )

    return best


# =========================
# Preparación de serie diaria
# =========================
def prepare_daily_series(best: pd.DataFrame) -> pd.DataFrame:
    df = best.copy()

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    df["doy"] = df["date"].dt.dayofyear
    df["iso_year"] = df["date"].dt.isocalendar().year.astype(int)
    df["iso_week"] = df["date"].dt.isocalendar().week.astype(int)
    df["week_id"] = df["iso_year"].astype(str) + "-W" + df["iso_week"].astype(str).str.zfill(2)

    # Variables derivadas útiles para análisis
    if "LST_C_mean" in df.columns and "LST_C_median" in df.columns:
        df["LST_C_mean_minus_median"] = df["LST_C_mean"] - df["LST_C_median"]

    if "LST_C_stdDev" in df.columns and "LST_C_mean" in df.columns:
        df["LST_C_cv_pct"] = np.where(
            df["LST_C_mean"].notna() & (df["LST_C_mean"] != 0),
            (df["LST_C_stdDev"] / df["LST_C_mean"]) * 100,
            np.nan,
        )

    # Bandera de utilidad para merge posterior
    essential_cols = ["LST_C_mean", "valid_pixel_pct", "is_valid_satellite_obs"]
    existing_essential = [c for c in essential_cols if c in df.columns]

    if existing_essential:
        df["is_merge_ready"] = df[existing_essential].notna().all(axis=1)
        if "is_valid_satellite_obs" in df.columns:
            df["is_merge_ready"] = df["is_merge_ready"] & df["is_valid_satellite_obs"].fillna(False)
    else:
        df["is_merge_ready"] = False

    ordered_cols = [
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
        "is_merge_ready",
        "year",
        "month",
        "day",
        "year_month",
        "doy",
        "iso_year",
        "iso_week",
        "week_id",
    ]
    ordered_cols = [c for c in ordered_cols if c in df.columns]

    return df[ordered_cols].sort_values("date").reset_index(drop=True)


# =========================
# Resumen
# =========================
def build_daily_summary(df_raw: pd.DataFrame, df_daily: pd.DataFrame, duplicates_review: pd.DataFrame) -> pd.DataFrame:
    if df_daily.empty:
        return pd.DataFrame(
            {
                "metric": [
                    "n_input_rows",
                    "n_daily_rows",
                    "n_duplicate_rows",
                    "n_duplicate_dates",
                    "n_merge_ready",
                    "mean_valid_pixel_pct_daily",
                    "mean_lst_c_daily",
                    "median_lst_c_daily",
                    "std_lst_c_daily",
                ],
                "value": [0, 0, 0, 0, 0, np.nan, np.nan, np.nan, np.nan],
            }
        )

    return pd.DataFrame(
        {
            "metric": [
                "n_input_rows",
                "n_daily_rows",
                "n_duplicate_rows",
                "n_duplicate_dates",
                "n_merge_ready",
                "mean_valid_pixel_pct_daily",
                "mean_lst_c_daily",
                "median_lst_c_daily",
                "std_lst_c_daily",
            ],
            "value": [
                len(df_raw),
                len(df_daily),
                len(duplicates_review),
                duplicates_review["date"].nunique() if not duplicates_review.empty else 0,
                int(df_daily["is_merge_ready"].sum()) if "is_merge_ready" in df_daily.columns else 0,
                df_daily["valid_pixel_pct"].mean() if "valid_pixel_pct" in df_daily.columns else np.nan,
                df_daily["LST_C_mean"].mean() if "LST_C_mean" in df_daily.columns else np.nan,
                df_daily["LST_C_median"].median() if "LST_C_median" in df_daily.columns else np.nan,
                df_daily["LST_C_stdDev"].mean() if "LST_C_stdDev" in df_daily.columns else np.nan,
            ],
        }
    )


# =========================
# Reporte
# =========================
def print_report(df_raw: pd.DataFrame, duplicates_review: pd.DataFrame, df_daily: pd.DataFrame) -> None:
    print("\n=== PREPARACIÓN DE SERIE DIARIA LANDSAT LST ===")
    print(f"Filas de entrada:              {len(df_raw)}")
    print(f"Fechas únicas de entrada:      {df_raw['date'].nunique()}")
    print(f"Fechas duplicadas:             {duplicates_review['date'].nunique() if not duplicates_review.empty else 0}")
    print(f"Filas serie diaria final:      {len(df_daily)}")

    if "is_merge_ready" in df_daily.columns:
        print(f"Observaciones merge-ready:     {int(df_daily['is_merge_ready'].sum())}")

    if "valid_pixel_pct" in df_daily.columns:
        print(f"% píxeles válidos promedio:    {df_daily['valid_pixel_pct'].mean():.2f}")

    if "LST_C_mean" in df_daily.columns:
        print(f"LST_C_mean promedio:           {df_daily['LST_C_mean'].mean():.2f}")

    print("\nPrimeras 10 filas de la serie diaria:")
    show_cols = [
        "date",
        "sensor_label",
        "valid_pixel_pct",
        "is_valid_satellite_obs",
        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "selected_from_duplicates",
        "is_merge_ready",
    ]
    show_cols = [c for c in show_cols if c in df_daily.columns]
    print(df_daily[show_cols].head(10).to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    df_raw = load_lst_timeseries(INPUT_LST_TIMESERIES)
    duplicates_review = build_duplicates_review(df_raw)
    best = select_best_observation_per_date(df_raw)
    df_daily = prepare_daily_series(best)
    summary = build_daily_summary(df_raw, df_daily, duplicates_review)

    duplicates_review.to_csv(OUT_DUPLICATES_REVIEW, index=False, encoding="utf-8")
    df_daily.to_csv(OUT_DAILY_SERIES, index=False, encoding="utf-8")
    summary.to_csv(OUT_DAILY_SUMMARY, index=False, encoding="utf-8")

    print_report(df_raw, duplicates_review, df_daily)

    print("\nArchivos generados:")
    print(f"- {OUT_DUPLICATES_REVIEW}")
    print(f"- {OUT_DAILY_SERIES}")
    print(f"- {OUT_DAILY_SUMMARY}")


if __name__ == "__main__":
    main()