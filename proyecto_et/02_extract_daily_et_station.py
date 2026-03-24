from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_5MIN = BASE_DIR / "data" / "processed" / "station_clean_5min.csv"

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_DAILY_FULL = OUTPUT_DIR / "station_daily_official.csv"
OUT_DAILY_SUMMARY = OUTPUT_DIR / "station_daily_official_summary.csv"

EXPECTED_RECORDS_PER_DAY = 288
MIN_VALID_PCT = 80.0


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def last_valid(series: pd.Series):
    valid = series.dropna()
    return valid.iloc[-1] if not valid.empty else np.nan


# =========================
# Lectura
# =========================
def load_clean_5min(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"]).copy()
    df = df.sort_values("datetime").reset_index(drop=True)
    df["date"] = df["datetime"].dt.floor("D")
    return df


# =========================
# Construcción diaria
# =========================
def build_daily_station_table(
    df: pd.DataFrame,
    expected_records_per_day: int = 288,
    min_valid_pct: float = 80.0,
) -> pd.DataFrame:
    grouped = (
        df.groupby("date", as_index=False)
        .agg(
            datetime_first=("datetime", "min"),
            datetime_last=("datetime", "max"),
            n_records=("datetime", "size"),

            temp_in_mean=("temp_in_c", "mean"),
            temp_in_min=("temp_in_c", "min"),
            temp_in_max=("temp_in_c", "max"),
            temp_out_mean=("temp_out_c", "mean"),
            temp_out_min=("temp_out_c", "min"),
            temp_out_max=("temp_out_c", "max"),

            rh_in_mean=("rh_in_pct", "mean"),
            rh_in_min=("rh_in_pct", "min"),
            rh_in_max=("rh_in_pct", "max"),
            rh_out_mean=("rh_out_pct", "mean"),
            rh_out_min=("rh_out_pct", "min"),
            rh_out_max=("rh_out_pct", "max"),

            rad_in_mean=("rad_in_w_m2", "mean"),
            rad_in_max=("rad_in_w_m2", "max"),
            rad_out_mean=("rad_out_w_m2", "mean"),
            rad_out_max=("rad_out_w_m2", "max"),

            par_in_mean=("par_in_umol_m2_s", "mean"),
            par_out_mean=("par_out_umol_m2_s", "mean"),

            dli_in_max=("dli_in_mol_m2_d", "max"),
            dli_out_max=("dli_out_mol_m2_d", "max"),

            vpd_in_mean=("vpd_in_kpa", "mean"),
            vpd_in_max=("vpd_in_kpa", "max"),
            vpd_out_mean=("vpd_out_kpa", "mean"),
            vpd_out_max=("vpd_out_kpa", "max"),

            dewpoint_in_mean=("dewpoint_in_c", "mean"),
            dewpoint_out_mean=("dewpoint_out_c", "mean"),

            et_in_daily_max=("et_in_mm", "max"),
            et_out_daily_max=("et_out_mm", "max"),

            rad_acc_in_daily_max=("rad_acc_in_j_cm2_d", "max"),
            rad_acc_out_daily_max=("rad_acc_out_j_cm2_d", "max"),
        )
    )

    last_et = (
        df.groupby("date", as_index=False)
        .agg(
            et_in_daily_last=("et_in_mm", last_valid),
            et_out_daily_last=("et_out_mm", last_valid),
        )
    )

    daily = grouped.merge(last_et, on="date", how="left")

    # Cobertura del día
    daily["pct_day_records"] = daily["n_records"] / expected_records_per_day * 100.0

    # ET operativa recomendada
    # En esta base la ET se comporta como acumulado diario con reinicio
    daily["et_in_daily"] = daily["et_in_daily_max"]
    daily["et_out_daily"] = daily["et_out_daily_max"]

    # Diagnóstico: diferencia entre último valor y máximo
    daily["et_in_last_minus_max"] = daily["et_in_daily_last"] - daily["et_in_daily_max"]
    daily["et_out_last_minus_max"] = daily["et_out_daily_last"] - daily["et_out_daily_max"]

    # Regla de validez del día
    daily["is_valid_day"] = daily["pct_day_records"] >= min_valid_pct

    # Orden y formato
    daily = daily.sort_values("date").reset_index(drop=True)
    daily["date"] = pd.to_datetime(daily["date"]).dt.date

    return daily


# =========================
# Tablas de salida
# =========================
def build_summary_table(daily: pd.DataFrame) -> pd.DataFrame:
    summary_cols = [
        "date",
        "n_records",
        "pct_day_records",
        "et_in_daily",
        "et_out_daily",
        "et_in_daily_last",
        "et_out_daily_last",
        "is_valid_day",
    ]
    return daily[summary_cols].copy()


# =========================
# Reporte rápido
# =========================
def print_report(daily: pd.DataFrame, summary: pd.DataFrame) -> None:
    total_days = len(daily)
    valid_days = int(daily["is_valid_day"].sum())
    invalid_days = total_days - valid_days

    print("\n=== EXTRACCIÓN DIARIA OFICIAL ===")
    print(f"Días totales:         {total_days}")
    print(f"Días válidos:         {valid_days}")
    print(f"Días inválidos:       {invalid_days}")
    print(f"ET interna media:     {daily['et_in_daily'].mean():.2f} mm/día")
    print(f"ET externa media:     {daily['et_out_daily'].mean():.2f} mm/día")
    print(f"T media interior:     {daily['temp_in_mean'].mean():.2f} °C")
    print(f"T media exterior:     {daily['temp_out_mean'].mean():.2f} °C")
    print(f"DPV medio interior:   {daily['vpd_in_mean'].mean():.2f} kPa")
    print(f"DPV medio exterior:   {daily['vpd_out_mean'].mean():.2f} kPa")

    print("\nPrimeros 10 días:")
    print(summary.head(10).to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    df = load_clean_5min(INPUT_5MIN)
    daily = build_daily_station_table(
        df,
        expected_records_per_day=EXPECTED_RECORDS_PER_DAY,
        min_valid_pct=MIN_VALID_PCT,
    )
    summary = build_summary_table(daily)

    daily.to_csv(OUT_DAILY_FULL, index=False, encoding="utf-8")
    summary.to_csv(OUT_DAILY_SUMMARY, index=False, encoding="utf-8")

    print_report(daily, summary)

    print("\nArchivos generados:")
    print(f"- {OUT_DAILY_FULL}")
    print(f"- {OUT_DAILY_SUMMARY}")


if __name__ == "__main__":
    main()