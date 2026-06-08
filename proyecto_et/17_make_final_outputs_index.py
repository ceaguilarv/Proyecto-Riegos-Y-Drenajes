from __future__ import annotations

from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

TABLES = BASE_DIR / "data" / "article_tables"
FIGURES = BASE_DIR / "data" / "article_figures"
TEXT = BASE_DIR / "data" / "article_text"
PROCESSED = BASE_DIR / "data" / "processed"

OUT_INDEX = TEXT / "final_outputs_index.md"
OUT_TABLE = TABLES / "table_07_final_outputs_index.csv"

TABLES.mkdir(parents=True, exist_ok=True)
TEXT.mkdir(parents=True, exist_ok=True)


def file_status(path: Path) -> dict:
    return {
        "exists": path.exists(),
        "size_kb": round(path.stat().st_size / 1024, 2) if path.exists() else None,
        "path": str(path.relative_to(BASE_DIR)) if path.exists() else str(path.relative_to(BASE_DIR)),
    }


def add(rows, category, name, path, role, include_in_report, notes):
    status = file_status(path)
    rows.append({
        "category": category,
        "name": name,
        "path": status["path"],
        "exists": status["exists"],
        "size_kb": status["size_kb"],
        "role": role,
        "include_in_report": include_in_report,
        "notes": notes,
    })


