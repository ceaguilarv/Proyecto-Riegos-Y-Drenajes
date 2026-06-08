from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent

PROCESSED = BASE_DIR / "data" / "processed"
TABLES = BASE_DIR / "data" / "article_tables"
FIGURES = BASE_DIR / "data" / "article_figures"
TEXT = BASE_DIR / "data" / "article_text"

TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)
TEXT.mkdir(parents=True, exist_ok=True)

INPUT_KC_STATS = PROCESSED / "dynamic_kc_etc_map_stats.csv"
INPUT_KC_PARAMS = PROCESSED / "dynamic_kc_parameters.json"
INPUT_SENTINEL_ANALYSIS = PROCESSED / "station_sentinel_analysis_ready.csv"

OUT_TABLE_SUMMARY = TABLES / "table_08_dynamic_kc_etc_summary.csv"
OUT_TABLE_BY_DATE = TABLES / "table_09_dynamic_kc_etc_by_date.csv"

OUT_FIG_ETC_TIMESERIES = FIGURES / "fig08_dynamic_etc_timeseries.png"
OUT_FIG_KC_TIMESERIES = FIGURES / "fig09_dynamic_kc_timeseries.png"
OUT_FIG_ET_BASE_VS_ETC = FIGURES / "fig10_et_base_vs_etc_dynamic.png"

OUT_TEXT = TEXT / "dynamic_kc_etc_results.md"


def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def pearson_r(x: pd.Series, y: pd.Series) -> float:
    sub = pd.concat([x, y], axis=1).dropna()
    if len(sub) < 3:
        return np.nan
    return float(sub.iloc[:, 0].corr(sub.iloc[:, 1], method="pearson"))


def load_data() -> tuple[pd.DataFrame, dict]:
    ensure_file(INPUT_KC_STATS)
    ensure_file(INPUT_KC_PARAMS)

    kc = pd.read_csv(INPUT_KC_STATS)
    kc["date"] = pd.to_datetime(kc["date"], errors="coerce")
    kc = kc.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    with open(INPUT_KC_PARAMS, "r", encoding="utf-8") as f:
        params = json.load(f)

    numeric_cols = [
        "et_base_out_mm_d",
        "SAVI_mean",
        "NDVI_mean",
        "Kc_SAVI_dynamic_mean",
        "Kc_SAVI_dynamic_median",
        "Kc_SAVI_dynamic_stdDev",
        "Kc_SAVI_dynamic_min",
        "Kc_SAVI_dynamic_max",
        "Kc_NDVI_dynamic_mean",
        "Kc_NDVI_dynamic_median",
        "Kc_NDVI_dynamic_stdDev",
        "Kc_NDVI_dynamic_min",
        "Kc_NDVI_dynamic_max",
        "ETc_SAVI_mm_d_mean",
        "ETc_SAVI_mm_d_median",
        "ETc_SAVI_mm_d_stdDev",
        "ETc_SAVI_mm_d_min",
        "ETc_SAVI_mm_d_max",
        "ETc_NDVI_mm_d_mean",
        "ETc_NDVI_mm_d_median",
        "ETc_NDVI_mm_d_stdDev",
        "ETc_NDVI_mm_d_min",
        "ETc_NDVI_mm_d_max",
    ]

    for col in numeric_cols:
        if col in kc.columns:
            kc[col] = pd.to_numeric(kc[col], errors="coerce")

    return kc, params


def build_by_date_table(kc: pd.DataFrame) -> pd.DataFrame:
    out = kc.copy()

    out["date"] = out["date"].dt.strftime("%Y-%m-%d")

    # Diferencias entre ET base y ETc dinámica
    out["ETc_SAVI_minus_ET_base"] = out["ETc_SAVI_mm_d_mean"] - out["et_base_out_mm_d"]
    out["ETc_NDVI_minus_ET_base"] = out["ETc_NDVI_mm_d_mean"] - out["et_base_out_mm_d"]

    out["ETc_SAVI_pct_of_ET_base"] = np.where(
        out["et_base_out_mm_d"] > 0,
        out["ETc_SAVI_mm_d_mean"] / out["et_base_out_mm_d"] * 100,
        np.nan,
    )

    out["ETc_NDVI_pct_of_ET_base"] = np.where(
        out["et_base_out_mm_d"] > 0,
        out["ETc_NDVI_mm_d_mean"] / out["et_base_out_mm_d"] * 100,
        np.nan,
    )

    keep = [
        "date",
        "et_base_out_mm_d",
        "SAVI_mean",
        "Kc_SAVI_dynamic_mean",
        "Kc_SAVI_dynamic_stdDev",
        "ETc_SAVI_mm_d_mean",
        "ETc_SAVI_mm_d_stdDev",
        "ETc_SAVI_minus_ET_base",
        "ETc_SAVI_pct_of_ET_base",
        "NDVI_mean",
        "Kc_NDVI_dynamic_mean",
        "Kc_NDVI_dynamic_stdDev",
        "ETc_NDVI_mm_d_mean",
        "ETc_NDVI_mm_d_stdDev",
        "ETc_NDVI_minus_ET_base",
        "ETc_NDVI_pct_of_ET_base",
        "valid_pixel_pct",
    ]

    keep = [c for c in keep if c in out.columns]
    return out[keep].round(3)


