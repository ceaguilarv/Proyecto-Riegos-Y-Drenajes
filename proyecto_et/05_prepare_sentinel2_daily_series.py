from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_S2_TIMESERIES = BASE_DIR / "data" / "processed" / "sentinel2_roi_timeseries.csv"

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_S2_DAILY = OUTPUT_DIR / "sentinel2_daily_series.csv"
OUT_S2_DAILY_ALL = OUTPUT_DIR / "sentinel2_daily_series_all_dates.csv"
OUT_S2_DUPLICATES = OUTPUT_DIR / "sentinel2_duplicate_dates_review.csv"
OUT_S2_SUMMARY = OUTPUT_DIR / "sentinel2_daily_series_summary.csv"


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


# =========================
# Lectura
# =========================
def load_sentinel_timeseries(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)

    if "date" not in df.columns:
        raise ValueError("El archivo de entrada no tiene la columna 'date'.")

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
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "is_valid_satellite_obs" in df.columns:
        df["is_valid_satellite_obs"] = df["is_valid_satellite_obs"].astype(str).str.lower().map(
            {"true": True, "false": False}
        )
    else:
        df["is_valid_satellite_obs"] = df["valid_pixel_pct"] >= 30.0

    df = df.sort_values(["date", "valid_pixel_pct", "cloudy_pixel_percentage"],
                        ascending=[True, False, True]).reset_index(drop=True)
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

    review = review.sort_values(
        ["date", "is_valid_satellite_obs", "valid_pixel_pct", "cloudy_pixel_percentage"],
        ascending=[True, False, False, True]
    ).reset_index(drop=True)

    review["candidate_rank"] = (
        review.groupby("date")
        .cumcount()
        .add(1)
    )

    return review


# =========================
# Selección de una fila por fecha
# =========================
def select_best_observation_per_date(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    # Ranking:
    # 1) observación válida primero
    # 2) mayor porcentaje de píxeles válidos
    # 3) menor nubosidad de escena
    work["valid_rank"] = work["is_valid_satellite_obs"].fillna(False).astype(int)

    work = work.sort_values(
        ["date", "valid_rank", "valid_pixel_pct", "cloudy_pixel_percentage"],
        ascending=[True, False, False, True]
    ).reset_index(drop=True)

    best = work.groupby("date", as_index=False).first()

    best["n_obs_same_date"] = df.groupby("date").size().values
    best["selected_from_duplicates"] = best["n_obs_same_date"] > 1

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

    # Variables útiles para análisis posterior
    if "NDVI_mean" in df.columns and "EVI_mean" in df.columns:
        df["ndvi_evi_diff"] = df["NDVI_mean"] - df["EVI_mean"]

    if "NDVI_mean" in df.columns and "SAVI_mean" in df.columns:
        df["ndvi_savi_diff"] = df["NDVI_mean"] - df["SAVI_mean"]

    # Banderas de calidad
    df["flag_low_valid_pixel_pct"] = df["valid_pixel_pct"] < 50
    df["flag_high_scene_cloudiness"] = df["cloudy_pixel_percentage"] > 50

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
        "image_id",
        "datetime_utc",
        "cloudy_pixel_percentage",
        "valid_pixel_pct",
        "is_valid_satellite_obs",
        "n_obs_same_date",
        "selected_from_duplicates",
        "NDVI_mean", "NDVI_median", "NDVI_stdDev",
        "EVI_mean", "EVI_median", "EVI_stdDev",
        "SAVI_mean", "SAVI_median", "SAVI_stdDev",
        "NDRE_mean", "NDRE_median", "NDRE_stdDev",
        "ndvi_evi_diff",
        "ndvi_savi_diff",
        "flag_low_valid_pixel_pct",
        "flag_high_scene_cloudiness",
    ]
    ordered_cols = [c for c in ordered_cols if c in df.columns]

    return df[ordered_cols].sort_values("date").reset_index(drop=True)


