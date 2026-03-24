from __future__ import annotations

from pathlib import Path
import json
import pandas as pd
import numpy as np


# ============================================================
# 11_write_results_narrative_support.py
# Extrae números clave y genera borradores de redacción para
# resultados, captions de figuras y notas de tablas.
# ============================================================


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "data" / "processed"
DEFAULT_TABLE_DIR = BASE_DIR / "data" / "article_tables"
DEFAULT_FIG_DIR = BASE_DIR / "data" / "article_figures"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "article_text"

FALLBACK_INPUT_DIR = BASE_DIR
FALLBACK_TABLE_DIR = BASE_DIR / "article_tables"
FALLBACK_FIG_DIR = BASE_DIR / "article_figures"
FALLBACK_OUTPUT_DIR = BASE_DIR / "article_text"


TARGET_LABELS = {
    "et_base_out_mm_d": "ET diaria (mismo día)",
    "et_base_out_mm_d_w3_mean": "ET media móvil 3 días",
    "et_base_out_mm_d_w5_mean": "ET media móvil 5 días",
    "et_base_out_mm_d_w7_mean": "ET media móvil 7 días",
    "et_base_out_mm_d_w3_sum": "ET acumulada 3 días",
    "et_base_out_mm_d_w5_sum": "ET acumulada 5 días",
    "et_base_out_mm_d_w7_sum": "ET acumulada 7 días",
}

PREDICTOR_LABELS = {
    "NDVI_mean": "NDVI",
    "EVI_mean": "EVI",
    "SAVI_mean": "SAVI",
    "NDRE_mean": "NDRE",
}

TEMPORAL_ORDER = [
    "et_base_out_mm_d",
    "et_base_out_mm_d_w3_mean",
    "et_base_out_mm_d_w5_mean",
    "et_base_out_mm_d_w7_mean",
    "et_base_out_mm_d_w3_sum",
    "et_base_out_mm_d_w5_sum",
    "et_base_out_mm_d_w7_sum",
]


# =========================
# Rutas
# =========================
def resolve_dirs() -> tuple[Path, Path, Path, Path]:
    if DEFAULT_INPUT_DIR.exists():
        input_dir = DEFAULT_INPUT_DIR
        table_dir = DEFAULT_TABLE_DIR
        fig_dir = DEFAULT_FIG_DIR
        output_dir = DEFAULT_OUTPUT_DIR
    else:
        input_dir = FALLBACK_INPUT_DIR
        table_dir = FALLBACK_TABLE_DIR
        fig_dir = FALLBACK_FIG_DIR
        output_dir = FALLBACK_OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, table_dir, fig_dir, output_dir


INPUT_DIR, TABLE_DIR, FIG_DIR, OUTPUT_DIR = resolve_dirs()

INPUT_ANALYSIS = INPUT_DIR / "station_sentinel_analysis_ready.csv"
INPUT_REGS = TABLE_DIR / "table_02_all_regressions_supplement.csv"
INPUT_CORRS = TABLE_DIR / "table_03_all_correlations_supplement.csv"
INPUT_BEST_ARTICLE = TABLE_DIR / "table_01_best_models_article.csv"
INPUT_ROB_SUMMARY = INPUT_DIR / "robustness_summary.csv"
INPUT_BOOT_SUMMARY = INPUT_DIR / "robustness_bootstrap_summary.csv"
INPUT_PERM_SUMMARY = INPUT_DIR / "robustness_permutation_summary.csv"
INPUT_LOO = INPUT_DIR / "robustness_leave_one_out.csv"

OUT_JSON = OUTPUT_DIR / "results_key_numbers.json"
OUT_RESULTS_MD = OUTPUT_DIR / "results_sentences_draft.md"
OUT_CAPTIONS_MD = OUTPUT_DIR / "figure_captions_draft.md"
OUT_TABLE_NOTES_MD = OUTPUT_DIR / "table_notes_draft.md"
OUT_METHODS_MD = OUTPUT_DIR / "results_methods_bridge_draft.md"


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def load_csv(path: Path, parse_dates: bool = False) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)
    if parse_dates and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def to_float(value, default=np.nan) -> float:
    try:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return default
        return float(value)
    except Exception:
        return default


