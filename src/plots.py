from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes
from pathlib import Path


_COLUMNAS_REQUERIDAS = {
    "Experimento",
    "N",
    "Modo",
    "Estructura",
    "Q",
    "Tiempo_Promedio_s",
}
_ORDEN_ESTRUCTURAS = ("ListaEnlazada", "ABB", "ArbolBPlus")
_PALETA_ESTRUCTURAS = {
    "ListaEnlazada": "crimson",
    "ABB": "darkorange",
    "ArbolBPlus": "royalblue",
}
_ETIQUETAS_ESTRUCTURAS = {
    "ListaEnlazada": "Lista enlazada",
    "ABB": "Árbol binario de búsqueda (ABB)",
    "ArbolBPlus": "Árbol B+",
}


def _formatear_tiempo_segundos(tiempo: float) -> str:
    return f"{tiempo:.3g} s"


def _cargar_resultados(ruta_csv: Path) -> pd.DataFrame:
    if not ruta_csv.is_file():
        raise FileNotFoundError(
            f"No se encontró el CSV de resultados del benchmark: {ruta_csv}"
        )

    datos = pd.read_csv(ruta_csv)
    faltantes = _COLUMNAS_REQUERIDAS.difference(datos.columns)
    if faltantes:
        columnas = ", ".join(sorted(faltantes))
        raise ValueError(f"El CSV del benchmark no contiene las columnas: {columnas}.")
    if datos.empty:
        raise ValueError(f"El CSV del benchmark no contiene resultados: {ruta_csv}")

    datos = datos.copy()
    datos["N"] = pd.to_numeric(datos["N"], errors="raise")
    datos["Tiempo_Promedio_s"] = pd.to_numeric(
        datos["Tiempo_Promedio_s"],
        errors="raise",
    )
    datos["Q"] = pd.to_numeric(datos["Q"], errors="coerce")

    if (datos["N"] <= 0).any():
        raise ValueError("Los tamaños N del CSV deben ser mayores que cero.")
    if (datos["Tiempo_Promedio_s"] <= 0).any():
        raise ValueError("Los tiempos promedio deben ser mayores que cero.")

    return datos


def _dibujar_lineas(
    ax: Axes,
    datos: pd.DataFrame,
    x: str,
    y: str,
) -> None:
    sns.lineplot(
        data=datos.sort_values(x),
        x=x,
        y=y,
        hue="Estructura",
        hue_order=_ORDEN_ESTRUCTURAS,
        palette=_PALETA_ESTRUCTURAS,
        style="Estructura",
        style_order=_ORDEN_ESTRUCTURAS,
        markers=True,
        dashes=False,
        estimator=None,
        sort=True,
        linewidth=2.2,
        markersize=6,
        ax=ax,
    )
    handles, etiquetas = ax.get_legend_handles_labels()
    ax.legend(
        handles,
        [_ETIQUETAS_ESTRUCTURAS.get(etiqueta, etiqueta) for etiqueta in etiquetas],
        title="Estructura (tiempo en s)",
        frameon=True,
    )
    ax.grid(True, which="both", linestyle="--", alpha=0.45)


def _anotar_tiempos(ax: Axes, datos: pd.DataFrame) -> None:
    for indice, estructura in enumerate(_ORDEN_ESTRUCTURAS):
        puntos = datos.loc[datos["Estructura"] == estructura]
        for _, punto in puntos.iterrows():
            ax.annotate(
                _formatear_tiempo_segundos(punto["Tiempo_Promedio_s"]),
                xy=(punto["N"], punto["Tiempo_Promedio_s"]),
                xytext=(0, 7 + indice * 6),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
            )


def _filtrar_experimento(
    datos: pd.DataFrame,
    experimento: str,
    modo: str,
) -> pd.DataFrame:
    seleccion = datos.loc[
        (datos["Experimento"] == experimento) & (datos["Modo"] == modo)
    ]
    if seleccion.empty:
        raise ValueError(
            f"El CSV no tiene datos para el experimento {experimento!r} "
            f"en modo {modo!r}."
        )
    return seleccion


