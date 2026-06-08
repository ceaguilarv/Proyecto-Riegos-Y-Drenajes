from __future__ import annotations

from pathlib import Path
import json
import pandas as pd
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
PROCESSED = BASE_DIR / "data" / "processed"
TABLES = BASE_DIR / "data" / "article_tables"
TEXT = BASE_DIR / "data" / "article_text"

OUT_AUDIT = TABLES / "table_06_final_project_audit.csv"
OUT_REPORT = TEXT / "final_project_audit_report.md"

TABLES.mkdir(parents=True, exist_ok=True)
TEXT.mkdir(parents=True, exist_ok=True)


def read_csv_safe(path: Path, parse_date: bool = False) -> pd.DataFrame:
    if not path.exists():
        print(f"ADVERTENCIA: no existe {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    if parse_date and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def add(rows, section, metric, value, interpretation=""):
    rows.append({
        "section": section,
        "metric": metric,
        "value": value,
        "interpretation": interpretation,
    })


def main():
    rows = []

    # =====================
    # Estación
    # =====================
    station = read_csv_safe(PROCESSED / "station_daily_exterior_ready.csv", parse_date=True)

    if not station.empty:
        add(rows, "station", "n_station_days", len(station), "Días diarios disponibles después de corregir fechas.")
        add(rows, "station", "date_start", station["date"].min().strftime("%Y-%m-%d"), "Inicio real de la serie diaria.")
        add(rows, "station", "date_end", station["date"].max().strftime("%Y-%m-%d"), "Fin real de la serie diaria.")
        add(rows, "station", "n_valid_analysis_days", int(station["is_valid_day_analysis"].sum()), "Días válidos por cobertura y variables meteorológicas.")
        add(rows, "station", "mean_et_base_out_mm_d", round(station["et_base_out_mm_d"].mean(), 3), "ET diaria media de estación exterior.")
        add(rows, "station", "min_et_base_out_mm_d", round(station["et_base_out_mm_d"].min(), 3), "ET diaria mínima.")
        add(rows, "station", "max_et_base_out_mm_d", round(station["et_base_out_mm_d"].max(), 3), "ET diaria máxima.")
        add(rows, "station", "mean_temp_out_c", round(station["temp_out_mean"].mean(), 3), "Temperatura exterior media.")
        add(rows, "station", "mean_rad_out", round(station["rad_out_mean"].mean(), 3), "Radiación media exterior.")

    # =====================
    # Sentinel merge
    # =====================
    sentinel_summary = read_csv_safe(PROCESSED / "station_sentinel_merge_summary.csv")
    sentinel_analysis = read_csv_safe(PROCESSED / "station_sentinel_analysis_ready.csv", parse_date=True)
    sentinel_best = read_csv_safe(PROCESSED / "station_sentinel_best_models.csv")

    if not sentinel_summary.empty:
        for _, r in sentinel_summary.iterrows():
            add(rows, "sentinel_merge", str(r["metric"]), round(float(r["value"]), 6), "Resumen del cruce estación-Sentinel.")

    if not sentinel_analysis.empty:
        add(rows, "sentinel_analysis", "date_start", sentinel_analysis["date"].min().strftime("%Y-%m-%d"), "Primera fecha analysis-ready Sentinel.")
        add(rows, "sentinel_analysis", "date_end", sentinel_analysis["date"].max().strftime("%Y-%m-%d"), "Última fecha analysis-ready Sentinel.")
        add(rows, "sentinel_analysis", "n_analysis_ready", len(sentinel_analysis), "Observaciones usadas en regresiones Sentinel.")

    if not sentinel_best.empty:
        best_same_day = sentinel_best.loc[sentinel_best["target"] == "et_base_out_mm_d"].copy()
        if not best_same_day.empty:
            best_same_day = best_same_day.sort_values(["r2", "rmse"], ascending=[False, True]).iloc[0]
            add(rows, "sentinel_best_model", "target", best_same_day["target"], "Variable dependiente del mejor modelo mismo día.")
            add(rows, "sentinel_best_model", "predictor", best_same_day["predictor"], "Mejor proxy espectral para ET diaria.")
            add(rows, "sentinel_best_model", "n", int(best_same_day["n"]), "Tamaño muestral del modelo principal.")
            add(rows, "sentinel_best_model", "pearson_r", round(float(best_same_day["pearson_r"]), 6), "Correlación de Pearson.")
            add(rows, "sentinel_best_model", "spearman_rho", round(float(best_same_day["spearman_rho"]), 6), "Correlación de Spearman.")
            add(rows, "sentinel_best_model", "r2", round(float(best_same_day["r2"]), 6), "Coeficiente de determinación.")
            add(rows, "sentinel_best_model", "rmse", round(float(best_same_day["rmse"]), 6), "Error cuadrático medio en mm/día.")
            add(rows, "sentinel_best_model", "mae", round(float(best_same_day["mae"]), 6), "Error absoluto medio en mm/día.")
            add(rows, "sentinel_best_model", "slope", round(float(best_same_day["slope"]), 6), "Pendiente del modelo.")
            add(rows, "sentinel_best_model", "intercept", round(float(best_same_day["intercept"]), 6), "Intercepto del modelo.")

    # =====================
    # Robustez
    # =====================
    robustness = read_csv_safe(PROCESSED / "robustness_summary.csv")
    if not robustness.empty:
        for _, r in robustness.iterrows():
            value = r["value"]
            try:
                value_out = round(float(value), 6)
            except Exception:
                value_out = value
            add(rows, "sentinel_robustness", str(r["metric"]), value_out, "Resumen de robustez del modelo principal Sentinel.")

    # =====================
    # Landsat
    # =====================
    landsat_summary = read_csv_safe(PROCESSED / "station_landsat_merge_summary.csv")
    landsat_analysis = read_csv_safe(PROCESSED / "station_landsat_analysis_ready.csv", parse_date=True)
    landsat_diag = read_csv_safe(TABLES / "table_05_landsat_lst_diagnostic.csv")

    if not landsat_summary.empty:
        for _, r in landsat_summary.iterrows():
            add(rows, "landsat_merge", str(r["metric"]), round(float(r["value"]), 6), "Resumen del cruce estación-Landsat/LST.")

    if not landsat_analysis.empty:
        add(rows, "landsat_analysis", "date_start", landsat_analysis["date"].min().strftime("%Y-%m-%d"), "Primera fecha analysis-ready Landsat.")
        add(rows, "landsat_analysis", "date_end", landsat_analysis["date"].max().strftime("%Y-%m-%d"), "Última fecha analysis-ready Landsat.")
        add(rows, "landsat_analysis", "n_analysis_ready", len(landsat_analysis), "Coincidencias válidas estación-LST.")
        add(rows, "landsat_analysis", "mean_lst_c", round(landsat_analysis["LST_C_mean"].mean(), 3), "LST media en fechas válidas.")
        add(rows, "landsat_analysis", "mean_lst_minus_ta_c", round(landsat_analysis["lst_minus_ta_mean_c"].mean(), 3), "Diferencia media LST - temperatura del aire.")

    if not landsat_diag.empty:
        for _, r in landsat_diag.iterrows():
            add(rows, "landsat_diagnostic", str(r["metric"]), r["value"], str(r.get("note", "")))

    # =====================
    # Decisiones metodológicas
    # =====================
    add(rows, "methodological_decision", "sentinel_status", "usable_exploratory_model", "Sentinel-2 sí permite análisis exploratorio con regresiones simples, manteniendo cautela por n pequeño.")
    add(rows, "methodological_decision", "landsat_status", "diagnostic_only", "Landsat/LST no debe usarse para regresiones robustas porque solo tiene n=4.")
    add(rows, "methodological_decision", "main_result", "SAVI_mean", "SAVI fue el mejor proxy espectral para ET diaria del mismo día.")
    add(rows, "methodological_decision", "avoid_claim", "SAVI_or_LST_do_not_calculate_ET", "No afirmar que SAVI o LST calculan ET satelital.")

    audit = pd.DataFrame(rows)
    audit.to_csv(OUT_AUDIT, index=False)

    # Reporte markdown
    report = f"""# Auditoría final del proyecto ET estación–satélite

## Estado general

La serie meteorológica fue corregida y validada temporalmente. El rango real de estación es {station["date"].min().strftime("%Y-%m-%d") if not station.empty else "NA"} a {station["date"].max().strftime("%Y-%m-%d") if not station.empty else "NA"}, con {int(station["is_valid_day_analysis"].sum()) if not station.empty else "NA"} días válidos para análisis.

## Resultado Sentinel-2

Después de corregir fechas y reprocesar, la rama Sentinel-2 produjo {len(sentinel_analysis) if not sentinel_analysis.empty else "NA"} observaciones analysis-ready. El mejor modelo para ET diaria del mismo día fue:

- Target: ET diaria de estación.
- Predictor: SAVI_mean.
- n: {int(best_same_day["n"]) if not sentinel_best.empty and not best_same_day.empty else "NA"}.
- r: {round(float(best_same_day["pearson_r"]), 3) if not sentinel_best.empty and not best_same_day.empty else "NA"}.
- R²: {round(float(best_same_day["r2"]), 3) if not sentinel_best.empty and not best_same_day.empty else "NA"}.
- RMSE: {round(float(best_same_day["rmse"]), 3) if not sentinel_best.empty and not best_same_day.empty else "NA"} mm/día.

Este resultado se interpreta como evidencia exploratoria de asociación entre un proxy espectral y la ET de estación, no como validación de ET satelital.

## Resultado Landsat/LST

La rama Landsat/LST produjo {len(landsat_analysis) if not landsat_analysis.empty else "NA"} coincidencias válidas estación–LST. Esto no es suficiente para regresiones robustas. La rama se conserva como diagnóstico térmico exploratorio y como justificación de una línea futura.

## Decisión para el informe

- Usar Sentinel-2 como resultado principal.
- Presentar Landsat/LST como diagnóstico complementario.
- No forzar regresiones térmicas.
- Mantener lenguaje prudente: asociación, proxy, exploratorio.
"""

    OUT_REPORT.write_text(report, encoding="utf-8")

    print("\n=== AUDITORÍA FINAL GENERADA ===")
    print(audit.to_string(index=False))
    print(f"\nTabla audit: {OUT_AUDIT}")
    print(f"Reporte: {OUT_REPORT}")


if __name__ == "__main__":
    main()