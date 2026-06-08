from __future__ import annotations

from pathlib import Path
import re
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from rasterio.features import rasterize
from shapely.ops import unary_union


# ============================================================
# 21_mask_kc_rasters_with_aoi.py
#
# Recorta los GeoTIFF de Kc/ETc usando un AOI de pasturas y,
# opcionalmente, excluye construcciones o superficies duras.
#
# Entrada:
# - data/rasters/kc_etc/raw_from_drive/kc_etc_sentinel_YYYYMMDD.tif
# - data/vectors/aoi_kc_pasturas.gpkg
# - data/vectors/exclusion_buildings.gpkg   opcional
#
# Salida:
# - data/rasters/kc_etc/masked/*.tif
# - data/rasters/kc_etc/stats/kc_etc_masked_stats_by_date.csv
# - data/article_tables/table_10_kc_etc_masked_stats_by_date.csv
#
# Bandas esperadas según el script 18:
# 1 NDVI
# 2 SAVI
# 3 SAVI_norm
# 4 NDVI_norm
# 5 Kc_SAVI_dynamic
# 6 ETc_SAVI_mm_d
# 7 Kc_NDVI_dynamic
# 8 ETc_NDVI_mm_d
# ============================================================


BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "data" / "rasters" / "kc_etc" / "raw_from_drive"
MASKED_DIR = BASE_DIR / "data" / "rasters" / "kc_etc" / "masked"
STATS_DIR = BASE_DIR / "data" / "rasters" / "kc_etc" / "stats"
ARTICLE_TABLES = BASE_DIR / "data" / "article_tables"
ARTICLE_TEXT = BASE_DIR / "data" / "article_text"

MASKED_DIR.mkdir(parents=True, exist_ok=True)
STATS_DIR.mkdir(parents=True, exist_ok=True)
ARTICLE_TABLES.mkdir(parents=True, exist_ok=True)
ARTICLE_TEXT.mkdir(parents=True, exist_ok=True)

AOI_PATH = BASE_DIR / "data" / "vectors" / "aoi_kc_pasturas.gpkg"
EXCLUSION_PATH = BASE_DIR / "data" / "vectors" / "exclusion_buildings.gpkg"

OUT_STATS = STATS_DIR / "kc_etc_masked_stats_by_date.csv"
OUT_STATS_ARTICLE = ARTICLE_TABLES / "table_10_kc_etc_masked_stats_by_date.csv"
OUT_TEXT = ARTICLE_TEXT / "kc_etc_masked_results.md"

BAND_NAMES = {
    1: "NDVI",
    2: "SAVI",
    3: "SAVI_norm",
    4: "NDVI_norm",
    5: "Kc_SAVI_dynamic",
    6: "ETc_SAVI_mm_d",
    7: "Kc_NDVI_dynamic",
    8: "ETc_NDVI_mm_d",
}


def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo requerido: {path}")


def extract_date_from_filename(path: Path) -> str:
    match = re.search(r"(\d{8})", path.name)
    if not match:
        return ""
    raw = match.group(1)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def load_clean_geometry(target_crs) -> gpd.GeoDataFrame:
    ensure_file(AOI_PATH)

    aoi = gpd.read_file(AOI_PATH)
    if aoi.empty:
        raise ValueError(f"El AOI está vacío: {AOI_PATH}")

    if aoi.crs is None:
        raise ValueError("El AOI no tiene CRS definido. Asígnale EPSG:4326 en QGIS si lo dibujaste sobre Google Satellite.")

    aoi = aoi.to_crs(target_crs)
    aoi_geom = unary_union(aoi.geometry)

    if EXCLUSION_PATH.exists():
        exclusions = gpd.read_file(EXCLUSION_PATH)

        if not exclusions.empty:
            if exclusions.crs is None:
                raise ValueError("La capa de exclusiones no tiene CRS definido.")

            exclusions = exclusions.to_crs(target_crs)
            exclusion_geom = unary_union(exclusions.geometry)

            clean_geom = aoi_geom.difference(exclusion_geom)
            print(f"AOI limpio = AOI - exclusiones ({len(exclusions)} polígonos excluidos).")
        else:
            clean_geom = aoi_geom
            print("La capa de exclusiones existe, pero está vacía. Se usará solo el AOI.")
    else:
        clean_geom = aoi_geom
        print("No existe exclusion_buildings.gpkg. Se usará solo el AOI.")

    if clean_geom.is_empty:
        raise ValueError("La geometría limpia quedó vacía. Revisa AOI y exclusiones.")

    clean = gpd.GeoDataFrame({"name": ["aoi_clean_pastures"]}, geometry=[clean_geom], crs=target_crs)
    return clean