def fmt_num(value, ndigits=3) -> str:
    value = to_float(value)
    if pd.isna(value):
        return "NA"
    return f"{value:.{ndigits}f}"


def fmt_int(value) -> str:
    value = to_float(value)
    if pd.isna(value):
        return "NA"
    return str(int(round(value)))


def fmt_date(value) -> str:
    if pd.isna(value):
        return "NA"
    if not isinstance(value, pd.Timestamp):
        value = pd.to_datetime(value, errors="coerce")
    if pd.isna(value):
        return "NA"
    return value.strftime("%Y-%m-%d")


def label_target(target: str) -> str:
    return TARGET_LABELS.get(target, target)


def label_predictor(pred: str) -> str:
    return PREDICTOR_LABELS.get(pred, pred)


def get_summary_value(df: pd.DataFrame, metric: str):
    sub = df.loc[df["metric"] == metric, "value"]
    if sub.empty:
        return np.nan
    return sub.iloc[0]


def safe_row(df: pd.DataFrame, mask) -> pd.Series | None:
    sub = df.loc[mask]
    if sub.empty:
        return None
    return sub.iloc[0]


def relation_strength_from_r2(r2: float) -> str:
    r2 = to_float(r2)
    if pd.isna(r2):
        return "indeterminada"
    if r2 >= 0.70:
        return "alta"
    if r2 >= 0.50:
        return "relativamente fuerte"
    if r2 >= 0.30:
        return "moderada"
    if r2 >= 0.10:
        return "débil"
    return "muy débil"


def predictor_rank_text(regs_same_day: pd.DataFrame) -> str:
    lines = []
    for _, row in regs_same_day.iterrows():
        rank_col = "rank_within_target" if "rank_within_target" in regs_same_day.columns else "rank"
        lines.append(
            f"{int(row[rank_col])}. {row['predictor_label']} "
            f"(r = {fmt_num(row['pearson_r'])}, R² = {fmt_num(row['r2'])}, RMSE = {fmt_num(row['rmse'])})"
        )
    return "; ".join(lines)