def build_summary_table(kc: pd.DataFrame, params: dict) -> pd.DataFrame:
    rows = []

    def add(metric, value, interpretation):
        rows.append({
            "metric": metric,
            "value": value,
            "interpretation": interpretation,
        })

    n = len(kc)

    add("n_dates", n, "Fechas Sentinel usadas para Kc dinámico.")
    add("date_start", kc["date"].min().strftime("%Y-%m-%d"), "Primera fecha con Kc dinámico.")
    add("date_end", kc["date"].max().strftime("%Y-%m-%d"), "Última fecha con Kc dinámico.")
    add("kc_min_assumed", params.get("kc_min"), "Límite inferior asumido para Kc dinámico exploratorio.")
    add("kc_max_assumed", params.get("kc_max"), "Límite superior asumido para Kc dinámico exploratorio.")
    add("main_vi", params.get("main_vi"), "Índice principal usado para la rama Kc.")
    add("comparison_vi", params.get("comparison_vi"), "Índice usado como comparación.")

    add("mean_et_base_mm_d", round(kc["et_base_out_mm_d"].mean(), 3), "ET base media de estación en fechas Sentinel.")
    add("mean_kc_savi", round(kc["Kc_SAVI_dynamic_mean"].mean(), 3), "Kc dinámico medio basado en SAVI.")
    add("min_kc_savi", round(kc["Kc_SAVI_dynamic_mean"].min(), 3), "Mínimo temporal del Kc medio SAVI.")
    add("max_kc_savi", round(kc["Kc_SAVI_dynamic_mean"].max(), 3), "Máximo temporal del Kc medio SAVI.")
    add("mean_etc_savi_mm_d", round(kc["ETc_SAVI_mm_d_mean"].mean(), 3), "ETc dinámica media basada en SAVI.")
    add("min_etc_savi_mm_d", round(kc["ETc_SAVI_mm_d_mean"].min(), 3), "Mínima ETc media basada en SAVI.")
    add("max_etc_savi_mm_d", round(kc["ETc_SAVI_mm_d_mean"].max(), 3), "Máxima ETc media basada en SAVI.")

    add("mean_kc_ndvi", round(kc["Kc_NDVI_dynamic_mean"].mean(), 3), "Kc dinámico medio basado en NDVI.")
    add("mean_etc_ndvi_mm_d", round(kc["ETc_NDVI_mm_d_mean"].mean(), 3), "ETc dinámica media basada en NDVI.")

    savi_pct = (kc["ETc_SAVI_mm_d_mean"] / kc["et_base_out_mm_d"] * 100).mean()
    ndvi_pct = (kc["ETc_NDVI_mm_d_mean"] / kc["et_base_out_mm_d"] * 100).mean()

    add("mean_etc_savi_pct_of_et_base", round(savi_pct, 2), "ETc SAVI como porcentaje medio de ET base.")
    add("mean_etc_ndvi_pct_of_et_base", round(ndvi_pct, 2), "ETc NDVI como porcentaje medio de ET base.")

    add(
        "r_et_base_vs_etc_savi",
        round(pearson_r(kc["et_base_out_mm_d"], kc["ETc_SAVI_mm_d_mean"]), 3),
        "Correlación descriptiva; alta por construcción matemática ETc = ET_base × Kc.",
    )

    add(
        "r_et_base_vs_kc_savi",
        round(pearson_r(kc["et_base_out_mm_d"], kc["Kc_SAVI_dynamic_mean"]), 3),
        "Relación entre demanda base y estado espectral; útil para interpretación, no validación.",
    )

    add(
        "r_kc_savi_vs_kc_ndvi",
        round(pearson_r(kc["Kc_SAVI_dynamic_mean"], kc["Kc_NDVI_dynamic_mean"]), 3),
        "Consistencia entre los dos enfoques de Kc dinámico.",
    )

    add(
        "mean_spatial_sd_kc_savi",
        round(kc["Kc_SAVI_dynamic_stdDev"].mean(), 4),
        "Variabilidad espacial media del Kc SAVI dentro del ROI.",
    )

    add(
        "mean_spatial_sd_etc_savi",
        round(kc["ETc_SAVI_mm_d_stdDev"].mean(), 4),
        "Variabilidad espacial media de ETc SAVI dentro del ROI.",
    )

    add(
        "interpretation_status",
        "exploratory_spatialization",
        "El producto espacializa ET base según vigor/cobertura, pero no valida ET real.",
    )

    return pd.DataFrame(rows)