def compute_band_stats(array: np.ndarray, band_name: str, nodata=None) -> dict:
    data = array.astype("float64")

    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)

    data = np.where(np.isfinite(data), data, np.nan)

    valid = data[~np.isnan(data)]

    if valid.size == 0:
        return {
            f"{band_name}_count": 0,
            f"{band_name}_mean": np.nan,
            f"{band_name}_median": np.nan,
            f"{band_name}_min": np.nan,
            f"{band_name}_max": np.nan,
            f"{band_name}_std": np.nan,
        }

    return {
        f"{band_name}_count": int(valid.size),
        f"{band_name}_mean": float(np.nanmean(valid)),
        f"{band_name}_median": float(np.nanmedian(valid)),
        f"{band_name}_min": float(np.nanmin(valid)),
        f"{band_name}_max": float(np.nanmax(valid)),
        f"{band_name}_std": float(np.nanstd(valid, ddof=0)),
    }


def mask_raster_with_clean_aoi(raster_path: Path) -> dict:
    date_txt = extract_date_from_filename(raster_path)

    with rasterio.open(raster_path) as src:
        clean_gdf = load_clean_geometry(src.crs)
        clean_geom = [clean_gdf.geometry.iloc[0].__geo_interface__]

        out_image, out_transform = mask(
            src,
            clean_geom,
            crop=True,
            filled=True,
            nodata=src.nodata if src.nodata is not None else np.nan,
        )

        out_meta = src.meta.copy()
        out_meta.update(
            {
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "count": out_image.shape[0],
                "compress": "lzw",
            }
        )

        out_path = MASKED_DIR / raster_path.name.replace(".tif", "_masked.tif")

        with rasterio.open(out_path, "w", **out_meta) as dst:
            dst.write(out_image)

            for band_idx, band_name in BAND_NAMES.items():
                if band_idx <= out_image.shape[0]:
                    dst.set_band_description(band_idx, band_name)

        row = {
            "date": date_txt,
            "input_raster": str(raster_path.relative_to(BASE_DIR)),
            "output_raster": str(out_path.relative_to(BASE_DIR)),
            "n_bands": int(out_image.shape[0]),
            "crs": str(src.crs),
        }

        for band_idx, band_name in BAND_NAMES.items():
            if band_idx <= out_image.shape[0]:
                stats = compute_band_stats(out_image[band_idx - 1], band_name, nodata=src.nodata)
                row.update(stats)
            else:
                row[f"{band_name}_count"] = 0
                row[f"{band_name}_mean"] = np.nan
                row[f"{band_name}_median"] = np.nan
                row[f"{band_name}_min"] = np.nan
                row[f"{band_name}_max"] = np.nan
                row[f"{band_name}_std"] = np.nan

        return row