# =========================
# Extracción de números clave
# =========================
def build_key_numbers() -> dict:
    analysis = load_csv(INPUT_ANALYSIS, parse_dates=True)
    regs = load_csv(INPUT_REGS)
    corrs = load_csv(INPUT_CORRS)
    best_article = load_csv(INPUT_BEST_ARTICLE)
    rob_summary = load_csv(INPUT_ROB_SUMMARY)
    boot_summary = load_csv(INPUT_BOOT_SUMMARY)
    perm_summary = load_csv(INPUT_PERM_SUMMARY)
    loo = load_csv(INPUT_LOO)

    for col in ["n", "pearson_r", "spearman_rho", "r2", "rmse", "mae", "bias", "slope", "intercept"]:
        for df in [regs, corrs, best_article]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    date_start = analysis["date"].min() if "date" in analysis.columns and not analysis.empty else pd.NaT
    date_end = analysis["date"].max() if "date" in analysis.columns and not analysis.empty else pd.NaT

    best_same_day = best_article.loc[best_article["target"] == "et_base_out_mm_d"].copy()
    if best_same_day.empty:
        raise ValueError("No se encontró el mejor modelo de mismo día en la tabla de artículo.")
    best_same_day = best_same_day.sort_values(["r2", "rmse"], ascending=[False, True]).iloc[0]

    regs_same_day = regs.loc[regs["target"] == "et_base_out_mm_d"].copy()
    regs_same_day = regs_same_day.sort_values(["rank_within_target", "r2"], ascending=[True, False]).reset_index(drop=True)

    corr_best_predictor = corrs.loc[corrs["predictor"] == best_same_day["predictor"]].copy()
    order_map = {k: i for i, k in enumerate(TEMPORAL_ORDER)}
    if not corr_best_predictor.empty:
        corr_best_predictor["target_order"] = corr_best_predictor["target"].map(order_map).fillna(999)
        corr_best_predictor = corr_best_predictor.sort_values("target_order").reset_index(drop=True)

    perm_row = perm_summary.iloc[0] if not perm_summary.empty else pd.Series(dtype=object)

    boot_slope = safe_row(boot_summary, boot_summary["metric"] == "slope")
    boot_r2 = safe_row(boot_summary, boot_summary["metric"] == "r2")
    boot_r = safe_row(boot_summary, boot_summary["metric"] == "pearson_r")

    loo_top = loo.iloc[0] if not loo.empty else pd.Series(dtype=object)

    keys = {
        "dataset": {
            "n_obs": int(len(analysis)),
            "date_start": fmt_date(date_start),
            "date_end": fmt_date(date_end),
        },
        "best_same_day_model": {
            "target": str(best_same_day["target"]),
            "target_label": str(best_same_day["target_label"]),
            "predictor": str(best_same_day["predictor"]),
            "predictor_label": str(best_same_day["predictor_label"]),
            "n": int(best_same_day["n"]),
            "pearson_r": to_float(best_same_day["pearson_r"]),
            "spearman_rho": to_float(best_same_day["spearman_rho"]),
            "r2": to_float(best_same_day["r2"]),
            "rmse": to_float(best_same_day["rmse"]),
            "mae": to_float(best_same_day["mae"]),
            "bias": to_float(best_same_day["bias"]),
            "slope": to_float(best_same_day["slope"]),
            "intercept": to_float(best_same_day["intercept"]),
            "equation": str(best_same_day["equation"]),
            "strength_label": relation_strength_from_r2(best_same_day["r2"]),
        },
        "same_day_predictor_ranking": [
            {
                "rank": int(row["rank_within_target"]),
                "predictor": str(row["predictor"]),
                "predictor_label": str(row["predictor_label"]),
                "pearson_r": to_float(row["pearson_r"]),
                "r2": to_float(row["r2"]),
                "rmse": to_float(row["rmse"]),
            }
            for _, row in regs_same_day.iterrows()
        ],
        "best_predictor_temporal_profile": [
            {
                "target": str(row["target"]),
                "target_label": str(row["target_label"]),
                "pearson_r": to_float(row["pearson_r"]),
                "spearman_rho": to_float(row.get("spearman_rho", np.nan)),
                "rank_within_target": int(row.get("rank_within_target", np.nan)) if not pd.isna(row.get("rank_within_target", np.nan)) else None,
            }
            for _, row in corr_best_predictor.iterrows()
        ],
        "robustness": {
            "n_full": int(to_float(get_summary_value(rob_summary, "n_full"))),
            "full_r": to_float(get_summary_value(rob_summary, "full_pearson_r")),
            "full_r2": to_float(get_summary_value(rob_summary, "full_r2")),
            "full_rmse": to_float(get_summary_value(rob_summary, "full_rmse")),
            "full_slope": to_float(get_summary_value(rob_summary, "full_slope")),
            "loo_min_r2": to_float(get_summary_value(rob_summary, "loo_min_r2")),
            "loo_max_r2": to_float(get_summary_value(rob_summary, "loo_max_r2")),
            "loo_min_r": to_float(get_summary_value(rob_summary, "loo_min_pearson_r")),
            "loo_max_r": to_float(get_summary_value(rob_summary, "loo_max_pearson_r")),
            "loo_max_abs_delta_r2": to_float(get_summary_value(rob_summary, "loo_max_abs_delta_r2")),
            "loo_max_abs_delta_r": to_float(get_summary_value(rob_summary, "loo_max_abs_delta_pearson_r")),
            "loo_most_influential_date": str(get_summary_value(rob_summary, "loo_most_influential_date")),
            "bootstrap_slope_mean": to_float(get_summary_value(rob_summary, "bootstrap_slope_mean")),
            "bootstrap_slope_p02_5": to_float(get_summary_value(rob_summary, "bootstrap_slope_p02_5")),
            "bootstrap_slope_p97_5": to_float(get_summary_value(rob_summary, "bootstrap_slope_p97_5")),
            "bootstrap_r2_mean": to_float(get_summary_value(rob_summary, "bootstrap_r2_mean")),
            "bootstrap_r2_p02_5": to_float(get_summary_value(rob_summary, "bootstrap_r2_p02_5")),
            "bootstrap_r2_p97_5": to_float(get_summary_value(rob_summary, "bootstrap_r2_p97_5")),
            "bootstrap_r_mean": to_float(get_summary_value(rob_summary, "bootstrap_pearson_r_mean")),
            "bootstrap_r_p02_5": to_float(get_summary_value(rob_summary, "bootstrap_pearson_r_p02_5")),
            "bootstrap_r_p97_5": to_float(get_summary_value(rob_summary, "bootstrap_pearson_r_p97_5")),
            "permutation_observed_abs_r": to_float(get_summary_value(rob_summary, "permutation_observed_abs_r")),
            "permutation_null_mean_abs_r": to_float(get_summary_value(rob_summary, "permutation_null_mean_abs_r")),
            "permutation_null_p95_abs_r": to_float(get_summary_value(rob_summary, "permutation_null_p95_abs_r")),
            "permutation_empirical_p": to_float(get_summary_value(rob_summary, "permutation_empirical_p_two_sided")),
        },
        "robustness_detail": {
            "bootstrap_slope": None if boot_slope is None else {
                "mean": to_float(boot_slope["mean"]),
                "p02_5": to_float(boot_slope["p02_5"]),
                "p97_5": to_float(boot_slope["p97_5"]),
            },
            "bootstrap_r2": None if boot_r2 is None else {
                "mean": to_float(boot_r2["mean"]),
                "p02_5": to_float(boot_r2["p02_5"]),
                "p97_5": to_float(boot_r2["p97_5"]),
            },
            "bootstrap_r": None if boot_r is None else {
                "mean": to_float(boot_r["mean"]),
                "p02_5": to_float(boot_r["p02_5"]),
                "p97_5": to_float(boot_r["p97_5"]),
            },
            "permutation": {
                "observed_abs_r": to_float(perm_row.get("observed_abs_pearson_r", np.nan)),
                "null_mean_abs_r": to_float(perm_row.get("null_mean_abs_r", np.nan)),
                "null_p95_abs_r": to_float(perm_row.get("null_p95_abs_r", np.nan)),
                "empirical_p_two_sided": to_float(perm_row.get("empirical_p_two_sided", np.nan)),
            },
            "loo_top_case": None if loo_top.empty else {
                "omitted_date": str(loo_top.get("omitted_date", "")),
                "abs_delta_r2": to_float(loo_top.get("abs_delta_r2_vs_full", np.nan)),
                "abs_delta_r": to_float(loo_top.get("abs_delta_pearson_r_vs_full", np.nan)),
            },
        },
    }
    return keys


