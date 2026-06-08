from __future__ import annotations

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "data" / "processed"

OUT_TABLE_DIR = BASE_DIR / "data" / "article_tables"
OUT_FIG_DIR = BASE_DIR / "data" / "article_figures"

OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
OUT_FIG_DIR.mkdir(parents=True, exist_ok=True)

INPUT_ROI = INPUT_DIR / "landsat_lst_roi_timeseries.csv"
INPUT_DAILY = INPUT_DIR / "landsat_lst_daily_series.csv"
INPUT_ANALYSIS = INPUT_DIR / "station_landsat_analysis_ready.csv"
INPUT_SUMMARY = INPUT_DIR / "station_landsat_merge_summary.csv"

OUT_DIAGNOSTIC_TABLE = OUT_TABLE_DIR / "table_05_landsat_lst_diagnostic.csv"
OUT_VALID_PIXEL_FIG = OUT_FIG_DIR / "fig06_landsat_valid_pixel_pct.png"
OUT_LST_TAIR_FIG = OUT_FIG_DIR / "fig07_landsat_lst_vs_tair.png"
OUT_TEXT = BASE_DIR / "data" / "article_text" / "landsat_diagnostic_results.md"


def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def load_data():
    for path in [INPUT_ROI, INPUT_DAILY, INPUT_ANALYSIS, INPUT_SUMMARY]:
        ensure_file(path)

    roi = pd.read_csv(INPUT_ROI)
    daily = pd.read_csv(INPUT_DAILY)
    analysis = pd.read_csv(INPUT_ANALYSIS)
    summary = pd.read_csv(INPUT_SUMMARY)

    for df in [roi, daily, analysis]:
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

    numeric_cols = [
        "valid_pixel_pct",
        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "LST_C_cv_pct",
        "et_base_out_mm_d",
        "temp_out_mean",
        "lst_minus_ta_mean_c",
        "vpd_out_mean",
    ]

    for df in [roi, daily, analysis]:
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    return roi, daily, analysis, summary


def build_diagnostic_table(roi: pd.DataFrame, daily: pd.DataFrame, analysis: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(metric, value, note=""):
        rows.append({"metric": metric, "value": value, "note": note})

    add("n_landsat_roi_images", len(roi), "Imágenes Landsat extraídas sobre el ROI")
    add("n_landsat_daily_dates", len(daily), "Fechas Landsat depuradas a escala diaria")
    add("n_valid_roi_images", int(roi["is_valid_satellite_obs"].astype(str).str.lower().eq("true").sum()), "Imágenes válidas según máscara QA y umbral de píxeles válidos")
    add("n_analysis_ready", len(analysis), "Coincidencias válidas estación-Landsat")
    add("roi_date_start", roi["date"].min().strftime("%Y-%m-%d") if not roi.empty else "", "Primera fecha Landsat ROI")
    add("roi_date_end", roi["date"].max().strftime("%Y-%m-%d") if not roi.empty else "", "Última fecha Landsat ROI")
    add("analysis_date_start", analysis["date"].min().strftime("%Y-%m-%d") if not analysis.empty else "", "Primera fecha usada en análisis")
    add("analysis_date_end", analysis["date"].max().strftime("%Y-%m-%d") if not analysis.empty else "", "Última fecha usada en análisis")
    add("valid_pixel_pct_median_roi", roi["valid_pixel_pct"].median(), "Mediana de píxeles válidos en todas las escenas ROI")
    add("valid_pixel_pct_max_roi", roi["valid_pixel_pct"].max(), "Máximo porcentaje de píxeles válidos")
    add("mean_valid_pixel_pct_analysis", analysis["valid_pixel_pct"].mean() if not analysis.empty else "", "Promedio de píxeles válidos en fechas analysis-ready")
    add("mean_lst_c_analysis", analysis["LST_C_mean"].mean() if not analysis.empty else "", "LST media en fechas analysis-ready")
    add("mean_temp_out_analysis", analysis["temp_out_mean"].mean() if not analysis.empty else "", "Temperatura media exterior en fechas analysis-ready")
    add("mean_lst_minus_ta_analysis", analysis["lst_minus_ta_mean_c"].mean() if not analysis.empty else "", "Diferencia media LST - temperatura del aire")
    add("min_lst_minus_ta_analysis", analysis["lst_minus_ta_mean_c"].min() if not analysis.empty else "", "Mínima diferencia LST - temperatura del aire")
    add("max_lst_minus_ta_analysis", analysis["lst_minus_ta_mean_c"].max() if not analysis.empty else "", "Máxima diferencia LST - temperatura del aire")

    out = pd.DataFrame(rows)
    return out


def make_valid_pixel_figure(roi: pd.DataFrame):
    df = roi.copy().sort_values("date")

    plt.figure(figsize=(10, 5))
    plt.bar(df["date"].dt.strftime("%Y-%m-%d"), df["valid_pixel_pct"])
    plt.axhline(30, linestyle="--", linewidth=1.2, label="Umbral 30%")
    plt.xticks(rotation=90)
    plt.xlabel("Fecha Landsat")
    plt.ylabel("Píxeles válidos (%)")
    plt.title("Disponibilidad de píxeles válidos Landsat/LST sobre el ROI")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_VALID_PIXEL_FIG, dpi=300)
    plt.close()