def build_article_text(stats: pd.DataFrame) -> str:
    if stats.empty:
        return "# Resultados Kc/ETc en AOI limpio\n\nNo se generaron estadísticas.\n"

    kc_mean = stats["Kc_SAVI_dynamic_mean"].mean()
    kc_min = stats["Kc_SAVI_dynamic_mean"].min()
    kc_max = stats["Kc_SAVI_dynamic_mean"].max()

    etc_mean = stats["ETc_SAVI_mm_d_mean"].mean()
    etc_min = stats["ETc_SAVI_mm_d_mean"].min()
    etc_max = stats["ETc_SAVI_mm_d_mean"].max()

    ndvi_kc_mean = stats["Kc_NDVI_dynamic_mean"].mean()
    ndvi_etc_mean = stats["ETc_NDVI_mm_d_mean"].mean()

    date_start = stats["date"].min()
    date_end = stats["date"].max()

    text = f"""# Resultados Kc/ETc en AOI limpio

Se aplicó una máscara espacial sobre los rasters de Kc dinámico y ETc para restringir el análisis al área de pasturas definida por el AOI y excluir construcciones o superficies duras digitalizadas. Este refinamiento busca reducir la interferencia espectral de techos, vías y edificaciones dentro del buffer original.

Después del enmascaramiento, se procesaron {len(stats)} fechas entre {date_start} y {date_end}. El Kc dinámico basado en SAVI presentó un valor medio de {kc_mean:.3f}, con un rango temporal entre {kc_min:.3f} y {kc_max:.3f}. La ETc media basada en SAVI fue de {etc_mean:.3f} mm/día, con valores entre {etc_min:.3f} y {etc_max:.3f} mm/día.

Como comparación, el Kc dinámico basado en NDVI tuvo un valor medio de {ndvi_kc_mean:.3f}, mientras que la ETc media basada en NDVI fue de {ndvi_etc_mean:.3f} mm/día.

Estos resultados deben interpretarse como una espacialización exploratoria de la ET de estación modulada por vigor/cobertura vegetal. El uso de un AOI limpio mejora la representatividad de la señal para pasturas, pero no convierte el producto en una medición directa de ET real.
"""

    return text


def main() -> None:
    rasters = sorted(RAW_DIR.glob("kc_etc_sentinel_*.tif"))

    if not rasters:
        raise FileNotFoundError(
            f"No se encontraron rasters en {RAW_DIR}. "
            "Copia allí los GeoTIFF exportados desde Google Drive."
        )

    print("\n=== ENMASCARAMIENTO Kc/ETc CON AOI LIMPIO ===")
    print(f"Rasters encontrados: {len(rasters)}")
    print(f"AOI: {AOI_PATH}")
    print(f"Exclusiones: {EXCLUSION_PATH if EXCLUSION_PATH.exists() else 'No existe'}")

    rows = []

    for raster_path in rasters:
        print(f"\nProcesando: {raster_path.name}")
        try:
            row = mask_raster_with_clean_aoi(raster_path)
            rows.append(row)
            print(f"OK → {row['output_raster']}")
            print(
                f"Kc_SAVI_mean={row.get('Kc_SAVI_dynamic_mean', np.nan):.3f} | "
                f"ETc_SAVI_mean={row.get('ETc_SAVI_mm_d_mean', np.nan):.3f}"
            )
        except Exception as e:
            warnings.warn(f"No se pudo procesar {raster_path.name}: {e}")

    if not rows:
        raise RuntimeError("No se pudo procesar ningún raster.")

    stats = pd.DataFrame(rows)
    stats = stats.sort_values("date").reset_index(drop=True)

    stats.to_csv(OUT_STATS, index=False)
    stats.to_csv(OUT_STATS_ARTICLE, index=False)

    text = build_article_text(stats)
    OUT_TEXT.write_text(text, encoding="utf-8")

    print("\n=== SALIDAS ===")
    print(f"Rasters enmascarados: {MASKED_DIR}")
    print(f"Estadísticas: {OUT_STATS}")
    print(f"Tabla artículo: {OUT_STATS_ARTICLE}")
    print(f"Texto: {OUT_TEXT}")

    print("\nResumen:")
    keep = [
        "date",
        "Kc_SAVI_dynamic_mean",
        "ETc_SAVI_mm_d_mean",
        "Kc_NDVI_dynamic_mean",
        "ETc_NDVI_mm_d_mean",
    ]
    keep = [c for c in keep if c in stats.columns]
    print(stats[keep].round(3).to_string(index=False))


if __name__ == "__main__":
    main()