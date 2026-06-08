from __future__ import annotations

from pathlib import Path
import json
import warnings

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point


# ============================================================
# 18_build_dynamic_kc_maps.py
#
# Construye mapas exploratorios de Kc dinámico y ETc espacial
# usando Sentinel-2 y la ET diaria exterior de estación.
#
# NOTA CIENTÍFICA:
# - Esto NO calcula ET satelital física.
# - Kc_dynamic se construye como un coeficiente relativo/escalado
#   a partir de índices espectrales.
# - ETc_dynamic = ET_base_estación × Kc_dynamic.
# - Debe interpretarse como producto exploratorio y metodológico.
# ============================================================


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_ANALYSIS = BASE_DIR / "data" / "processed" / "station_sentinel_analysis_ready.csv"

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_VECTOR_DIR = BASE_DIR / "data" / "vectors"
OUTPUT_VECTOR_DIR.mkdir(parents=True, exist_ok=True)

OUT_POINT_GEOJSON = OUTPUT_VECTOR_DIR / "station_point.geojson"
OUT_BUFFER_GEOJSON = OUTPUT_VECTOR_DIR / "station_buffer_300m.geojson"

OUT_KC_STATS = OUTPUT_DIR / "dynamic_kc_etc_map_stats.csv"
OUT_KC_PARAMS = OUTPUT_DIR / "dynamic_kc_parameters.json"
OUT_EXPORT_TASKS = OUTPUT_DIR / "dynamic_kc_export_tasks.csv"

# Coordenadas estación
STATION_LAT = 4.636146
STATION_LON = -74.088631

# Geometría
BUFFER_METERS = 300
WORKING_CRS_METRIC = "EPSG:9377"
REDUCE_SCALE_METERS = 10

# Parámetros Kc exploratorios para pastura/cobertura herbácea
# Ajustables y deben declararse como supuestos metodológicos.
KC_MIN = 0.70
KC_MAX = 1.05

# Exportación de mapas a Google Drive
EXPORT_TO_DRIVE = True
DRIVE_FOLDER = "proyecto_et_kc_maps"
EXPORT_SCALE_METERS = 10
EXPORT_CRS = "EPSG:4326"

# Índices principales
MAIN_VI = "SAVI"
COMPARISON_VI = "NDVI"


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def init_ee() -> None:
    ee.Authenticate(auth_mode="localhost")
    ee.Initialize(project="bamboo-storm-477002-v4")
    print("GEE ok")


def build_station_point_gdf(lat: float, lon: float) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["station_point"]},
        geometry=[Point(lon, lat)],
        crs="EPSG:4326",
    )


def build_buffer_gdf(point_gdf: gpd.GeoDataFrame, buffer_meters: float) -> gpd.GeoDataFrame:
    metric = point_gdf.to_crs(WORKING_CRS_METRIC).copy()
    metric["geometry"] = metric.geometry.buffer(buffer_meters)
    buffered = metric.to_crs("EPSG:4326")
    buffered["name"] = f"station_buffer_{int(buffer_meters)}m"
    return buffered


def save_vectors(point_gdf: gpd.GeoDataFrame, buffer_gdf: gpd.GeoDataFrame) -> None:
    point_gdf.to_file(OUT_POINT_GEOJSON, driver="GeoJSON")
    buffer_gdf.to_file(OUT_BUFFER_GEOJSON, driver="GeoJSON")


def to_featurecollection_from_gdf(gdf: gpd.GeoDataFrame) -> ee.FeatureCollection:
    geojson = json.loads(gdf.to_json())
    features = []
    for feat in geojson["features"]:
        geom = ee.Geometry(feat["geometry"])
        props = feat.get("properties", {})
        features.append(ee.Feature(geom, props))
    return ee.FeatureCollection(features)


# =========================
# Lectura de datos
# =========================
def load_analysis_table(path: Path) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)

    if "date" not in df.columns:
        raise ValueError("station_sentinel_analysis_ready.csv no tiene columna 'date'.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    required = ["date", "et_base_out_mm_d"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")

    for col in [
        "et_base_out_mm_d",
        "NDVI_mean",
        "SAVI_mean",
        "EVI_mean",
        "NDRE_mean",
        "valid_pixel_pct",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["et_base_out_mm_d"]).copy()
    df = df.sort_values("date").reset_index(drop=True)

    return df