def _guardar_matriz_comparativa(datos: pd.DataFrame, carpeta: Path) -> None:
    sns.set_theme(style="whitegrid")
    fig, ejes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    configuraciones = (
        (ejes[0, 0], "Insercion", "IDs Aleatorios", "Inserción con IDs aleatorios"),
        (ejes[0, 1], "Insercion", "IDs Ordenados", "Inserción con IDs ordenados"),
        (ejes[1, 0], "Busqueda", "IDs Aleatorios", "Búsqueda con IDs aleatorios (Q = 1000)"),
        (ejes[1, 1], "Busqueda", "IDs Ordenados", "Búsqueda con IDs ordenados (Q = 1000)"),
    )

    for ax, experimento, modo, titulo in configuraciones:
        seleccion = _filtrar_experimento(datos, experimento, modo)
        if experimento == "Busqueda":
            seleccion = seleccion.loc[seleccion["Q"] == 1000]
            if seleccion.empty:
                raise ValueError(
                    "El CSV no incluye resultados de búsqueda con Q = 1000 "
                    f"para el modo {modo!r}."
                )
        _dibujar_lineas(ax, seleccion, "N", "Tiempo_Promedio_s")
        _anotar_tiempos(ax, seleccion)
        ax.set_title(titulo, fontsize=12, fontweight="bold")
        ax.set_xlabel("Cantidad de registros, N")
        ax.set_ylabel("Tiempo de Ejecución (s)")

        if experimento == "Insercion" and modo == "Ordenado":
            abb = seleccion.loc[seleccion["Estructura"] == "ABB"].sort_values("N")
            if not abb.empty:
                punto = abb.iloc[-1]
                ax.annotate(
                    "Degradación del ABB\ncon inserción ordenada\n"
                    f"{_formatear_tiempo_segundos(punto['Tiempo_Promedio_s'])}",
                    xy=(punto["N"], punto["Tiempo_Promedio_s"]),
                    xytext=(-145, -45),
                    textcoords="offset points",
                    color=_PALETA_ESTRUCTURAS["ABB"],
                    fontsize=9,
                    fontweight="bold",
                    arrowprops={
                        "arrowstyle": "->",
                        "color": _PALETA_ESTRUCTURAS["ABB"],
                    },
                )

    fig.suptitle(
        "Comparación del rendimiento de las estructuras de datos",
        fontsize=16,
        fontweight="bold",
    )
    fig.savefig(carpeta / "matriz_comparativa.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def _guardar_semilog_busquedas(datos: pd.DataFrame, carpeta: Path) -> None:
    seleccion = datos.loc[
        (datos["Experimento"] == "Busqueda")
        & (datos["Modo"] == "IDs Aleatorios")
        & (datos["Q"] == 1000)
    ]
    if seleccion.empty:
        raise ValueError(
            "El CSV no incluye resultados de búsqueda aleatoria con Q = 1000."
        )

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    _dibujar_lineas(ax, seleccion, "N", "Tiempo_Promedio_s")
    _anotar_tiempos(ax, seleccion)
    ax.set_yscale("log")
    ax.set_title(
        "Búsqueda aleatoria: 1.000 consultas por ráfaga según el tamaño de entrada",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Cantidad de registros, N")
    ax.set_ylabel("Tiempo de Ejecución (s)")
    ax.grid(True, which="both", linestyle="--", alpha=0.45)
    fig.savefig(carpeta / "semilog_busquedas.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def _guardar_loglog_insercion(datos: pd.DataFrame, carpeta: Path) -> None:
    seleccion = _filtrar_experimento(datos, "Insercion", "IDs Ordenados")

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    _dibujar_lineas(ax, seleccion, "N", "Tiempo_Promedio_s")
    _anotar_tiempos(ax, seleccion)
    ax.set_xscale("log", base=10)
    ax.set_yscale("log", base=10)
    ax.set_title(
        "Inserción con IDs ordenados: análisis log-log",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Cantidad de registros, N (escala log10)")
    ax.set_ylabel("Tiempo de Ejecución (s)")

    ax.text(
        0.03,
        0.96,
        "Pendientes teóricas:\nABB: m ≈ 2  ·  O(N²)\n"
        "Árbol B+ y lista: m ≈ 1  ·  O(N)",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "white", "alpha": 0.9},
    )
    ax.grid(True, which="both", linestyle="--", alpha=0.45)
    fig.savefig(carpeta / "loglog_insercion.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def generar_todas_las_graficas(
    ruta_csv: str | Path | None = None,
    carpeta_salida: str | Path | None = None,
) -> list[Path]:
    raiz_proyecto = Path(__file__).resolve().parent.parent
    archivo_csv = (
        Path(ruta_csv)
        if ruta_csv is not None
        else raiz_proyecto / "resultados" / "resultados_benchmark.csv"
    )
    carpeta = (
        Path(carpeta_salida)
        if carpeta_salida is not None
        else raiz_proyecto / "graficas"
    )
    datos = _cargar_resultados(archivo_csv)
    carpeta.mkdir(parents=True, exist_ok=True)

    _guardar_matriz_comparativa(datos, carpeta)
    _guardar_semilog_busquedas(datos, carpeta)
    _guardar_loglog_insercion(datos, carpeta)

    return [
        carpeta / "matriz_comparativa.png",
        carpeta / "semilog_busquedas.png",
        carpeta / "loglog_insercion.png",
    ]