# =========================
# Borradores textuales
# =========================
def make_results_markdown(keys: dict) -> str:
    ds = keys["dataset"]
    best = keys["best_same_day_model"]
    rob = keys["robustness"]
    ranking = keys["same_day_predictor_ranking"]
    temporal = keys["best_predictor_temporal_profile"]

    ranking_text = predictor_rank_text(pd.DataFrame(ranking)) if ranking else "NA"

    temporal_lines = []
    for row in temporal:
        temporal_lines.append(
            f"- {row['target_label']}: r = {fmt_num(row['pearson_r'])}, rho = {fmt_num(row['spearman_rho'])}"
        )
    temporal_block = "\n".join(temporal_lines) if temporal_lines else "- NA"

    md = f"""# Borrador de resultados

## Resumen principal

Se analizaron {fmt_int(ds['n_obs'])} observaciones coincidentes entre la serie diaria de estación y Sentinel-2, distribuidas entre {ds['date_start']} y {ds['date_end']}. El mejor desempeño para la ET del mismo día se observó con {best['predictor_label']}, con una relación {best['strength_label']} y positiva frente a la ET de estación (r = {fmt_num(best['pearson_r'])}, rho = {fmt_num(best['spearman_rho'])}, R² = {fmt_num(best['r2'])}, RMSE = {fmt_num(best['rmse'])} mm d⁻¹, MAE = {fmt_num(best['mae'])} mm d⁻¹, n = {fmt_int(best['n'])}). La ecuación del ajuste fue: {best['equation']}.

## Párrafo de resultados

En la comparación entre ET diaria de estación y proxies espectrales Sentinel-2, {best['predictor_label']} presentó el mejor ajuste para el mismo día. La correlación de Pearson alcanzó r = {fmt_num(best['pearson_r'])} y el coeficiente de determinación fue R² = {fmt_num(best['r2'])}, lo que indica que aproximadamente el {fmt_num(best['r2'] * 100, 1)}% de la variabilidad observada en la ET diaria quedó capturada por una relación lineal simple con este índice. El error del ajuste fue moderado (RMSE = {fmt_num(best['rmse'])} mm d⁻¹; MAE = {fmt_num(best['mae'])} mm d⁻¹), y la pendiente positiva ({fmt_num(best['slope'])}) sugiere que valores más altos de {best['predictor_label']} tendieron a asociarse con mayores valores de ET de estación en la muestra analizada.

## Comparación entre predictores en ET del mismo día

El orden de desempeño para ET del mismo día fue: {ranking_text}.

## Perfil temporal del mejor predictor

Tomando {best['predictor_label']} como predictor focal, el patrón por escalas temporales fue el siguiente:
{temporal_block}

## Robustez con muestra pequeña

El análisis de robustez se realizó sobre el modelo {best['target_label']} ~ {best['predictor_label']}. En leave-one-out, la correlación varió entre r = {fmt_num(rob['loo_min_r'])} y r = {fmt_num(rob['loo_max_r'])}, mientras que R² osciló entre {fmt_num(rob['loo_min_r2'])} y {fmt_num(rob['loo_max_r2'])}. La fecha más influyente fue {rob['loo_most_influential_date']}, pero incluso en ese caso el cambio absoluto máximo fue moderado (ΔR² = {fmt_num(rob['loo_max_abs_delta_r2'])}; Δr = {fmt_num(rob['loo_max_abs_delta_r'])}).

El bootstrap mantuvo una pendiente positiva media de {fmt_num(rob['bootstrap_slope_mean'])}, con intervalo percentil 95% entre {fmt_num(rob['bootstrap_slope_p02_5'])} y {fmt_num(rob['bootstrap_slope_p97_5'])}. Para R², la media bootstrap fue {fmt_num(rob['bootstrap_r2_mean'])} y el intervalo percentil 95% se ubicó entre {fmt_num(rob['bootstrap_r2_p02_5'])} y {fmt_num(rob['bootstrap_r2_p97_5'])}. En términos de correlación, el remuestreo produjo un valor medio de r = {fmt_num(rob['bootstrap_r_mean'])}, con intervalo percentil 95% entre {fmt_num(rob['bootstrap_r_p02_5'])} y {fmt_num(rob['bootstrap_r_p97_5'])}.

El test de permutación mostró que la correlación observada (|r| = {fmt_num(rob['permutation_observed_abs_r'])}) excedió el promedio de la distribución nula (|r| = {fmt_num(rob['permutation_null_mean_abs_r'])}) y también su percentil 95 ({fmt_num(rob['permutation_null_p95_abs_r'])}), con un valor p empírico bilateral de {fmt_num(rob['permutation_empirical_p'], 4)}.

## Interpretación prudente

En conjunto, estos resultados indican que la asociación observada entre {best['predictor_label']} y la ET diaria de estación fue consistente dentro de la muestra disponible y no parece depender de una única observación extrema. Sin embargo, la amplitud de los intervalos bootstrap confirma que la magnitud exacta del efecto sigue siendo incierta, por lo que el resultado debe interpretarse como evidencia exploratoria y no como una validación definitiva de estimación remota de ET.
"""
    return md


