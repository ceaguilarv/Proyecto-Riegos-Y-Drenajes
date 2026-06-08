from __future__ import annotations

from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

TABLES = BASE_DIR / "data" / "article_tables"
FIGURES = BASE_DIR / "data" / "article_figures"
TEXT = BASE_DIR / "data" / "article_text"
PROCESSED = BASE_DIR / "data" / "processed"

INPUT_INDEX_TABLE = TABLES / "table_07_final_outputs_index.csv"
OUT_INDEX_TABLE = TABLES / "table_07_final_outputs_index.csv"
OUT_INDEX_MD = TEXT / "final_outputs_index.md"

TABLES.mkdir(parents=True, exist_ok=True)
TEXT.mkdir(parents=True, exist_ok=True)


def file_status(path: Path) -> dict:
    exists = path.exists()
    return {
        "exists": exists,
        "size_kb": round(path.stat().st_size / 1024, 2) if exists else None,
        "path": str(path.relative_to(BASE_DIR)),
    }


def make_row(category, name, path, role, include_in_report, notes):
    status = file_status(path)
    return {
        "category": category,
        "name": name,
        "path": status["path"],
        "exists": status["exists"],
        "size_kb": status["size_kb"],
        "role": role,
        "include_in_report": include_in_report,
        "notes": notes,
    }


def main() -> None:
    if INPUT_INDEX_TABLE.exists():
        df = pd.read_csv(INPUT_INDEX_TABLE)
    else:
        df = pd.DataFrame(
            columns=[
                "category",
                "name",
                "path",
                "exists",
                "size_kb",
                "role",
                "include_in_report",
                "notes",
            ]
        )

    # Eliminar entradas previas de Kc si el script se corre varias veces
    kc_names = {
        "Tabla 8. Resumen Kc dinámico y ETc",
        "Tabla 9. Kc dinámico y ETc por fecha",
        "Figura 8. Serie temporal ET base y ETc dinámica",
        "Figura 9. Serie temporal Kc dinámico",
        "Figura 10. ET base vs ETc dinámica",
        "Resultados Kc dinámico y ETc espacial",
        "Parámetros Kc dinámico",
        "Estadísticas espaciales Kc/ETc",
    }

    if not df.empty and "name" in df.columns:
        df = df.loc[~df["name"].isin(kc_names)].copy()

    new_rows = []

    new_rows.append(
        make_row(
            "table",
            "Tabla 8. Resumen Kc dinámico y ETc",
            TABLES / "table_08_dynamic_kc_etc_summary.csv",
            "Tabla principal de la rama Kc dinámico.",
            "yes",
            "Resume Kc_min, Kc_max, Kc SAVI medio, ETc SAVI media y métricas de interpretación.",
        )
    )

    new_rows.append(
        make_row(
            "table",
            "Tabla 9. Kc dinámico y ETc por fecha",
            TABLES / "table_09_dynamic_kc_etc_by_date.csv",
            "Tabla detallada por fecha para Kc y ETc.",
            "yes",
            "Permite reportar la evolución temporal de ET base, Kc SAVI, ETc SAVI, Kc NDVI y ETc NDVI.",
        )
    )

    new_rows.append(
        make_row(
            "figure",
            "Figura 8. Serie temporal ET base y ETc dinámica",
            FIGURES / "fig08_dynamic_etc_timeseries.png",
            "Figura principal de la rama ETc espacial.",
            "yes",
            "Compara ET base de estación con ETc dinámica basada en SAVI y NDVI.",
        )
    )

    new_rows.append(
        make_row(
            "figure",
            "Figura 9. Serie temporal Kc dinámico",
            FIGURES / "fig09_dynamic_kc_timeseries.png",
            "Figura principal del Kc dinámico.",
            "yes",
            "Muestra la evolución temporal del Kc dinámico basado en SAVI y NDVI.",
        )
    )

    new_rows.append(
        make_row(
            "figure",
            "Figura 10. ET base vs ETc dinámica",
            FIGURES / "fig10_et_base_vs_etc_dynamic.png",
            "Figura descriptiva de relación ET base–ETc.",
            "optional",
            "Debe interpretarse con cautela porque ETc se construye como ET base multiplicada por Kc.",
        )
    )

    new_rows.append(
        make_row(
            "text",
            "Resultados Kc dinámico y ETc espacial",
            TEXT / "dynamic_kc_etc_results.md",
            "Texto base para la sección de Kc dinámico.",
            "yes",
            "Debe incluirse porque responde al objetivo más importante del proyecto.",
        )
    )

    new_rows.append(
        make_row(
            "processed",
            "Parámetros Kc dinámico",
            PROCESSED / "dynamic_kc_parameters.json",
            "Archivo de trazabilidad metodológica del Kc.",
            "no/direct_input",
            "Contiene Kc_min, Kc_max, rangos observados de SAVI/NDVI y supuestos metodológicos.",
        )
    )

    new_rows.append(
        make_row(
            "processed",
            "Estadísticas espaciales Kc/ETc",
            PROCESSED / "dynamic_kc_etc_map_stats.csv",
            "Base procesada de estadísticas espaciales Kc/ETc.",
            "no/direct_input",
            "Fuente de las tablas 8 y 9; contiene medias, medianas, mínimos, máximos y desviaciones espaciales.",
        )
    )

    df_new = pd.DataFrame(new_rows)
    df = pd.concat([df, df_new], ignore_index=True)

    # Orden sugerido para que el índice quede lógico
    category_order = {
        "table": 1,
        "figure": 2,
        "text": 3,
        "processed": 4,
    }

    df["_category_order"] = df["category"].map(category_order).fillna(99)
    df = df.sort_values(["_category_order", "name"]).drop(columns=["_category_order"]).reset_index(drop=True)

    df.to_csv(OUT_INDEX_TABLE, index=False)

    missing = df.loc[~df["exists"]].copy()
    included = df.loc[df["include_in_report"].isin(["yes", "optional/supplement", "optional"])].copy()

    md = "# Índice final actualizado de salidas del proyecto\n\n"

    md += "## Resumen\n\n"
    md += f"- Archivos registrados: {len(df)}\n"
    md += f"- Archivos existentes: {int(df['exists'].sum())}\n"
    md += f"- Archivos faltantes: {len(missing)}\n\n"

    md += "## Decisión metodológica final\n\n"
    md += (
        "El proyecto queda estructurado en tres ramas: "
        "**Sentinel-2 como análisis principal de asociación ET–proxy espectral**, "
        "**Kc dinámico/ETc espacial como producto metodológico central**, "
        "y **Landsat/LST como diagnóstico térmico complementario**. "
        "La rama Kc dinámico responde al objetivo de pasar de una señal puntual de estación "
        "a una representación espacial modulada por vigor/cobertura vegetal. "
        "Debe interpretarse como Kc exploratorio relativo, no como Kc calibrado universal.\n\n"
    )

    md += "## Archivos recomendados para el informe\n\n"

    for _, r in included.iterrows():
        status = "OK" if r["exists"] else "FALTA"

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

    OUT_INDEX_MD.write_text(md, encoding="utf-8")

    print("\n=== ÍNDICE FINAL ACTUALIZADO CON Kc/ETc ===")
    print(df.to_string(index=False))
    print(f"\nTabla actualizada: {OUT_INDEX_TABLE}")
    print(f"Índice markdown actualizado: {OUT_INDEX_MD}")

    if not missing.empty:
        print("\nADVERTENCIA: hay archivos faltantes:")
        print(missing[["name", "path"]].to_string(index=False))
    else:
        print("\nTodos los archivos registrados existen.")


if __name__ == "__main__":
    main()