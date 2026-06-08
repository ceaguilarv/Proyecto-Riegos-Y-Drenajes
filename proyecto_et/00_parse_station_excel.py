from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# =========================
# Configuración
# =========================
INPUT_XLSX = Path("datos_articulo.xlsx")
SHEET_NAME = "Mediciones_2501"

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CLEAN_5MIN = OUTPUT_DIR / "station_clean_5min.csv"
OUT_DAILY = OUTPUT_DIR / "station_daily.csv"
OUT_QC_JSON = OUTPUT_DIR / "station_qc_summary.json"
OUT_DAILY_SUMMARY = OUTPUT_DIR / "station_daily_summary.csv"

# =========================
# Utilidades
# =========================
def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def clean_text(text: Any) -> str:
    if pd.isna(text):
        return ""
    text = str(text).strip()
    text = text.replace("Â", "")
    text = strip_accents(text)
    text = text.replace("%", "pct")
    text = text.replace("°", "")
    text = text.replace("º", "")
    text = text.replace("μ", "u")
    text = text.replace("µ", "u")
    text = text.replace("/", "_")
    text = text.replace(".", "_")
    text = text.replace("-", "_")
    text = re.sub(r"[()]+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_").lower()


def parse_excel_date(value: Any) -> pd.Timestamp | pd.NaT:
    """
    Convierte la fecha original del Excel a fecha normalizada.

    Corrección crítica:
    - Si la fecha viene en formato ISO tipo YYYY-MM-DD, se interpreta con dayfirst=False.
      Ejemplo: 2025-11-01 debe ser 1 de noviembre de 2025, no 11 de enero de 2025.
    - Solo para formatos ambiguos tipo DD/MM/YYYY se intenta primero dayfirst=True.
    """
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value.normalize()

    # Serial Excel
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            base = pd.Timestamp("1899-12-30")
            return (base + pd.to_timedelta(float(value), unit="D")).normalize()
        except Exception:
            return pd.NaT

    value_str = str(value).strip()
    if not value_str:
        return pd.NaT

    # Caso ISO explícito: YYYY-MM-DD o YYYY/MM/DD
    # Este era el punto crítico del error.
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", value_str):
        parsed = pd.to_datetime(value_str, errors="coerce", dayfirst=False)
        if pd.notna(parsed):
            return parsed.normalize()

    # Caso con separador y año al final: probablemente DD/MM/YYYY
    if re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}", value_str):
        parsed = pd.to_datetime(value_str, errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            return parsed.normalize()

        parsed = pd.to_datetime(value_str, errors="coerce", dayfirst=False)
        if pd.notna(parsed):
            return parsed.normalize()

    # Último intento conservador
    parsed = pd.to_datetime(value_str, errors="coerce", dayfirst=False)
    if pd.notna(parsed):
        return parsed.normalize()

    return pd.NaT


def parse_excel_time_to_seconds(value: Any) -> float:
    if pd.isna(value):
        return np.nan

    if isinstance(value, pd.Timestamp):
        return float(value.hour * 3600 + value.minute * 60 + value.second)

    # Serial Excel para hora
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value_float = float(value)
        if 0 <= value_float < 2:
            seconds = round((value_float % 1) * 24 * 3600)
            return float(seconds)

    value_str = str(value).strip()
    if not value_str:
        return np.nan

    parsed = pd.to_datetime(value_str, errors="coerce")
    if pd.notna(parsed):
        return float(parsed.hour * 3600 + parsed.minute * 60 + parsed.second)

    return np.nan


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def first_valid(series: pd.Series) -> Any:
    valid = series.dropna()
    return valid.iloc[0] if not valid.empty else np.nan


def last_valid(series: pd.Series) -> Any:
    valid = series.dropna()
    return valid.iloc[-1] if not valid.empty else np.nan


def summarize_intervals(datetimes: pd.Series) -> dict[str, int]:
    s = datetimes.sort_values().dropna()
    diffs = s.diff().dropna().value_counts().sort_index()
    return {str(k): int(v) for k, v in diffs.items()}


# =========================
# Lectura y limpieza inicial
# =========================
def load_station_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    # La fila 2 del Excel real contiene los encabezados útiles
    df = pd.read_excel(path, sheet_name=sheet_name, header=1)
    df.columns = [clean_text(c) for c in df.columns]

    rename_map = {
        "fecha": "fecha",
        "hora": "hora",
        "temperatura_in_c": "temp_in_c",
        "humedad_in_pct": "rh_in_pct",
        "radiacion_in_w_m2": "rad_in_w_m2",
        "par_in_umol_m2_s": "par_in_umol_m2_s",
        "dli_in_mol_m2_dia": "dli_in_mol_m2_d",
        "dpv_in_kpa": "vpd_in_kpa",
        "radiacion_acum_in_j_cm2_dia": "rad_acc_in_j_cm2_d",
        "temperaturarocio_in_c": "dewpoint_in_c",
        "evapotranspiracion_in_mm": "et_in_mm",
        "temperatura_out_c": "temp_out_c",
        "humedad_out_pct": "rh_out_pct",
        "radiacion_out_w_m2": "rad_out_w_m2",
        "par_out_umol_m2_s": "par_out_umol_m2_s",
        "dli_out_mol_m2_dia": "dli_out_mol_m2_d",
        "dpv_out_kpa": "vpd_out_kpa",
        "radiacionacum_out_j_cm2_dia": "rad_acc_out_j_cm2_d",
        "evapotranspiracion_out_mm": "et_out_mm",
        "temperaturarocio_out_c": "dewpoint_out_c",
    }

    df = df.rename(columns=rename_map)

    expected = [
        "fecha",
        "hora",
        "temp_in_c",
        "rh_in_pct",
        "rad_in_w_m2",
        "par_in_umol_m2_s",
        "dli_in_mol_m2_d",
        "vpd_in_kpa",
        "rad_acc_in_j_cm2_d",
        "dewpoint_in_c",
        "et_in_mm",
        "temp_out_c",
        "rh_out_pct",
        "rad_out_w_m2",
        "par_out_umol_m2_s",
        "dli_out_mol_m2_d",
        "vpd_out_kpa",
        "rad_acc_out_j_cm2_d",
        "et_out_mm",
        "dewpoint_out_c",
    ]

    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas esperadas: {missing}")

    return df[expected].copy()


# =========================
# Construcción temporal
# =========================
def build_datetime(df: pd.DataFrame) -> pd.DataFrame:
    dates = df["fecha"].apply(parse_excel_date)
    seconds = df["hora"].apply(parse_excel_time_to_seconds)

    dt = dates + pd.to_timedelta(seconds, unit="s")
    df["datetime"] = pd.to_datetime(dt, errors="coerce")

    df = df.dropna(subset=["datetime"]).copy()
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


# =========================
# Control de calidad temporal
# =========================
def add_temporal_qc(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = df.copy()

    df["is_duplicate_datetime"] = df["datetime"].duplicated(keep="first")
    df = df[~df["is_duplicate_datetime"]].copy()

    df["delta_minutes"] = df["datetime"].diff().dt.total_seconds() / 60.0
    df["date"] = df["datetime"].dt.date

    start = df["datetime"].min()
    end = df["datetime"].max()

    full_range = pd.date_range(start.floor("D"), end.floor("D") + pd.Timedelta(days=1) - pd.Timedelta(minutes=5), freq="5min")
    expected_rows = len(full_range)

    observed_rows = len(df)
    missing_rows_est = max(expected_rows - observed_rows, 0)

    daily_counts = df.groupby("date").size()
    expected_per_day = 288  # 24h * 12 registros por hora

    missing_full_days = []
    full_days = pd.date_range(start.floor("D"), end.floor("D"), freq="D").date
    observed_days = set(df["date"].unique())
    for d in full_days:
        if d not in observed_days:
            missing_full_days.append(str(d))

    gap_rows = df[df["delta_minutes"] > 5].copy()
    gap_rows["gap_minutes"] = gap_rows["delta_minutes"] - 5

    qc = {
        "start_datetime": str(start),
        "end_datetime": str(end),
        "observed_rows_after_dedup": int(observed_rows),
        "expected_rows_5min": int(expected_rows),
        "estimated_missing_rows_vs_full_5min_grid": int(missing_rows_est),
        "days_with_any_data": int(len(observed_days)),
        "missing_full_days_count": int(len(missing_full_days)),
        "missing_full_days": missing_full_days,
        "interval_distribution": summarize_intervals(df["datetime"]),
        "gaps_larger_than_5min_count": int((df["delta_minutes"] > 5).sum()),
        "largest_gap_minutes": float(df["delta_minutes"].max()) if df["delta_minutes"].notna().any() else None,
    }

    df["records_in_day"] = df.groupby("date")["date"].transform("size")
    df["pct_day_records"] = df["records_in_day"] / expected_per_day * 100.0

    return df, qc


# =========================
# Conversión numérica
# =========================
def coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        "temp_in_c",
        "rh_in_pct",
        "rad_in_w_m2",
        "par_in_umol_m2_s",
        "dli_in_mol_m2_d",
        "vpd_in_kpa",
        "rad_acc_in_j_cm2_d",
        "dewpoint_in_c",
        "et_in_mm",
        "temp_out_c",
        "rh_out_pct",
        "rad_out_w_m2",
        "par_out_umol_m2_s",
        "dli_out_mol_m2_d",
        "vpd_out_kpa",
        "rad_acc_out_j_cm2_d",
        "et_out_mm",
        "dewpoint_out_c",
    ]
    for col in numeric_cols:
        df[col] = safe_numeric(df[col])
    return df


# =========================
# Agregación diaria
# =========================
def build_daily_table(df: pd.DataFrame, min_valid_pct: float = 80.0) -> pd.DataFrame:
    # Para ET diaria, guardamos tanto el último valor válido como el máximo diario.
    # El valor operativo recomendado es el máximo diario, porque la ET viene acumulada.
    grouped = df.groupby("date", as_index=False).agg(
        datetime_first=("datetime", "min"),
        datetime_last=("datetime", "max"),
        n_records=("datetime", "size"),
        pct_day_records=("pct_day_records", "max"),

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

    # Último valor válido diario para ET
    et_last = df.groupby("date").agg(
        et_in_daily_last=("et_in_mm", last_valid),
        et_out_daily_last=("et_out_mm", last_valid),
    ).reset_index()

    daily = grouped.merge(et_last, on="date", how="left")

    # Valor operativo recomendado
    daily["et_in_daily"] = daily["et_in_daily_max"]
    daily["et_out_daily"] = daily["et_out_daily_max"]

    # Calidad de día
    daily["is_valid_day"] = daily["pct_day_records"] >= min_valid_pct

    # Diferencia entre "last" y "max", útil para diagnosticar reinicios o faltantes
    daily["et_in_last_minus_max"] = daily["et_in_daily_last"] - daily["et_in_daily_max"]
    daily["et_out_last_minus_max"] = daily["et_out_daily_last"] - daily["et_out_daily_max"]

    return daily


# =========================
# Main
# =========================
def main() -> None:
    df = load_station_sheet(INPUT_XLSX, SHEET_NAME)
    df = build_datetime(df)
    df = coerce_numeric_columns(df)
    df, qc = add_temporal_qc(df)

    daily = build_daily_table(df, min_valid_pct=80.0)

    # Guardar salidas
    df.to_csv(OUT_CLEAN_5MIN, index=False, encoding="utf-8")
    daily.to_csv(OUT_DAILY, index=False, encoding="utf-8")

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
    daily_summary = daily[summary_cols].copy()
    daily_summary.to_csv(OUT_DAILY_SUMMARY, index=False, encoding="utf-8")

    qc["daily_rows"] = int(len(daily))
    qc["valid_days_count"] = int(daily["is_valid_day"].sum())
    qc["invalid_days_count"] = int((~daily["is_valid_day"]).sum())

    with open(OUT_QC_JSON, "w", encoding="utf-8") as f:
        json.dump(qc, f, indent=2, ensure_ascii=False)

    print(f"Archivo limpio 5 min:   {OUT_CLEAN_5MIN}")
    print(f"Archivo diario completo:{OUT_DAILY}")
    print(f"Archivo diario resumen: {OUT_DAILY_SUMMARY}")
    print(f"Resumen QC:             {OUT_QC_JSON}")
    print("\nPrimeros días:")
    print(daily_summary.head(10).to_string(index=False))
   
if __name__ == "__main__":
    main()