def make_captions_markdown(keys: dict) -> str:
    best = keys["best_same_day_model"]
    rob = keys["robustness"]
    ranking = keys["same_day_predictor_ranking"]
    rank2 = ranking[1]["predictor_label"] if len(ranking) > 1 else "NDVI"
    rank3 = ranking[2]["predictor_label"] if len(ranking) > 2 else "EVI"
    rank4 = ranking[3]["predictor_label"] if len(ranking) > 3 else "NDRE"

    md = f"""# Borrador de captions de figuras

## Figura 1

**Serie temporal de ET diaria de estación y fechas disponibles de Sentinel-2.** La línea muestra la ET diaria derivada de la estación meteorológica. Los marcadores identifican las fechas satelitales válidas empleadas en el cruce estación–satélite. En el eje secundario se presenta la evolución del predictor focal {best['predictor_label']} en las fechas con observación satelital.

## Figura 2

**Relación entre la ET diaria de estación y {best['predictor_label']} del mismo día.** Cada punto representa una fecha con coincidencia estación–satélite (n = {fmt_int(best['n'])}). La línea corresponde al ajuste lineal simple ({best['equation']}). El modelo presentó r = {fmt_num(best['pearson_r'])}, R² = {fmt_num(best['r2'])} y RMSE = {fmt_num(best['rmse'])} mm d⁻¹.

## Figura 3

**Comparación de predictores espectrales para ET del mismo día.** Se muestran los diagramas de dispersión y ajustes lineales simples entre la ET diaria de estación y los cuatro índices espectrales evaluados ({best['predictor_label']}, {rank2}, {rank3} y {rank4}). El panel permite comparar visualmente la fuerza relativa de las asociaciones y la dispersión residual entre predictores.

## Figura 4

**Desempeño de los mejores modelos por escala temporal de ET.** Para cada target temporal se representa el mejor predictor seleccionado a partir del mayor R² y menor RMSE. Las barras resumen el poder explicativo relativo de cada modelo, mientras que las etiquetas reportan la correlación de Pearson correspondiente.

## Figura 5

**Comportamiento temporal del predictor focal {best['predictor_label']}.** La figura compara la correlación de Pearson entre {best['predictor_label']} y la ET de estación para distintas escalas temporales, incluyendo mismo día, medias móviles y acumulados. El máximo se observó en el modelo de mismo día, lo que sugiere una asociación más estrecha bajo sincronía temporal directa entre la señal espectral y la respuesta de ET.

## Figura adicional sugerida de robustez

**Robustez del modelo {best['target_label']} ~ {best['predictor_label']}.** Un panel complementario podría resumir el leave-one-out y el test de permutación, mostrando que la correlación se mantuvo entre r = {fmt_num(rob['loo_min_r'])} y r = {fmt_num(rob['loo_max_r'])} al excluir observaciones individuales y que la correlación observada superó claramente el percentil 95 de la distribución nula obtenida por permutación (p empírico = {fmt_num(rob['permutation_empirical_p'], 4)}).
"""
    return md


