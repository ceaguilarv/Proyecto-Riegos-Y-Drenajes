from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_5MIN = BASE_DIR / "data" / "processed" / "station_clean_5min.csv"
INPUT_DAILY = BASE_DIR / "data" / "processed" / "station_daily_summary.csv"

FIG_DIR = BASE_DIR / "outputs" / "figures" / "qc"
TAB_DIR = BASE_DIR / "outputs" / "tables"

FIG_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)

OUT_STATS = TAB_DIR / "qc_summary_stats.csv"


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def save_line_plot(
    df: pd.DataFrame,
    x: str,
    y_cols: list[str],
    title: str,
    ylabel: str,
    output_path: Path,
) -> None:
    plt.figure(figsize=(12, 5))
    for col in y_cols:
        plt.plot(df[x], df[col], label=col)
    plt.title(title)
    plt.xlabel("Fecha")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_bar_plot(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    ylabel: str,
    output_path: Path,
) -> None:
    plt.figure(figsize=(12, 5))
    plt.bar(df[x].astype(str), df[y])
    plt.title(title)
    plt.xlabel("Fecha")
    plt.ylabel(ylabel)
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


# =========================
# Lectura
# =========================
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    ensure_file(INPUT_5MIN)
    ensure_file(INPUT_DAILY)

    df_5min = pd.read_csv(INPUT_5MIN)
    df_daily = pd.read_csv(INPUT_DAILY)

    df_5min["datetime"] = pd.to_datetime(df_5min["datetime"], errors="coerce")
    df_daily["date"] = pd.to_datetime(df_daily["date"], errors="coerce")

    return df_5min, df_daily


# =========================
# Estadísticas resumidas
# =========================
def build_summary_stats(df_5min: pd.DataFrame, df_daily: pd.DataFrame) -> pd.DataFrame:
    stats_rows = []

    def add_stat(variable: str, series: pd.Series) -> None:
        stats_rows.append(
            {
                "variable": variable,
                "count": int(series.notna().sum()),
                "mean": float(series.mean()) if series.notna().any() else None,
                "min": float(series.min()) if series.notna().any() else None,
                "max": float(series.max()) if series.notna().any() else None,
            }
        )

    cols_to_check = [
        "temp_in_c",
        "temp_out_c",
        "rh_in_pct",
        "rh_out_pct",
        "rad_in_w_m2",
        "rad_out_w_m2",
        "vpd_in_kpa",
        "vpd_out_kpa",
        "et_in_mm",
        "et_out_mm",
    ]

    for col in cols_to_check:
        if col in df_5min.columns:
            add_stat(col, df_5min[col])

    if "et_in_daily" in df_daily.columns:
        add_stat("et_in_daily", df_daily["et_in_daily"])

    if "et_out_daily" in df_daily.columns:
        add_stat("et_out_daily", df_daily["et_out_daily"])

    stats = pd.DataFrame(stats_rows)
    return stats


# =========================
# Preparación diaria ampliada
# =========================
def build_daily_diagnostics(df_5min: pd.DataFrame, df_daily: pd.DataFrame) -> pd.DataFrame:
    # Estadísticos diarios adicionales desde 5 min
    extra = (
        df_5min.groupby(df_5min["datetime"].dt.floor("D"))
        .agg(
            temp_in_mean=("temp_in_c", "mean"),
            temp_in_min=("temp_in_c", "min"),
            temp_in_max=("temp_in_c", "max"),
            temp_out_mean=("temp_out_c", "mean"),
            temp_out_min=("temp_out_c", "min"),
            temp_out_max=("temp_out_c", "max"),
            rh_in_mean=("rh_in_pct", "mean"),
            rh_out_mean=("rh_out_pct", "mean"),
            vpd_in_mean=("vpd_in_kpa", "mean"),
            vpd_out_mean=("vpd_out_kpa", "mean"),
        )
        .reset_index()
        .rename(columns={"datetime": "date"})
    )

    merged = df_daily.merge(extra, on="date", how="left")
    return merged