def main():
    rows = []

    # =====================
    # Tablas principales
    # =====================
    add(
        rows,
        "table",
        "Tabla 1. Mejores modelos Sentinel",
        TABLES / "table_01_best_models_article.csv",
        "Tabla principal de resultados Sentinel-2.",
        "yes",
        "Incluye el modelo principal ET diaria ~ SAVI_mean y los mejores modelos por target temporal.",
    )

    add(
        rows,
        "table",
        "Tabla 2. Regresiones suplementarias Sentinel",
        TABLES / "table_02_all_regressions_supplement.csv",
        "Tabla suplementaria con todas las regresiones simples.",
        "optional/supplement",
        "Útil como anexo o material suplementario; no conviene saturar el cuerpo principal.",
    )

    add(
        rows,
        "table",
        "Tabla 3. Correlaciones suplementarias Sentinel",
        TABLES / "table_03_all_correlations_supplement.csv",
        "Tabla suplementaria con correlaciones Pearson y Spearman.",
        "optional/supplement",
        "Sirve para mostrar ranking completo de predictores y targets.",
    )

    add(
        rows,
        "table",
        "Tabla 4. Descripción del dataset Sentinel",
        TABLES / "table_04_dataset_description.csv",
        "Resumen descriptivo del dataset analysis-ready Sentinel.",
        "yes",
        "Ya corregida: date_start y date_end deben aparecer como 2025-08-20 y 2025-12-28.",
    )

    add(
        rows,
        "table",
        "Tabla 5. Diagnóstico Landsat/LST",
        TABLES / "table_05_landsat_lst_diagnostic.csv",
        "Tabla diagnóstica de disponibilidad y calidad Landsat/LST.",
        "yes",
        "Debe entrar como diagnóstico, no como base de regresión.",
    )

    add(
        rows,
        "table",
        "Tabla 6. Auditoría final del proyecto",
        TABLES / "table_06_final_project_audit.csv",
        "Tabla maestra de control interno del proyecto.",
        "optional",
        "No necesariamente entra completa al informe; sirve para control y trazabilidad.",
    )

    # =====================
    # Figuras Sentinel
    # =====================
    add(
        rows,
        "figure",
        "Figura 1. Serie temporal estación-Sentinel",
        FIGURES / "fig01_station_satellite_timeline.png",
        "Figura principal de contexto temporal.",
        "yes",
        "Muestra ET diaria y fechas Sentinel válidas.",
    )

    add(
        rows,
        "figure",
        "Figura 2. Mejor modelo ET ~ SAVI",
        FIGURES / "fig02_scatter_best_same_day_model.png",
        "Figura principal del resultado Sentinel.",
        "yes",
        "Debe acompañar la Tabla 1.",
    )

    add(
        rows,
        "figure",
        "Figura 3. Comparación predictores Sentinel",
        FIGURES / "fig03_scatter_same_day_predictor_grid.png",
        "Comparación visual entre SAVI, NDVI, EVI y NDRE.",
        "yes",
        "Muy útil para justificar que SAVI fue el mejor predictor de ET diaria.",
    )

    add(
        rows,
        "figure",
        "Figura 4. Ranking modelos por target",
        FIGURES / "fig04_best_model_ranking.png",
        "Ranking de desempeño por escala temporal.",
        "optional",
        "Puede entrar si hay espacio; si no, dejar como suplementaria.",
    )

    add(
        rows,
        "figure",
        "Figura 5. Perfil temporal del predictor focal",
        FIGURES / "fig05_temporal_windows_best_predictor.png",
        "Comparación por ventanas temporales.",
        "optional",
        "Útil para explicar por qué el mismo día fue más fuerte.",
    )

    # =====================
    # Figuras Landsat
    # =====================
    add(
        rows,
        "figure",
        "Figura 6. Píxeles válidos Landsat/LST",
        FIGURES / "fig06_landsat_valid_pixel_pct.png",
        "Diagnóstico de disponibilidad térmica.",
        "yes",
        "Figura clave para justificar por qué no se hacen regresiones Landsat.",
    )

    add(
        rows,
        "figure",
        "Figura 7. LST vs temperatura del aire",
        FIGURES / "fig07_landsat_lst_vs_tair.png",
        "Comparación descriptiva térmica.",
        "yes",
        "Sirve para mostrar coherencia física sin inferencia estadística.",
    )

    # =====================
    # Textos automáticos
    # =====================
    add(
        rows,
        "text",
        "Borrador de resultados Sentinel",
        TEXT / "results_sentences_draft.md",
        "Texto base para sección de resultados Sentinel.",
        "yes",
        "Debe actualizarse con los resultados corregidos n=8.",
    )

    add(
        rows,
        "text",
        "Captions de figuras",
        TEXT / "figure_captions_draft.md",
        "Borrador de leyendas de figuras.",
        "yes",
        "Debe revisar que las cifras correspondan al reprocesamiento corregido.",
    )

    add(
        rows,
        "text",
        "Notas de tablas",
        TEXT / "table_notes_draft.md",
        "Notas metodológicas para tablas.",
        "yes",
        "Útil para el informe final.",
    )

    add(
        rows,
        "text",
        "Resultados diagnósticos Landsat",
        TEXT / "landsat_diagnostic_results.md",
        "Texto base para sección Landsat/LST.",
        "yes",
        "Debe entrar con lenguaje prudente.",
    )

    add(
        rows,
        "text",
        "Auditoría final automática",
        TEXT / "final_project_audit_report.md",
        "Resumen ejecutivo interno del estado del proyecto.",
        "optional",
        "Puede alimentar la discusión metodológica.",
    )

    # =====================
    # Archivos procesados clave
    # =====================
    add(
        rows,
        "processed",
        "Estación diaria exterior corregida",
        PROCESSED / "station_daily_exterior_ready.csv",
        "Base meteorológica final.",
        "no/direct_input",
        "Fuente de todos los cruces estación-satélite.",
    )

    add(
        rows,
        "processed",
        "Analysis-ready Sentinel",
        PROCESSED / "station_sentinel_analysis_ready.csv",
        "Base final de regresiones Sentinel.",
        "no/direct_input",
        "n=8 después de corrección de fechas.",
    )

    add(
        rows,
        "processed",
        "Analysis-ready Landsat",
        PROCESSED / "station_landsat_analysis_ready.csv",
        "Base diagnóstica Landsat.",
        "no/direct_input",
        "n=4, no usar para regresión robusta.",
    )

    add(
        rows,
        "processed",
        "Robustez Sentinel",
        PROCESSED / "robustness_summary.csv",
        "Resumen de leave-one-out, bootstrap y permutación.",
        "yes",
        "Debe incluirse en resultados o discusión.",
    )

    df = pd.DataFrame(rows)
    df.to_csv(OUT_TABLE, index=False)

    missing = df.loc[~df["exists"]].copy()
    included = df.loc[df["include_in_report"].isin(["yes", "optional/supplement", "optional"])].copy()

    md = "# Índice final de salidas del proyecto\n\n"

    md += "## Resumen\n\n"
    md += f"- Archivos registrados: {len(df)}\n"
    md += f"- Archivos existentes: {int(df['exists'].sum())}\n"
    md += f"- Archivos faltantes: {len(missing)}\n\n"

    md += "## Decisión de inclusión\n\n"
    md += "La rama Sentinel-2 se mantiene como resultado principal exploratorio. La rama Landsat/LST se mantiene como diagnóstico complementario por limitación de observaciones válidas.\n\n"

    md += "## Archivos recomendados para el informe\n\n"
    for _, r in included.iterrows():
        if not r["exists"]:
            status = "FALTA"
        else:
            status = "OK"

        md += f"### {r['name']}\n\n"
        md += f"- Estado: {status}\n"
        md += f"- Ruta: `{r['path']}`\n"
        md += f"- Rol: {r['role']}\n"
        md += f"- Inclusión: {r['include_in_report']}\n"
        md += f"- Nota: {r['notes']}\n\n"

    if not missing.empty:
        md += "## Archivos faltantes\n\n"
        for _, r in missing.iterrows():
            md += f"- `{r['path']}` ({r['name']})\n"

    OUT_INDEX.write_text(md, encoding="utf-8")

    print("\n=== ÍNDICE FINAL GENERADO ===")
    print(df.to_string(index=False))
    print(f"\nTabla: {OUT_TABLE}")
    print(f"Índice markdown: {OUT_INDEX}")


if __name__ == "__main__":
    main()