def make_figures(kc: pd.DataFrame) -> None:
    df = kc.copy().sort_values("date")

    # Figura ETc
    plt.figure(figsize=(10, 5))
    plt.plot(df["date"], df["et_base_out_mm_d"], marker="o", label="ET base estación")
    plt.plot(df["date"], df["ETc_SAVI_mm_d_mean"], marker="o", label="ETc dinámica SAVI")
    plt.plot(df["date"], df["ETc_NDVI_mm_d_mean"], marker="o", label="ETc dinámica NDVI")
    plt.xticks(rotation=45)
    plt.xlabel("Fecha")
    plt.ylabel("Lámina (mm/día)")
    plt.title("ET base y ETc dinámica derivada de Kc espectral")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_FIG_ETC_TIMESERIES, dpi=300)
    plt.close()

    # Figura Kc
    plt.figure(figsize=(10, 5))
    plt.plot(df["date"], df["Kc_SAVI_dynamic_mean"], marker="o", label="Kc dinámico SAVI")
    plt.plot(df["date"], df["Kc_NDVI_dynamic_mean"], marker="o", label="Kc dinámico NDVI")
    plt.xticks(rotation=45)
    plt.xlabel("Fecha")
    plt.ylabel("Kc dinámico")
    plt.title("Evolución temporal del Kc dinámico")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_FIG_KC_TIMESERIES, dpi=300)
    plt.close()

    # Figura ET base vs ETc
    plt.figure(figsize=(6, 5))
    plt.scatter(df["et_base_out_mm_d"], df["ETc_SAVI_mm_d_mean"], label="SAVI")
    plt.scatter(df["et_base_out_mm_d"], df["ETc_NDVI_mm_d_mean"], label="NDVI")
    plt.xlabel("ET base estación (mm/día)")
    plt.ylabel("ETc dinámica media (mm/día)")
    plt.title("Relación descriptiva entre ET base y ETc dinámica")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_FIG_ET_BASE_VS_ETC, dpi=300)
    plt.close()


def write_text(summary: pd.DataFrame, by_date: pd.DataFrame, params: dict) -> None:
    def val(metric):
        s = summary.loc[summary["metric"] == metric, "value"]
        return s.iloc[0] if not s.empty else "NA"

    text = f"""# Resultados de Kc dinámico y ETc espacial

Se construyó un Kc dinámico exploratorio a partir de índices espectrales Sentinel-2, usando SAVI como índice principal y NDVI como comparación metodológica. El Kc se escaló dentro del rango observado de cada índice en las fechas analysis-ready y se acotó entre {val("kc_min_assumed")} y {val("kc_max_assumed")}. Por tanto, este Kc debe interpretarse como un coeficiente relativo de vigor/cobertura para el sitio y periodo analizado, no como un Kc universal calibrado.

La serie incluyó {val("n_dates")} fechas entre {val("date_start")} y {val("date_end")}. El Kc dinámico basado en SAVI tuvo un valor medio de {val("mean_kc_savi")}, con un rango temporal entre {val("min_kc_savi")} y {val("max_kc_savi")}. Al multiplicar la ET base de estación por el Kc dinámico, la ETc SAVI media fue de {val("mean_etc_savi_mm_d")} mm/día, con valores entre {val("min_etc_savi_mm_d")} y {val("max_etc_savi_mm_d")} mm/día.

En promedio, la ETc basada en SAVI representó el {val("mean_etc_savi_pct_of_et_base")}% de la ET base de estación, mientras que la ETc basada en NDVI representó el {val("mean_etc_ndvi_pct_of_et_base")}% de la ET base. La correlación entre ET base y ETc SAVI fue de r = {val("r_et_base_vs_etc_savi")}; sin embargo, esta relación es esperable por construcción matemática, ya que ETc se calculó como ET base multiplicada por Kc dinámico.

El aporte principal de esta rama no es validar una ET satelital independiente, sino espacializar la ET de estación en función del estado espectral de la cobertura vegetal. En ese sentido, el producto Kc/ETc dinámico permite pasar de una señal puntual de estación a una superficie espacialmente variable dentro del ROI, conservando una interpretación exploratoria.
"""

    OUT_TEXT.write_text(text, encoding="utf-8")


def main() -> None:
    kc, params = load_data()

    by_date = build_by_date_table(kc)
    summary = build_summary_table(kc, params)

    by_date.to_csv(OUT_TABLE_BY_DATE, index=False)
    summary.to_csv(OUT_TABLE_SUMMARY, index=False)

    make_figures(kc)
    write_text(summary, by_date, params)

    print("\n=== EVALUACIÓN Kc DINÁMICO / ETc ===")
    print("\nResumen:")
    print(summary.to_string(index=False))

    print("\nPor fecha:")
    print(by_date.to_string(index=False))

    print("\nSalidas:")
    print(f"Tabla resumen: {OUT_TABLE_SUMMARY}")
    print(f"Tabla por fecha: {OUT_TABLE_BY_DATE}")
    print(f"Figura ETc: {OUT_FIG_ETC_TIMESERIES}")
    print(f"Figura Kc: {OUT_FIG_KC_TIMESERIES}")
    print(f"Figura ET base vs ETc: {OUT_FIG_ET_BASE_VS_ETC}")
    print(f"Texto: {OUT_TEXT}")


if __name__ == "__main__":
    main()