# =========================
# Gráficos
# =========================
def make_figures(df_daily_diag: pd.DataFrame) -> None:
    # ET diaria
    save_line_plot(
        df=df_daily_diag,
        x="date",
        y_cols=["et_in_daily", "et_out_daily"],
        title="Evapotranspiración diaria reportada por la estación",
        ylabel="ET diaria (mm)",
        output_path=FIG_DIR / "qc_et_daily.png",
    )

    # Temperatura media diaria
    save_line_plot(
        df=df_daily_diag,
        x="date",
        y_cols=["temp_in_mean", "temp_out_mean"],
        title="Temperatura media diaria: interior vs exterior",
        ylabel="Temperatura (°C)",
        output_path=FIG_DIR / "qc_temp_daily.png",
    )

    # Humedad relativa media diaria
    save_line_plot(
        df=df_daily_diag,
        x="date",
        y_cols=["rh_in_mean", "rh_out_mean"],
        title="Humedad relativa media diaria: interior vs exterior",
        ylabel="Humedad relativa (%)",
        output_path=FIG_DIR / "qc_rh_daily.png",
    )

    # DPV medio diario
    save_line_plot(
        df=df_daily_diag,
        x="date",
        y_cols=["vpd_in_mean", "vpd_out_mean"],
        title="DPV medio diario: interior vs exterior",
        ylabel="DPV (kPa)",
        output_path=FIG_DIR / "qc_vpd_daily.png",
    )

    # Porcentaje de registros por día
    save_bar_plot(
        df=df_daily_diag,
        x="date",
        y="pct_day_records",
        title="Cobertura diaria de registros",
        ylabel="% de registros del día",
        output_path=FIG_DIR / "qc_valid_days.png",
    )


# =========================
# Log de control rápido
# =========================
def print_quick_report(df_daily_diag: pd.DataFrame) -> None:
    valid_days = int(df_daily_diag["is_valid_day"].sum())
    total_days = int(len(df_daily_diag))
    invalid_days = total_days - valid_days

    print("\n=== RESUMEN QC METEOROLÓGICO ===")
    print(f"Días totales:      {total_days}")
    print(f"Días válidos:      {valid_days}")
    print(f"Días inválidos:    {invalid_days}")

    if "et_in_daily" in df_daily_diag.columns and "et_out_daily" in df_daily_diag.columns:
        print(f"ET interna media:  {df_daily_diag['et_in_daily'].mean():.2f} mm/día")
        print(f"ET externa media:  {df_daily_diag['et_out_daily'].mean():.2f} mm/día")

    if "temp_in_mean" in df_daily_diag.columns and "temp_out_mean" in df_daily_diag.columns:
        print(f"T media int.:      {df_daily_diag['temp_in_mean'].mean():.2f} °C")
        print(f"T media ext.:      {df_daily_diag['temp_out_mean'].mean():.2f} °C")

    if "vpd_in_mean" in df_daily_diag.columns and "vpd_out_mean" in df_daily_diag.columns:
        print(f"DPV medio int.:    {df_daily_diag['vpd_in_mean'].mean():.2f} kPa")
        print(f"DPV medio ext.:    {df_daily_diag['vpd_out_mean'].mean():.2f} kPa")


# =========================
# Main
# =========================
def main() -> None:
    df_5min, df_daily = load_data()
    df_daily_diag = build_daily_diagnostics(df_5min, df_daily)

    stats = build_summary_stats(df_5min, df_daily)
    stats.to_csv(OUT_STATS, index=False, encoding="utf-8")

    make_figures(df_daily_diag)
    print_quick_report(df_daily_diag)

    print("\nArchivos generados:")
    print(f"- {OUT_STATS}")
    print(f"- {FIG_DIR / 'qc_et_daily.png'}")
    print(f"- {FIG_DIR / 'qc_temp_daily.png'}")
    print(f"- {FIG_DIR / 'qc_rh_daily.png'}")
    print(f"- {FIG_DIR / 'qc_vpd_daily.png'}")
    print(f"- {FIG_DIR / 'qc_valid_days.png'}")


if __name__ == "__main__":
    main()