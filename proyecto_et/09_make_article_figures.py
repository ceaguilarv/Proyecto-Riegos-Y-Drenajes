from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# ============================================================
# 09_make_article_figures.py
# Genera figuras de artículo para el análisis estación vs
# proxies espectrales Sentinel-2.
# ============================================================


# =========================
# Configuración
# =========================
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "data" / "processed"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "article_figures"
FALLBACK_INPUT_DIR = BASE_DIR
FALLBACK_OUTPUT_DIR = BASE_DIR / "article_figures"

FIG_DPI = 300
SAVE_BBOX = "tight"


# =========================
# Etiquetas
# =========================
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

PREDICTOR_ORDER = ["NDVI_mean", "EVI_mean", "SAVI_mean", "NDRE_mean"]


# =========================
# Rutas
# =========================
def resolve_input_output_dirs() -> tuple[Path, Path]:
    if DEFAULT_INPUT_DIR.exists():
        input_dir = DEFAULT_INPUT_DIR
        output_dir = DEFAULT_OUTPUT_DIR
    else:
        input_dir = FALLBACK_INPUT_DIR
        output_dir = FALLBACK_OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir


INPUT_DIR, OUTPUT_DIR = resolve_input_output_dirs()

INPUT_ANALYSIS = INPUT_DIR / "station_sentinel_analysis_ready.csv"
INPUT_BEST = INPUT_DIR / "station_sentinel_best_models.csv"
INPUT_CORR = INPUT_DIR / "station_sentinel_correlations.csv"
INPUT_REG = INPUT_DIR / "station_sentinel_simple_regressions.csv"
INPUT_S2_DAILY = INPUT_DIR / "sentinel2_daily_series.csv"
INPUT_STATION_DAILY = INPUT_DIR / "station_daily_exterior_ready.csv"