def build_all_dates_table(best_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Deja una fila por fecha disponible en satélite, incluso si la observación elegida quedó inválida.
    """
    return best_daily.copy()


def build_valid_only_table(best_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla final principal para análisis: solo fechas válidas.
    """
    return best_daily.loc[best_daily["is_valid_satellite_obs"]].copy().reset_index(drop=True)


# =========================
# Resumen
# =========================
def build_summary(raw: pd.DataFrame, best_daily: pd.DataFrame, valid_daily: pd.DataFrame) -> pd.DataFrame:
    n_total_images = len(raw)
    n_unique_dates = raw["date"].nunique()
    n_duplicate_dates = int((raw.groupby("date").size() > 1).sum())
    n_best_daily = len(best_daily)
    n_valid_daily = len(valid_daily)

    summary = pd.DataFrame(
        {
            "metric": [
                "n_total_images",
                "n_unique_dates_raw",
                "n_dates_with_duplicates",
                "n_daily_selected",
                "n_daily_valid_final",
                "mean_valid_pixel_pct_final",
                "mean_ndvi_final",
                "mean_evi_final",
                "mean_savi_final",
                "mean_ndre_final",
            ],
            "value": [
                n_total_images,
                n_unique_dates,
                n_duplicate_dates,
                n_best_daily,
                n_valid_daily,
                valid_daily["valid_pixel_pct"].mean() if not valid_daily.empty else np.nan,
                valid_daily["NDVI_mean"].mean() if "NDVI_mean" in valid_daily.columns and not valid_daily.empty else np.nan,
                valid_daily["EVI_mean"].mean() if "EVI_mean" in valid_daily.columns and not valid_daily.empty else np.nan,
                valid_daily["SAVI_mean"].mean() if "SAVI_mean" in valid_daily.columns and not valid_daily.empty else np.nan,
                valid_daily["NDRE_mean"].mean() if "NDRE_mean" in valid_daily.columns and not valid_daily.empty else np.nan,
            ],
        }
    )
    return summary


# =========================
# Reporte
# =========================
def print_report(raw: pd.DataFrame, duplicates: pd.DataFrame, best_daily: pd.DataFrame, valid_daily: pd.DataFrame) -> None:
    print("\n=== PREPARACIÓN DE SERIE DIARIA SENTINEL-2 ===")
    print(f"Imágenes originales:                {len(raw)}")
    print(f"Fechas únicas originales:           {raw['date'].nunique()}")
    print(f"Fechas con duplicados:              {(raw.groupby('date').size() > 1).sum()}")
    print(f"Serie diaria seleccionada:          {len(best_daily)}")
    print(f"Serie diaria válida final:          {len(valid_daily)}")

    if not valid_daily.empty:
        print(f"% píxeles válidos medio final:      {valid_daily['valid_pixel_pct'].mean():.2f}")
        if "NDVI_mean" in valid_daily.columns:
            print(f"NDVI medio final:                   {valid_daily['NDVI_mean'].mean():.4f}")
        if "EVI_mean" in valid_daily.columns:
            print(f"EVI medio final:                    {valid_daily['EVI_mean'].mean():.4f}")
        if "SAVI_mean" in valid_daily.columns:
            print(f"SAVI medio final:                   {valid_daily['SAVI_mean'].mean():.4f}")
        if "NDRE_mean" in valid_daily.columns:
            print(f"NDRE medio final:                   {valid_daily['NDRE_mean'].mean():.4f}")

    if not duplicates.empty:
        print("\nPrimeras fechas con duplicados revisadas:")
        show_cols = [
            "date",
            "candidate_rank",
            "is_valid_satellite_obs",
            "valid_pixel_pct",
            "cloudy_pixel_percentage",
            "NDVI_mean",
            "EVI_mean",
            "SAVI_mean",
            "NDRE_mean",
        ]
        show_cols = [c for c in show_cols if c in duplicates.columns]
        print(duplicates[show_cols].head(12).to_string(index=False))

    print("\nPrimeras 10 filas de la serie diaria válida:")
    show_cols = [
        "date",
        "valid_pixel_pct",
        "cloudy_pixel_percentage",
        "selected_from_duplicates",
        "NDVI_mean",
        "EVI_mean",
        "SAVI_mean",
        "NDRE_mean",
    ]
    show_cols = [c for c in show_cols if c in valid_daily.columns]
    print(valid_daily[show_cols].head(10).to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    raw = load_sentinel_timeseries(INPUT_S2_TIMESERIES)
    duplicates = build_duplicates_review(raw)
    best_daily = select_best_observation_per_date(raw)
    best_daily = prepare_daily_series(best_daily)

    daily_valid = build_valid_only_table(best_daily)
    daily_all = build_all_dates_table(best_daily)
    summary = build_summary(raw, best_daily, daily_valid)

    daily_valid.to_csv(OUT_S2_DAILY, index=False, encoding="utf-8")
    daily_all.to_csv(OUT_S2_DAILY_ALL, index=False, encoding="utf-8")
    duplicates.to_csv(OUT_S2_DUPLICATES, index=False, encoding="utf-8")
    summary.to_csv(OUT_S2_SUMMARY, index=False, encoding="utf-8")

    print_report(raw, duplicates, best_daily, daily_valid)

    print("\nArchivos generados:")
    print(f"- {OUT_S2_DAILY}")
    print(f"- {OUT_S2_DAILY_ALL}")
    print(f"- {OUT_S2_DUPLICATES}")
    print(f"- {OUT_S2_SUMMARY}")


if __name__ == "__main__":
    main()