def get_observed_vi_ranges(df: pd.DataFrame) -> dict:
    """
    Define rangos de normalización a partir de las observaciones
    analysis-ready del ROI.

    Esto genera un Kc relativo al rango observado del estudio.
    No es un Kc calibrado universal.
    """
    ranges = {}

    for vi_col, vi_name in [
        ("SAVI_mean", "SAVI"),
        ("NDVI_mean", "NDVI"),
        ("EVI_mean", "EVI"),
        ("NDRE_mean", "NDRE"),
    ]:
        if vi_col in df.columns and df[vi_col].notna().any():
            vi_min = float(df[vi_col].min())
            vi_max = float(df[vi_col].max())

            if np.isclose(vi_min, vi_max):
                warnings.warn(f"Rango nulo para {vi_name}. Se ampliará artificialmente.")
                vi_min = vi_min - 0.01
                vi_max = vi_max + 0.01

            ranges[vi_name] = {
                "min": vi_min,
                "max": vi_max,
                "source_column": vi_col,
                "source": "station_sentinel_analysis_ready_observed_range",
            }

    if "SAVI" not in ranges or "NDVI" not in ranges:
        raise ValueError("No se pudieron definir rangos para SAVI y NDVI.")

    return ranges


# =========================
# Sentinel-2
# =========================
def mask_s2_sr(image: ee.Image) -> ee.Image:
    scl = image.select("SCL")
    qa60 = image.select("QA60")

    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11

    qa_mask = (
        qa60.bitwiseAnd(cloud_bit_mask).eq(0)
        .And(qa60.bitwiseAnd(cirrus_bit_mask).eq(0))
    )

    scl_mask = (
        scl.neq(3)    # cloud shadow
        .And(scl.neq(8))    # cloud medium probability
        .And(scl.neq(9))    # cloud high probability
        .And(scl.neq(10))   # cirrus
        .And(scl.neq(11))   # snow/ice
    )

    return image.updateMask(qa_mask).updateMask(scl_mask)


def add_spectral_indices(image: ee.Image) -> ee.Image:
    scaled = image.select(["B2", "B4", "B5", "B8"]).multiply(0.0001)

    blue = scaled.select("B2")
    red = scaled.select("B4")
    rededge = scaled.select("B5")
    nir = scaled.select("B8")

    ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")

    evi = (
        nir.subtract(red)
        .multiply(2.5)
        .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
        .rename("EVI")
    )

    L = 0.5
    savi = (
        nir.subtract(red)
        .multiply(1 + L)
        .divide(nir.add(red).add(L))
        .rename("SAVI")
    )

    ndre = nir.subtract(rededge).divide(nir.add(rededge)).rename("NDRE")

    return image.addBands([ndvi, evi, savi, ndre])