OUT_FIG01 = OUTPUT_DIR / "fig01_station_satellite_timeline.png"
OUT_FIG02 = OUTPUT_DIR / "fig02_scatter_best_same_day_model.png"
OUT_FIG03 = OUTPUT_DIR / "fig03_scatter_same_day_predictor_grid.png"
OUT_FIG04 = OUTPUT_DIR / "fig04_best_model_ranking.png"
OUT_FIG05 = OUTPUT_DIR / "fig05_temporal_windows_best_predictor.png"


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def load_csv(path: Path, parse_dates: bool = True) -> pd.DataFrame:
    ensure_file(path)
    df = pd.read_csv(path)
    if parse_dates and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def to_numeric_if_exists(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def fit_line(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return float(intercept), float(slope)


def add_regression_line(ax, x: np.ndarray, y: np.ndarray) -> None:
    if len(x) < 2:
        return
    intercept, slope = fit_line(x, y)
    xs = np.linspace(np.nanmin(x), np.nanmax(x), 100)
    ys = intercept + slope * xs
    ax.plot(xs, ys, linewidth=1.5)


def prettify_axes(ax, x_label: str | None = None, y_label: str | None = None, title: str | None = None) -> None:
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)
    if title:
        ax.set_title(title)
    ax.grid(True, alpha=0.3)


def get_best_same_day_model(best: pd.DataFrame) -> pd.Series:
    same_day = best.loc[best["target"] == "et_base_out_mm_d"].copy()
    if same_day.empty:
        raise ValueError("No se encontró modelo de mismo día en station_sentinel_best_models.csv")
    same_day = same_day.sort_values(["r2", "rmse"], ascending=[False, True]).reset_index(drop=True)
    return same_day.iloc[0]


def build_label_target(target: str) -> str:
    return TARGET_LABELS.get(target, target)


def build_label_predictor(pred: str) -> str:
    return PREDICTOR_LABELS.get(pred, pred)


# =========================
# Figura 1
# =========================
def make_fig01_timeline(station: pd.DataFrame, s2: pd.DataFrame, best_same_day_predictor: str) -> None:
    station = station.copy().sort_values("date")
    s2 = s2.copy().sort_values("date")

    fig, ax1 = plt.subplots(figsize=(11, 5.5))

    if "et_base_out_mm_d" not in station.columns:
        raise ValueError("Falta columna et_base_out_mm_d en station_daily_exterior_ready.csv")

    ax1.plot(
        station["date"],
        station["et_base_out_mm_d"],
        linewidth=1.2,
        label="ET estación diaria",
    )

    sat_station = station[["date", "et_base_out_mm_d"]].merge(
        s2[["date"]], on="date", how="inner"
    )

    if not sat_station.empty:
        ax1.scatter(
            sat_station["date"],
            sat_station["et_base_out_mm_d"],
            s=28,
            label="Fechas Sentinel-2",
        )

    prettify_axes(
        ax1,
        x_label="Fecha",
        y_label="ET estación (mm/día)",
        title="Serie temporal de ET diaria de estación y fechas Sentinel-2",
    )
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")

    ax2 = ax1.twinx()
    if best_same_day_predictor in s2.columns:
        ax2.plot(
            s2["date"],
            s2[best_same_day_predictor],
            linestyle="--",
            marker="o",
            markersize=3,
            linewidth=1.0,
            label=f"{build_label_predictor(best_same_day_predictor)} en fechas satelitales",
        )
        ax2.set_ylabel(f"{build_label_predictor(best_same_day_predictor)} (adimensional)")

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    if handles1 or handles2:
        ax1.legend(handles1 + handles2, labels1 + labels2, loc="best")

    fig.savefig(OUT_FIG01, dpi=FIG_DPI, bbox_inches=SAVE_BBOX)
    plt.close(fig)


# =========================
# Figura 2
# =========================
def make_fig02_best_scatter(analysis: pd.DataFrame, best_model: pd.Series) -> None:
    target = best_model["target"]
    predictor = best_model["predictor"]

    sub = analysis[[target, predictor, "date"]].dropna().copy()
    x = sub[predictor].to_numpy(dtype=float)
    y = sub[target].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.scatter(x, y, s=38)

    add_regression_line(ax, x, y)

    for _, row in sub.iterrows():
        x_val = float(row[predictor])
        y_val = float(row[target])
        date_txt = pd.to_datetime(row["date"]).strftime("%m-%d")
        ax.annotate(date_txt, (x_val, y_val), xytext=(4, 4), textcoords="offset points", fontsize=8)

    title = (
        f"Mejor modelo mismo día: {build_label_target(target)} vs "
        f"{build_label_predictor(predictor)}"
    )
    subtitle = (
        f"n={int(best_model['n'])}, r={best_model['pearson_r']:.3f}, "
        f"R²={best_model['r2']:.3f}, RMSE={best_model['rmse']:.3f}"
    )
    prettify_axes(
        ax,
        x_label=build_label_predictor(predictor),
        y_label="ET estación (mm/día)",
        title=title,
    )
    ax.text(0.01, 0.99, subtitle, transform=ax.transAxes, va="top", ha="left")

    fig.savefig(OUT_FIG02, dpi=FIG_DPI, bbox_inches=SAVE_BBOX)
    plt.close(fig)


# =========================
# Figura 3
# =========================
def make_fig03_predictor_grid(analysis: pd.DataFrame, regs: pd.DataFrame) -> None:
    target = "et_base_out_mm_d"
    available_predictors = [p for p in PREDICTOR_ORDER if p in analysis.columns]

    fig, axes = plt.subplots(2, 2, figsize=(10, 8), sharey=True)
    axes = axes.ravel()

    y_all = pd.to_numeric(analysis[target], errors="coerce")
    y_min = np.nanmin(y_all)
    y_max = np.nanmax(y_all)

    for ax, predictor in zip(axes, available_predictors):
        sub = analysis[[target, predictor]].dropna().copy()
        x = sub[predictor].to_numpy(dtype=float)
        y = sub[target].to_numpy(dtype=float)

        ax.scatter(x, y, s=30)
        add_regression_line(ax, x, y)

        reg_match = regs.loc[(regs["target"] == target) & (regs["predictor"] == predictor)]
        if not reg_match.empty:
            row = reg_match.iloc[0]
            metric_txt = f"r={row['pearson_r']:.3f}\nR²={row['r2']:.3f}"
            ax.text(0.03, 0.97, metric_txt, transform=ax.transAxes, va="top", ha="left")

        ax.set_ylim(y_min - 0.05, y_max + 0.05)
        prettify_axes(
            ax,
            x_label=build_label_predictor(predictor),
            y_label="ET estación (mm/día)",
            title=f"{build_label_predictor(predictor)} vs ET mismo día",
        )

    for ax in axes[len(available_predictors):]:
        ax.axis("off")

    fig.suptitle("Comparación de predictores satelitales para ET del mismo día", y=1.02)
    fig.savefig(OUT_FIG03, dpi=FIG_DPI, bbox_inches=SAVE_BBOX)
    plt.close(fig)


# =========================
# Figura 4
# =========================
def make_fig04_best_model_ranking(best: pd.DataFrame) -> None:
    plot_df = best.copy()
    if plot_df.empty:
        return

    plot_df["target_label"] = plot_df["target"].map(TARGET_LABELS).fillna(plot_df["target"])
    plot_df["predictor_label"] = plot_df["predictor"].map(PREDICTOR_LABELS).fillna(plot_df["predictor"])
    plot_df["combo_label"] = plot_df["target_label"] + " ← " + plot_df["predictor_label"]

    order_map = {k: i for i, k in enumerate(TEMPORAL_ORDER)}
    plot_df["target_order"] = plot_df["target"].map(order_map).fillna(999)
    plot_df = plot_df.sort_values(["target_order", "r2"], ascending=[True, False]).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(plot_df["combo_label"], plot_df["r2"])
    prettify_axes(
        ax,
        x_label="R²",
        y_label="Mejor modelo por target",
        title="Desempeño de los mejores modelos por escala temporal",
    )
    ax.invert_yaxis()

    for i, (_, row) in enumerate(plot_df.iterrows()):
        ax.text(float(row["r2"]) + 0.01, i, f"r={row['pearson_r']:.3f}", va="center", fontsize=8)

    fig.savefig(OUT_FIG04, dpi=FIG_DPI, bbox_inches=SAVE_BBOX)
    plt.close(fig)


# =========================
# Figura 5
# =========================
def make_fig05_temporal_windows(corrs: pd.DataFrame, best_same_day_predictor: str) -> None:
    plot_df = corrs.loc[corrs["predictor"] == best_same_day_predictor].copy()
    if plot_df.empty:
        return

    order_map = {k: i for i, k in enumerate(TEMPORAL_ORDER)}
    plot_df = plot_df.loc[plot_df["target"].isin(TEMPORAL_ORDER)].copy()
    plot_df["order"] = plot_df["target"].map(order_map)
    plot_df = plot_df.sort_values("order").reset_index(drop=True)

    plot_df["target_label"] = plot_df["target"].map(TARGET_LABELS).fillna(plot_df["target"])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(plot_df["target_label"], plot_df["pearson_r"], marker="o", linewidth=1.5)
    prettify_axes(
        ax,
        x_label="Escala temporal de ET",
        y_label="Correlación de Pearson (r)",
        title=f"Comparación temporal usando {build_label_predictor(best_same_day_predictor)}",
    )
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")

    for _, row in plot_df.iterrows():
        ax.annotate(
            f"{row['pearson_r']:.3f}",
            (row["target_label"], row["pearson_r"]),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )

    fig.savefig(OUT_FIG05, dpi=FIG_DPI, bbox_inches=SAVE_BBOX)
    plt.close(fig)


# =========================
# Main
# =========================
def main() -> None:
    analysis = load_csv(INPUT_ANALYSIS)
    best = load_csv(INPUT_BEST)
    corrs = load_csv(INPUT_CORR)
    regs = load_csv(INPUT_REG)
    s2 = load_csv(INPUT_S2_DAILY)
    station = load_csv(INPUT_STATION_DAILY)

    numeric_cols_analysis = [
        "et_base_out_mm_d",
        "et_base_out_mm_d_w3_mean",
        "et_base_out_mm_d_w5_mean",
        "et_base_out_mm_d_w7_mean",
        "et_base_out_mm_d_w3_sum",
        "et_base_out_mm_d_w5_sum",
        "et_base_out_mm_d_w7_sum",
        "NDVI_mean",
        "EVI_mean",
        "SAVI_mean",
        "NDRE_mean",
        "valid_pixel_pct",
        "cloudy_pixel_percentage",
    ]
    numeric_cols_stats = [
        "n",
        "intercept",
        "slope",
        "r2",
        "rmse",
        "mae",
        "bias",
        "pearson_r",
        "spearman_rho",
    ]

    analysis = to_numeric_if_exists(analysis, numeric_cols_analysis)
    best = to_numeric_if_exists(best, numeric_cols_stats)
    corrs = to_numeric_if_exists(corrs, ["n", "pearson_r", "spearman_rho"])
    regs = to_numeric_if_exists(regs, numeric_cols_stats)
    s2 = to_numeric_if_exists(
        s2,
        ["valid_pixel_pct", "cloudy_pixel_percentage", "NDVI_mean", "EVI_mean", "SAVI_mean", "NDRE_mean"],
    )
    station = to_numeric_if_exists(station, ["et_base_out_mm_d"])

    best_same_day = get_best_same_day_model(best)
    best_same_day_predictor = str(best_same_day["predictor"])

    make_fig01_timeline(station, s2, best_same_day_predictor)
    make_fig02_best_scatter(analysis, best_same_day)
    make_fig03_predictor_grid(analysis, regs)
    make_fig04_best_model_ranking(best)
    make_fig05_temporal_windows(corrs, best_same_day_predictor)

    print("\n=== FIGURAS DE ARTÍCULO: ESTACIÓN vs PROXIES SENTINEL-2 ===")
    print(f"Mejor predictor mismo día: {best_same_day_predictor}")
    print(f"Figura 1: {OUT_FIG01}")
    print(f"Figura 2: {OUT_FIG02}")
    print(f"Figura 3: {OUT_FIG03}")
    print(f"Figura 4: {OUT_FIG04}")
    print(f"Figura 5: {OUT_FIG05}")


if __name__ == "__main__":
    main()