def make_lst_tair_figure(analysis: pd.DataFrame):
    if analysis.empty:
        return

    df = analysis.copy().sort_values("date")

    plt.figure(figsize=(8, 5))
    plt.plot(df["date"], df["LST_C_mean"], marker="o", label="LST media")
    plt.plot(df["date"], df["temp_out_mean"], marker="o", label="Temperatura aire exterior")
    plt.xticks(rotation=45)
    plt.xlabel("Fecha")
    plt.ylabel("Temperatura (°C)")
    plt.title("Comparación descriptiva entre LST Landsat y temperatura del aire")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_LST_TAIR_FIG, dpi=300)
    plt.close()


def write_text(analysis: pd.DataFrame, roi: pd.DataFrame):
    n_roi = len(roi)
    n_valid = int(roi["is_valid_satellite_obs"].astype(str).str.lower().eq("true").sum())
    n_analysis = len(analysis)

    if n_analysis:
        date_start = analysis["date"].min().strftime("%Y-%m-%d")
        date_end = analysis["date"].max().strftime("%Y-%m-%d")
        mean_lst = analysis["LST_C_mean"].mean()
        mean_tair = analysis["temp_out_mean"].mean()
        mean_diff = analysis["lst_minus_ta_mean_c"].mean()
        min_diff = analysis["lst_minus_ta_mean_c"].min()
        max_diff = analysis["lst_minus_ta_mean_c"].max()
    else:
        date_start = date_end = "NA"
        mean_lst = mean_tair = mean_diff = min_diff = max_diff = float("nan")

    text = f"""# Resultados diagnósticos Landsat/LST

La rama térmica Landsat/LST produjo {n_roi} escenas sobre el ROI, de las cuales {n_valid} cumplieron el criterio de observación satelital válida. Después del cruce con la estación meteorológica se obtuvieron {n_analysis} fechas analysis-ready, en el periodo {date_start} a {date_end}.

La disponibilidad efectiva estuvo limitada principalmente por nubosidad, sombra o enmascaramiento de calidad, dado que la mayoría de escenas presentó porcentajes muy bajos de píxeles válidos. En las fechas útiles, la LST media fue de {mean_lst:.2f} °C y la temperatura media exterior de la estación fue de {mean_tair:.2f} °C. La diferencia LST - temperatura del aire tuvo un promedio de {mean_diff:.2f} °C, con un rango entre {min_diff:.2f} y {max_diff:.2f} °C.

Dado que el número de coincidencias válidas fue n = {n_analysis}, la rama Landsat/LST se interpreta como un diagnóstico exploratorio y no como una base suficiente para ajustar regresiones térmicas robustas. La LST se conserva como una variable remota conceptualmente relevante por su cercanía al balance energético superficial, pero la inferencia estadística queda limitada por el tamaño muestral.
"""

    OUT_TEXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TEXT.write_text(text, encoding="utf-8")


def main():
    roi, daily, analysis, summary = load_data()

    diagnostic = build_diagnostic_table(roi, daily, analysis)
    diagnostic.to_csv(OUT_DIAGNOSTIC_TABLE, index=False)

    make_valid_pixel_figure(roi)
    make_lst_tair_figure(analysis)
    write_text(analysis, roi)

    print("\n=== DIAGNÓSTICO LANDSAT/LST ===")
    print(diagnostic.to_string(index=False))
    print(f"\nTabla: {OUT_DIAGNOSTIC_TABLE}")
    print(f"Figura píxeles válidos: {OUT_VALID_PIXEL_FIG}")
    print(f"Figura LST vs Tair: {OUT_LST_TAIR_FIG}")
    print(f"Texto: {OUT_TEXT}")


if __name__ == "__main__":
    main()