def make_table_notes_markdown(keys: dict) -> str:
    best = keys["best_same_day_model"]

    md = f"""# Borrador de notas de tablas

## Tabla 1. Mejores modelos por target de ET

Los modelos se ordenaron por desempeño dentro de cada target usando R² en orden descendente y RMSE en orden ascendente. La columna `equation` resume el ajuste lineal simple entre la ET de estación y el predictor satelital correspondiente. Las etiquetas "mismo día", "media móvil" y "acumulada" se refieren a la escala temporal del target de ET. En las ventanas de 3, 5 y 7 días, la agregación incluye la fecha satelital de observación.

## Tabla 2. Regresiones suplementarias

Se reportan intercepto, pendiente, correlación de Pearson, correlación de Spearman, R², RMSE, MAE y sesgo para todas las combinaciones evaluadas entre ET de estación y predictores Sentinel-2. {best['predictor_label']} fue el mejor predictor para la ET del mismo día en la muestra actual.

## Tabla 3. Correlaciones suplementarias

Las correlaciones resumen la intensidad y dirección de la asociación entre los índices espectrales y los distintos targets de ET. Dado el tamaño muestral reducido, estas métricas deben interpretarse como evidencia exploratoria y complementarse con los análisis de robustez.

## Tabla 4. Descripción del dataset analítico

La tabla resume el número de observaciones útiles, el rango temporal analizado y estadísticas descriptivas de ET e índices espectrales. Si el archivo generado desde el script 08 presenta `date_start` o `date_end` como valores faltantes, conviene corregir ese script o extraer las fechas directamente desde `station_sentinel_analysis_ready.csv`, ya que el problema proviene de la coerción numérica de la columna `value`.
"""
    return md


