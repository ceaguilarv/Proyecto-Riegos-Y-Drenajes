from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_DAILY = BASE_DIR / "data" / "processed" / "station_daily_official.csv"

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_EXTERIOR_DAILY = OUTPUT_DIR / "station_daily_exterior_ready.csv"
OUT_EXTERIOR_WEEKLY = OUTPUT_DIR / "station_weekly_exterior_ready.csv"
OUT_EXTERIOR_SUMMARY = OUTPUT_DIR / "station_daily_exterior_summary.csv"

MIN_VALID_PCT = 80.0


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    return (series - series.mean()) / std


# =========================
# Lectura
# =========================
def load_daily_station(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


# =========================
# Preparación analítica exterior
# =========================
def prepare_exterior_daily_table(
    daily: pd.DataFrame,
    min_valid_pct: float = 80.0,
) -> pd.DataFrame:
    df = daily.copy()

    # Normalización mínima de tipos
    numeric_cols = [
        "n_records",
        "pct_day_records",
        "temp_out_mean",
        "temp_out_min",
        "temp_out_max",
        "rh_out_mean",
        "rh_out_min",
        "rh_out_max",
        "rad_out_mean",
        "rad_out_max",
        "par_out_mean",
        "dli_out_max",
        "vpd_out_mean",
        "vpd_out_max",
        "dewpoint_out_mean",
        "et_out_daily",
        "et_out_daily_last",
        "et_out_daily_max",
        "et_out_last_minus_max",
        "rad_acc_out_daily_max",
    ]
    present_numeric = [c for c in numeric_cols if c in df.columns]
    for col in present_numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Reglas principales de validez
    df["is_valid_day_by_coverage"] = df["pct_day_records"] >= min_valid_pct
    df["is_valid_day_by_et"] = df["et_out_daily"].notna() & (df["et_out_daily"] >= 0)
    df["is_valid_day_by_temp"] = df["temp_out_mean"].notna()
    df["is_valid_day_by_rh"] = df["rh_out_mean"].notna()
    df["is_valid_day_by_rad"] = df["rad_out_mean"].notna()

    df["is_valid_day_analysis"] = (
        df["is_valid_day_by_coverage"]
        & df["is_valid_day_by_et"]
        & df["is_valid_day_by_temp"]
        & df["is_valid_day_by_rh"]
        & df["is_valid_day_by_rad"]
    )

    # Señal base exterior usada para el artículo
    df["et_base_out_mm_d"] = df["et_out_daily"]

    # Variables temporales para integración posterior con satélite
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    df["iso_year"] = df["date"].dt.isocalendar().year.astype(int)
    df["iso_week"] = df["date"].dt.isocalendar().week.astype(int)
    df["week_id"] = (
        df["iso_year"].astype(str)
        + "-W"
        + df["iso_week"].astype(str).str.zfill(2)
    )
    df["doy"] = df["date"].dt.dayofyear

    # Diagnósticos simples para exploración
    df["temp_range_out_c"] = df["temp_out_max"] - df["temp_out_min"]
    df["rh_range_out_pct"] = df["rh_out_max"] - df["rh_out_min"]
    df["et_rad_ratio"] = np.where(
        df["rad_out_mean"].gt(0),
        df["et_base_out_mm_d"] / df["rad_out_mean"],
        np.nan,
    )
    df["vpd_rad_product"] = df["vpd_out_mean"] * df["rad_out_mean"]

    # Banderas de posible anomalía, sin eliminar observaciones automáticamente
    df["flag_et_jump_high"] = df["et_base_out_mm_d"] > df["et_base_out_mm_d"].quantile(0.99)
    df["flag_et_zero"] = df["et_base_out_mm_d"].fillna(-1).eq(0)
    df["flag_vpd_high_z"] = zscore(
        df["vpd_out_mean"].fillna(df["vpd_out_mean"].median())
    ).abs() > 3
    df["flag_temp_high_z"] = zscore(
        df["temp_out_mean"].fillna(df["temp_out_mean"].median())
    ).abs() > 3

    # Selección y orden final
    ordered_cols = [
        "date",
        "year",
        "month",
        "day",
        "year_month",
        "iso_year",
        "iso_week",
        "week_id",
        "doy",
        "n_records",
        "pct_day_records",
        "is_valid_day",
        "is_valid_day_by_coverage",
        "is_valid_day_by_et",
        "is_valid_day_by_temp",
        "is_valid_day_by_rh",
        "is_valid_day_by_rad",
        "is_valid_day_analysis",
        "et_base_out_mm_d",
        "et_out_daily",
        "et_out_daily_last",
        "et_out_daily_max",
        "et_out_last_minus_max",
        "temp_out_mean",
        "temp_out_min",
        "temp_out_max",
        "temp_range_out_c",
        "rh_out_mean",
        "rh_out_min",
        "rh_out_max",
        "rh_range_out_pct",
        "rad_out_mean",
        "rad_out_max",
        "rad_acc_out_daily_max",
        "par_out_mean",
        "dli_out_max",
        "vpd_out_mean",
        "vpd_out_max",
        "vpd_rad_product",
        "dewpoint_out_mean",
        "et_rad_ratio",
        "flag_et_jump_high",
        "flag_et_zero",
        "flag_vpd_high_z",
        "flag_temp_high_z",
    ]
    ordered_cols = [c for c in ordered_cols if c in df.columns]
    df = df[ordered_cols].copy()

    return df.sort_values("date").reset_index(drop=True)


# =========================
# Agregación semanal de apoyo
# =========================
def build_weekly_support_table(exterior_daily: pd.DataFrame) -> pd.DataFrame:
    valid = exterior_daily.loc[exterior_daily["is_valid_day_analysis"]].copy()

    if valid.empty:
        return pd.DataFrame(
            columns=[
                "week_id",
                "date_start",
                "date_end",
                "n_valid_days",
                "et_base_out_mm_week",
                "et_base_out_mm_d_mean",
                "temp_out_mean_week",
                "rh_out_mean_week",
                "rad_out_mean_week",
                "vpd_out_mean_week",
            ]
        )

    weekly = (
        valid.groupby("week_id", as_index=False)
        .agg(
            date_start=("date", "min"),
            date_end=("date", "max"),
            n_valid_days=("date", "size"),
            et_base_out_mm_week=("et_base_out_mm_d", "sum"),
            et_base_out_mm_d_mean=("et_base_out_mm_d", "mean"),
            temp_out_mean_week=("temp_out_mean", "mean"),
            rh_out_mean_week=("rh_out_mean", "mean"),
            rad_out_mean_week=("rad_out_mean", "mean"),
            vpd_out_mean_week=("vpd_out_mean", "mean"),
        )
    )

    return weekly.sort_values(["date_start", "week_id"]).reset_index(drop=True)


# =========================
# Tabla resumen
# =========================
def build_summary_table(exterior_daily: pd.DataFrame) -> pd.DataFrame:
    summary = exterior_daily.loc[:, [
        "date",
        "pct_day_records",
        "is_valid_day_analysis",
        "et_base_out_mm_d",
        "temp_out_mean",
        "rh_out_mean",
        "rad_out_mean",
        "vpd_out_mean",
        "flag_et_jump_high",
        "flag_et_zero",
        "flag_vpd_high_z",
        "flag_temp_high_z",
    ]].copy()
    return summary


# =========================
# Reporte rápido
# =========================
def print_report(exterior_daily: pd.DataFrame, weekly: pd.DataFrame) -> None:
    total_days = len(exterior_daily)
    valid_days = int(exterior_daily["is_valid_day_analysis"].sum())
    invalid_days = total_days - valid_days

    print("\n=== PREPARACIÓN EXTERIOR PARA CRUCE SATELITAL ===")
    print(f"Días totales:                    {total_days}")
    print(f"Días válidos para análisis:      {valid_days}")
    print(f"Días no válidos para análisis:   {invalid_days}")

    if valid_days > 0:
        valid = exterior_daily.loc[exterior_daily["is_valid_day_analysis"]]
        print(f"ET base exterior media:          {valid['et_base_out_mm_d'].mean():.2f} mm/día")
        print(f"Temperatura exterior media:      {valid['temp_out_mean'].mean():.2f} °C")
        print(f"Humedad relativa exterior media: {valid['rh_out_mean'].mean():.2f} %")
        print(f"Radiación exterior media:        {valid['rad_out_mean'].mean():.2f} W/m²")
        print(f"DPV exterior medio:              {valid['vpd_out_mean'].mean():.2f} kPa")

    print(f"Semanas con apoyo agregado:      {len(weekly)}")

    print("\nPrimeros 10 días listos para análisis:")
    cols = [
        "date",
        "pct_day_records",
        "is_valid_day_analysis",
        "et_base_out_mm_d",
        "temp_out_mean",
        "rh_out_mean",
        "rad_out_mean",
        "vpd_out_mean",
    ]
    cols = [c for c in cols if c in exterior_daily.columns]
    print(exterior_daily[cols].head(10).to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    daily = load_daily_station(INPUT_DAILY)
    exterior_daily = prepare_exterior_daily_table(daily, min_valid_pct=MIN_VALID_PCT)
    weekly = build_weekly_support_table(exterior_daily)
    summary = build_summary_table(exterior_daily)

    exterior_daily.to_csv(OUT_EXTERIOR_DAILY, index=False, encoding="utf-8")
    weekly.to_csv(OUT_EXTERIOR_WEEKLY, index=False, encoding="utf-8")
    summary.to_csv(OUT_EXTERIOR_SUMMARY, index=False, encoding="utf-8")

    print_report(exterior_daily, weekly)

    print("\nArchivos generados:")
    print(f"- {OUT_EXTERIOR_DAILY}")
    print(f"- {OUT_EXTERIOR_WEEKLY}")
    print(f"- {OUT_EXTERIOR_SUMMARY}")


if __name__ == "__main__":
    main()