def get_sentinel_image_for_row(row: pd.Series) -> ee.Image:
    """
    Carga la imagen Sentinel-2 seleccionada.

    En station_sentinel_analysis_ready.csv, image_id puede venir como:
    - ID completo: COPERNICUS/S2_SR_HARMONIZED/...
    - system:index corto: 20250820T152711_20250820T152849_T18NXL

    Si viene corto, se agrega el prefijo de la colección.
    Si falla, se busca por fecha como respaldo.
    """
    date = pd.to_datetime(row["date"]).strftime("%Y-%m-%d")
    next_date = (pd.to_datetime(row["date"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    image_id = str(row.get("image_id", "")).strip()

    if image_id and image_id.lower() not in ["nan", "none", ""]:
        if image_id.startswith("COPERNICUS/"):
            full_id = image_id
        else:
            full_id = f"COPERNICUS/S2_SR_HARMONIZED/{image_id}"

        try:
            return ee.Image(full_id)
        except Exception:
            warnings.warn(f"No se pudo cargar full_id={full_id}. Se buscará por fecha.")

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(date, next_date)
        .filterBounds(ee.Geometry.Point([STATION_LON, STATION_LAT]))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    return ee.Image(collection.first())


# =========================
# Kc dinámico
# =========================
def normalize_vi(image: ee.Image, vi_band: str, vi_min: float, vi_max: float) -> ee.Image:
    vi = image.select(vi_band)
    norm = vi.subtract(vi_min).divide(vi_max - vi_min).clamp(0, 1)
    return norm.rename(f"{vi_band}_norm")


def add_dynamic_kc_and_etc(
    image: ee.Image,
    et_base_mm_d: float,
    ranges: dict,
) -> ee.Image:
    """
    Agrega:
    - Kc_SAVI_dynamic
    - ETc_SAVI_mm_d
    - Kc_NDVI_dynamic
    - ETc_NDVI_mm_d
    """
    out = image

    for vi_name in ["SAVI", "NDVI"]:
        vi_min = ranges[vi_name]["min"]
        vi_max = ranges[vi_name]["max"]

        vi_norm = normalize_vi(out, vi_name, vi_min, vi_max)
        kc = (
            vi_norm.multiply(KC_MAX - KC_MIN)
            .add(KC_MIN)
            .rename(f"Kc_{vi_name}_dynamic")
        )

        etc = (
            kc.multiply(float(et_base_mm_d))
            .rename(f"ETc_{vi_name}_mm_d")
        )

        out = out.addBands([vi_norm, kc, etc])

    return out.set({
        "et_base_out_mm_d": float(et_base_mm_d),
        "kc_min": KC_MIN,
        "kc_max": KC_MAX,
        "main_vi": MAIN_VI,
        "comparison_vi": COMPARISON_VI,
    })


def reduce_kc_image_to_roi(image: ee.Image, roi: ee.Geometry, row: pd.Series) -> dict:
    bands = [
        "NDVI",
        "SAVI",
        "Kc_SAVI_dynamic",
        "ETc_SAVI_mm_d",
        "Kc_NDVI_dynamic",
        "ETc_NDVI_mm_d",
    ]

    reducers = (
        ee.Reducer.mean()
        .combine(ee.Reducer.median(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
        .combine(ee.Reducer.minMax(), sharedInputs=True)
    )

    reduced = image.select(bands).reduceRegion(
        reducer=reducers,
        geometry=roi,
        scale=REDUCE_SCALE_METERS,
        maxPixels=1_000_000,
        bestEffort=True,
    )

    props = reduced.getInfo()

    date_txt = pd.to_datetime(row["date"]).strftime("%Y-%m-%d")

    out = {
        "date": date_txt,
        "image_id": row.get("image_id", ""),
        "et_base_out_mm_d": float(row["et_base_out_mm_d"]),
        "valid_pixel_pct": float(row["valid_pixel_pct"]) if "valid_pixel_pct" in row and pd.notna(row["valid_pixel_pct"]) else np.nan,
        "kc_min": KC_MIN,
        "kc_max": KC_MAX,
        "main_vi": MAIN_VI,
        "comparison_vi": COMPARISON_VI,
    }

    for k, v in props.items():
        out[k] = v

    return out


def export_kc_image_to_drive(image: ee.Image, roi: ee.Geometry, date_txt: str) -> ee.batch.Task:
    export_bands = [
        "NDVI",
        "SAVI",
        "SAVI_norm",
        "NDVI_norm",
        "Kc_SAVI_dynamic",
        "ETc_SAVI_mm_d",
        "Kc_NDVI_dynamic",
        "ETc_NDVI_mm_d",
    ]

    export_img = image.select(export_bands).clip(roi).toFloat()

    description = f"kc_etc_sentinel_{date_txt.replace('-', '')}"
    file_prefix = description

    task = ee.batch.Export.image.toDrive(
        image=export_img,
        description=description,
        folder=DRIVE_FOLDER,
        fileNamePrefix=file_prefix,
        region=roi,
        scale=EXPORT_SCALE_METERS,
        crs=EXPORT_CRS,
        maxPixels=1_000_000_000,
        fileFormat="GeoTIFF",
    )

    task.start()
    return task


# =========================
# Main
# =========================
def main() -> None:
    analysis = load_analysis_table(INPUT_ANALYSIS)

    if analysis.empty:
        raise ValueError("station_sentinel_analysis_ready.csv está vacío.")

    ranges = get_observed_vi_ranges(analysis)

    params = {
        "method": "dynamic_kc_from_observed_vi_range",
        "interpretation": "exploratory_relative_kc_not_calibrated_universal",
        "kc_min": KC_MIN,
        "kc_max": KC_MAX,
        "main_vi": MAIN_VI,
        "comparison_vi": COMPARISON_VI,
        "buffer_meters": BUFFER_METERS,
        "reduce_scale_meters": REDUCE_SCALE_METERS,
        "export_to_drive": EXPORT_TO_DRIVE,
        "drive_folder": DRIVE_FOLDER,
        "vi_ranges": ranges,
        "n_analysis_dates": int(len(analysis)),
        "date_start": analysis["date"].min().strftime("%Y-%m-%d"),
        "date_end": analysis["date"].max().strftime("%Y-%m-%d"),
    }

    OUT_KC_PARAMS.write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")

    point_gdf = build_station_point_gdf(STATION_LAT, STATION_LON)
    buffer_gdf = build_buffer_gdf(point_gdf, BUFFER_METERS)
    save_vectors(point_gdf, buffer_gdf)

    init_ee()

    roi_fc = to_featurecollection_from_gdf(buffer_gdf)
    roi = roi_fc.geometry()

    rows_stats = []
    rows_tasks = []

    print("\n=== CONSTRUCCIÓN DE MAPAS Kc DINÁMICO / ETc ===")
    print(f"Fechas analysis-ready: {len(analysis)}")
    print(f"Rango: {params['date_start']} a {params['date_end']}")
    print(f"Kc_min={KC_MIN}, Kc_max={KC_MAX}")
    print("Rangos VI:")
    print(json.dumps(ranges, indent=2, ensure_ascii=False))

    for _, row in analysis.iterrows():
        date_txt = pd.to_datetime(row["date"]).strftime("%Y-%m-%d")
        et_base = float(row["et_base_out_mm_d"])

        print(f"\nProcesando {date_txt} | ET base = {et_base:.3f} mm/día")

        raw_img = get_sentinel_image_for_row(row)
        img = mask_s2_sr(raw_img)
        img = add_spectral_indices(img)
        img = add_dynamic_kc_and_etc(img, et_base, ranges)

        stats = reduce_kc_image_to_roi(img, roi, row)
        rows_stats.append(stats)

        print(
            f"Kc_SAVI_mean={stats.get('Kc_SAVI_dynamic_mean', np.nan)} | "
            f"ETc_SAVI_mean={stats.get('ETc_SAVI_mm_d_mean', np.nan)}"
        )

        if EXPORT_TO_DRIVE:
            task = export_kc_image_to_drive(img, roi, date_txt)
            rows_tasks.append({
                "date": date_txt,
                "description": task.config.get("description", ""),
                "task_id": task.id,
                "state_initial": task.status().get("state", ""),
                "drive_folder": DRIVE_FOLDER,
                "file_prefix": f"kc_etc_sentinel_{date_txt.replace('-', '')}",
            })
            print(f"Export task iniciado: {task.id}")

    stats_df = pd.DataFrame(rows_stats)
    stats_df.to_csv(OUT_KC_STATS, index=False)

    tasks_df = pd.DataFrame(rows_tasks)
    tasks_df.to_csv(OUT_EXPORT_TASKS, index=False)

    print("\n=== SALIDAS ===")
    print(f"Parámetros: {OUT_KC_PARAMS}")
    print(f"Estadísticas Kc/ETc: {OUT_KC_STATS}")
    print(f"Tareas de exportación: {OUT_EXPORT_TASKS}")

    if EXPORT_TO_DRIVE:
        print("\nRevisa tus tareas de Earth Engine / Google Drive.")
        print(f"Carpeta Drive esperada: {DRIVE_FOLDER}")


if __name__ == "__main__":
    main()