def make_methods_bridge_markdown(keys: dict) -> str:
    best = keys["best_same_day_model"]
    rob = keys["robustness"]

    md = f"""# Párrafo puente entre métodos y resultados

Se evaluaron relaciones bivariadas entre la ET de estación y cuatro proxies espectrales Sentinel-2 (NDVI, EVI, SAVI y NDRE) para el mismo día, medias móviles y acumulados temporales. El mejor ajuste para la ET del mismo día se observó con {best['predictor_label']} (r = {fmt_num(best['pearson_r'])}, R² = {fmt_num(best['r2'])}), por lo que este modelo se utilizó como caso focal en los análisis de robustez. Dado el tamaño muestral limitado (n = {fmt_int(best['n'])}), se aplicaron pruebas leave-one-out, bootstrap y permutación. En conjunto, estos análisis mostraron que la relación permaneció positiva y de magnitud comparable tras excluir observaciones individuales, mantuvo pendiente positiva en el remuestreo y excedió claramente lo esperable bajo aleatorización (p empírico = {fmt_num(rob['permutation_empirical_p'], 4)}).
"""
    return md


# =========================
# Main
# =========================
def main() -> None:
    keys = build_key_numbers()

    OUT_JSON.write_text(json.dumps(keys, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_RESULTS_MD.write_text(make_results_markdown(keys), encoding="utf-8")
    OUT_CAPTIONS_MD.write_text(make_captions_markdown(keys), encoding="utf-8")
    OUT_TABLE_NOTES_MD.write_text(make_table_notes_markdown(keys), encoding="utf-8")
    OUT_METHODS_MD.write_text(make_methods_bridge_markdown(keys), encoding="utf-8")

    best = keys["best_same_day_model"]
    ds = keys["dataset"]

    print("\n=== SOPORTE DE REDACCIÓN PARA ARTÍCULO ===")
    print(f"Observaciones analíticas: {ds['n_obs']}")
    print(f"Rango temporal: {ds['date_start']} a {ds['date_end']}")
    print(
        f"Mejor modelo mismo día: {best['target_label']} ~ {best['predictor_label']} "
        f"(r={best['pearson_r']:.3f}, R²={best['r2']:.3f}, RMSE={best['rmse']:.3f})"
    )
    print("\nArchivos generados:")
    print(f"- {OUT_JSON}")
    print(f"- {OUT_RESULTS_MD}")
    print(f"- {OUT_CAPTIONS_MD}")
    print(f"- {OUT_TABLE_NOTES_MD}")
    print(f"- {OUT_METHODS_MD}")


if __name__ == "__main__":
    main()