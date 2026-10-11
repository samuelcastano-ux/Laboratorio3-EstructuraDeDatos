from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from pathlib import Path


_COLUMNAS_REQUERIDAS = {
    "Experimento",
    "N",
    "Modo",
    "Estructura",
    "M",
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
    "ABB": "ABB",
    "ArbolBPlus": "Árbol B+",
}
_MARCADORES_MODO = {"IDs Aleatorios": "o", "IDs Ordenados": "s"}
_ESTILOS_MODO = {"IDs Aleatorios": "-", "IDs Ordenados": "--"}
_N_BARRIDO_ORDEN = 100_000
_N_MAXIMO = 1_000_000
_DPI = 300


def _configurar_ejes(ax: Axes) -> None:
    ax.minorticks_on()
    ax.grid(True, which="major", linestyle="-", alpha=0.45)
    ax.grid(True, which="minor", linestyle=":", alpha=0.25)


def _guardar(fig: Figure, ruta: Path) -> None:
    fig.savefig(ruta, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)


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
    for columna in (
        "N",
        "M",
        "Orden_BPlus",
        "Tiempo_Promedio_s",
        "IC95_Inferior_s",
        "IC95_Superior_s",
        "Memoria_Promedio_bytes",
        "Altura_Promedio",
        "Altura_Promedio",
    ):
        if columna not in datos.columns:
            datos[columna] = np.nan
        datos[columna] = pd.to_numeric(datos[columna], errors="coerce")

    if "Estado" in datos.columns:
        datos = datos.loc[datos["Estado"] == "medido"]
    if datos.empty:
        raise ValueError(f"El CSV no contiene resultados medidos: {ruta_csv}")
    if (datos["N"].dropna() <= 0).any():
        raise ValueError("Los tamaños N del CSV deben ser mayores que cero.")
    return datos


def _filtrar_experimento(
    datos: pd.DataFrame,
    experimento: str,
    modo: str | None = None,
) -> pd.DataFrame:
    seleccion = datos.loc[datos["Experimento"] == experimento]
    if modo is not None:
        seleccion = seleccion.loc[seleccion["Modo"] == modo]
    return seleccion


def _filtrar_orden_bplus_predeterminado(datos: pd.DataFrame) -> pd.DataFrame:
    return datos.loc[
        (datos["Estructura"] != "ArbolBPlus")
        | datos["Orden_BPlus"].isna()
        | (datos["Orden_BPlus"] == 16)
    ]


def _filtrar_m(datos: pd.DataFrame, m: int) -> pd.DataFrame:
    return datos.loc[datos["M"] == m]


def _leyenda(ax: Axes, *, titulo: str = "Estructura") -> None:
    handles, etiquetas = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, etiquetas, title=titulo, frameon=True)


def _etiqueta_serie(estructura: str, modo: str | None = None) -> str:
    nombre = _ETIQUETAS_ESTRUCTURAS.get(estructura, estructura)
    return f"{nombre}, {modo.removeprefix('IDs ')}" if modo else nombre


def _dibujar_series(
    ax: Axes,
    datos: pd.DataFrame,
    *,
    x: str,
    y: str,
    modo_en_estilo: bool = False,
    error_ic95: bool = False,
) -> None:
    columnas_grupo = ["Estructura"]
    if modo_en_estilo:
        columnas_grupo.append("Modo")

    for claves, grupo in datos.groupby(columnas_grupo, dropna=False, sort=False):
        if modo_en_estilo:
            estructura, modo = claves
        else:
            estructura = claves[0] if isinstance(claves, tuple) else claves
            modo = None
        agregaciones: dict[str, str] = {y: "mean"}
        if error_ic95:
            agregaciones["IC95_Inferior_s"] = "mean"
            agregaciones["IC95_Superior_s"] = "mean"
        grupo = (
            grupo.groupby(x, as_index=False, dropna=False)
            .agg(agregaciones)
            .sort_values(x)
        )
        etiqueta = _etiqueta_serie(str(estructura), str(modo) if modo else None)
        color = _PALETA_ESTRUCTURAS.get(str(estructura))
        marcador = _MARCADORES_MODO.get(str(modo), "o") if modo else "o"
        estilo = _ESTILOS_MODO.get(str(modo), "-") if modo else "-"

        ax.plot(
            grupo[x],
            grupo[y],
            label=etiqueta,
            color=color,
            marker=marcador,
            linestyle=estilo,
            linewidth=1.8,
            markersize=5,
        )
        if error_ic95:
            inferiores = pd.to_numeric(
                grupo["IC95_Inferior_s"],
                errors="coerce",
            )
            superiores = pd.to_numeric(
                grupo["IC95_Superior_s"],
                errors="coerce",
            )
            medias = pd.to_numeric(grupo[y], errors="coerce")
            valido = inferiores.notna() & superiores.notna() & medias.notna()
            if valido.any():
                errores = np.vstack(
                    (
                        np.maximum(medias[valido] - inferiores[valido], 0),
                        np.maximum(superiores[valido] - medias[valido], 0),
                    )
                )
                ax.errorbar(
                    grupo.loc[valido, x],
                    medias[valido],
                    yerr=errores,
                    fmt="none",
                    ecolor=color,
                    capsize=3,
                    linewidth=1,
                )


def _mensaje_sin_datos(ax: Axes, mensaje: str) -> None:
    ax.text(
        0.5,
        0.5,
        mensaje,
        transform=ax.transAxes,
        ha="center",
        va="center",
        wrap=True,
    )


def _preparar_figura(
    datos: pd.DataFrame,
    experimento: str,
    modo: str | None = None,
) -> pd.DataFrame:
    seleccion = _filtrar_experimento(datos, experimento, modo)
    return _filtrar_orden_bplus_predeterminado(seleccion)


def _guardar_matriz_comparativa(datos: pd.DataFrame, carpeta: Path) -> Path:
    fig, ejes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    configuraciones = (
        (ejes[0, 0], "Insercion", "IDs Aleatorios", "Inserción, IDs aleatorios"),
        (ejes[0, 1], "Insercion", "IDs Ordenados", "Inserción, IDs ordenados"),
        (ejes[1, 0], "Busqueda", "IDs Aleatorios", "Búsqueda, IDs aleatorios (M = 1000)"),
        (ejes[1, 1], "Busqueda", "IDs Ordenados", "Búsqueda, IDs ordenados (M = 1000)"),
    )
    for ax, experimento, modo, titulo in configuraciones:
        seleccion = _preparar_figura(datos, experimento, modo)
        if experimento == "Busqueda":
            seleccion = _filtrar_m(seleccion, 1_000)
        if seleccion.empty:
            _mensaje_sin_datos(ax, "Sin datos medidos para esta configuración.")
        else:
            _dibujar_series(ax, seleccion, x="N", y="Tiempo_Promedio_s", error_ic95=True)
            _leyenda(ax)
        ax.set_title(titulo)
        ax.set_xlabel("N (registros)")
        ax.set_ylabel("Tiempo promedio (s)")
        _configurar_ejes(ax)
    fig.suptitle("Inserción y búsqueda por estructura (IC 95%)", fontsize=15)
    ruta = carpeta / "matriz_comparativa.png"
    _guardar(fig, ruta)
    return ruta


def _guardar_semilog_busquedas(datos: pd.DataFrame, carpeta: Path) -> Path:
    seleccion = _preparar_figura(datos, "Busqueda")
    seleccion = seleccion.loc[seleccion["M"].isin((1_000, 10_000))]
    fig, ejes = plt.subplots(
        1,
        2,
        figsize=(15, 7),
        sharey=True,
        constrained_layout=True,
    )
    if seleccion.empty:
        for ax in ejes:
            _mensaje_sin_datos(ax, "Sin datos medidos para M = 1000 o M = 10000.")
    else:
        for ax, modo in zip(ejes, ("IDs Aleatorios", "IDs Ordenados")):
            subset = seleccion.loc[seleccion["Modo"] == modo]
            for (estructura, m), grupo in subset.groupby(
                ["Estructura", "M"],
                dropna=False,
                sort=False,
            ):
                grupo = (
                    grupo.groupby("N", as_index=False)["Tiempo_Promedio_s"]
                    .mean()
                    .sort_values("N")
                )
                ax.plot(
                    grupo["N"],
                    grupo["Tiempo_Promedio_s"],
                    color=_PALETA_ESTRUCTURAS.get(str(estructura)),
                    linestyle="-" if int(m) == 1_000 else "--",
                    marker="o" if int(m) == 1_000 else "s",
                    linewidth=1.7,
                    markersize=4,
                    label=f"{_ETIQUETAS_ESTRUCTURAS.get(str(estructura), estructura)}, M={int(m):,}",
                )
            ax.set_title(modo.removeprefix("IDs "))
            ax.set_yscale("log")
            ax.set_xlabel("N (registros, escala lineal)")
            _configurar_ejes(ax)
        handles, etiquetas = ejes[0].get_legend_handles_labels()
        if handles:
            fig.legend(
                handles,
                etiquetas,
                title="Estructura y tamaño del lote",
                loc="outside lower center",
                ncol=3,
            )
    ejes[0].set_ylabel("Tiempo por lote (s, escala logarítmica)")
    fig.suptitle("Búsqueda para M = 1000 y M = 10000")
    ruta = carpeta / "semilog_busquedas.png"
    _guardar(fig, ruta)
    return ruta


def _ajustar_pendiente(
    grupo: pd.DataFrame,
    *,
    x: str = "N",
    y: str = "Tiempo_Promedio_s",
) -> tuple[float, float, float, float] | None:
    valido = grupo.loc[
        (pd.to_numeric(grupo[x], errors="coerce") > 0)
        & (pd.to_numeric(grupo[y], errors="coerce") > 0)
    ]
    if len(valido) < 2:
        return None
    log_x = np.log10(valido[x].to_numpy(dtype=float))
    log_y = np.log10(valido[y].to_numpy(dtype=float))
    pendiente, intercepto = np.polyfit(log_x, log_y, 1)
    predichos = pendiente * log_x + intercepto
    suma_residuos = float(np.sum((log_y - predichos) ** 2))
    suma_total = float(np.sum((log_y - log_y.mean()) ** 2))
    r_cuadrado = 1.0 if suma_total == 0 else 1 - suma_residuos / suma_total
    return float(pendiente), float(intercepto), float(r_cuadrado), float(log_x.mean())


def _guardar_loglog_insercion(datos: pd.DataFrame, carpeta: Path) -> Path:
    seleccion = _preparar_figura(datos, "Insercion", "IDs Ordenados")
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    if seleccion.empty:
        _mensaje_sin_datos(ax, "Sin datos medidos para inserción ordenada.")
    else:
        limites_n: list[float] = []
        for estructura in _ORDEN_ESTRUCTURAS:
            grupo = seleccion.loc[seleccion["Estructura"] == estructura].sort_values("N")
            if grupo.empty:
                continue
            ajuste = _ajustar_pendiente(grupo)
            if ajuste is None:
                continue
            pendiente, intercepto, r_cuadrado, _ = ajuste
            etiqueta = (
                f"{_ETIQUETAS_ESTRUCTURAS[estructura]} "
                f"(m={pendiente:.3f}, R²={r_cuadrado:.3f})"
            )
            color = _PALETA_ESTRUCTURAS[estructura]
            ax.loglog(
                grupo["N"],
                grupo["Tiempo_Promedio_s"],
                marker="o",
                color=color,
                linewidth=1.8,
                label=etiqueta,
            )
            limites_n.extend(grupo["N"].astype(float).tolist())

        if limites_n:
            ns = np.asarray(limites_n)
            n_referencia = np.geomspace(ns.min(), ns.max(), 100)
            n_pivote = float(np.median(ns))
            referencia = seleccion.loc[seleccion["N"] == n_pivote]
            if referencia.empty:
                referencia = seleccion.iloc[[len(seleccion) // 2]]
            tiempo_pivote = float(referencia["Tiempo_Promedio_s"].median())
            for pendiente, nombre in ((1, "Referencia m=1"), (2, "Referencia m=2")):
                ax.loglog(
                    n_referencia,
                    tiempo_pivote * (n_referencia / n_pivote) ** pendiente,
                    linestyle=":",
                    color="gray",
                    label=nombre,
                )
        _leyenda(ax, titulo="Pendiente empírica; R²")
    ax.set_title("Inserción ordenada: pendiente empírica y referencias")
    ax.set_xlabel("N (registros, escala logarítmica)")
    ax.set_ylabel("Tiempo de inserción (s, escala logarítmica)")
    _configurar_ejes(ax)
    ruta = carpeta / "loglog_insercion.png"
    _guardar(fig, ruta)
    return ruta


def _guardar_extrapolacion(datos: pd.DataFrame, carpeta: Path) -> Path:
    seleccion = _preparar_figura(datos, "Insercion", "IDs Ordenados")
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    hay_extrapolacion = False
    if seleccion.empty:
        _mensaje_sin_datos(ax, "Sin datos medidos para proyectar inserción ordenada.")
    else:
        tamanios_proyeccion = np.asarray((200_000, 500_000, 750_000, 1_000_000))
        for estructura in _ORDEN_ESTRUCTURAS:
            grupo = seleccion.loc[seleccion["Estructura"] == estructura].sort_values("N")
            if grupo.empty:
                continue
            ax.loglog(
                grupo["N"],
                grupo["Tiempo_Promedio_s"],
                marker="o",
                color=_PALETA_ESTRUCTURAS[estructura],
                linestyle="-",
                label=f"{_ETIQUETAS_ESTRUCTURAS[estructura]} medido",
            )
            ajuste = _ajustar_pendiente(grupo)
            if ajuste is None:
                continue
            pendiente, intercepto, _, _ = ajuste
            n_ultimo = float(grupo["N"].max())
            proyectados = tamanios_proyeccion[tamanios_proyeccion > n_ultimo]
            if not len(proyectados):
                continue
            tiempos_proyectados = 10 ** (
                intercepto + pendiente * np.log10(proyectados)
            )
            ax.loglog(
                np.concatenate(([n_ultimo], proyectados)),
                np.concatenate(
                    (
                        [float(grupo.iloc[-1]["Tiempo_Promedio_s"])],
                        tiempos_proyectados,
                    )
                ),
                linestyle=":",
                color=_PALETA_ESTRUCTURAS[estructura],
                marker="X",
                markersize=7,
                label=f"{_ETIQUETAS_ESTRUCTURAS[estructura]} extrapolado",
            )
            hay_extrapolacion = True
    ax.set_xlim(left=1)
    ax.set_ylim(bottom=1e-9)
    ax.set_title("Inserción ordenada hasta N = 1.000.000")
    ax.set_xlabel("N (registros, escala logarítmica)")
    ax.set_ylabel("Tiempo (s, escala logarítmica)")
    if hay_extrapolacion:
        ax.text(
            0.02,
            0.02,
            "Puntos X: extrapolado",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
        )
    _leyenda(ax)
    _configurar_ejes(ax)
    ruta = carpeta / "loglog_extrapolacion.png"
    _guardar(fig, ruta)
    return ruta


def _guardar_busqueda_vs_m(datos: pd.DataFrame, carpeta: Path) -> Path:
    n_objetivo = 10_000
    seleccion = _preparar_figura(datos, "Busqueda", "IDs Aleatorios")
    seleccion = seleccion.loc[
        (seleccion["N"] == n_objetivo) & seleccion["M"].notna()
    ]
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    if seleccion.empty:
        _mensaje_sin_datos(ax, f"Sin datos para búsqueda aleatoria con N={n_objetivo:,}.")
    else:
        for estructura in _ORDEN_ESTRUCTURAS:
            grupo = seleccion.loc[seleccion["Estructura"] == estructura].sort_values("M")
            if grupo.empty:
                continue
            xs = grupo["M"].to_numpy(dtype=float)
            ys = grupo["Tiempo_Promedio_s"].to_numpy(dtype=float)
            ajuste = None
            if len(xs) >= 2:
                pendiente, intercepto = np.polyfit(xs, ys, 1)
                predichos = pendiente * xs + intercepto
                ss_res = float(np.sum((ys - predichos) ** 2))
                ss_total = float(np.sum((ys - ys.mean()) ** 2))
                r_cuadrado = 1.0 if ss_total == 0 else 1 - ss_res / ss_total
                ajuste = (pendiente, intercepto, r_cuadrado)
            etiqueta = _ETIQUETAS_ESTRUCTURAS[estructura]
            if ajuste:
                etiqueta += f" (ajuste lineal R²={ajuste[2]:.3f})"
            color = _PALETA_ESTRUCTURAS[estructura]
            ax.plot(xs, ys, "o-", color=color, label=etiqueta)
            if ajuste:
                rango_m = np.linspace(xs.min(), xs.max(), 100)
                ax.plot(
                    rango_m,
                    ajuste[0] * rango_m + ajuste[1],
                    linestyle=":",
                    color=color,
                    label=f"{_ETIQUETAS_ESTRUCTURAS[estructura]} ajuste",
                )
        _leyenda(ax, titulo="Estructura / ajuste")
    ax.set_title(f"Búsqueda frente al tamaño del lote (N = {n_objetivo:,})")
    ax.set_xlabel("M (búsquedas por lote)")
    ax.set_ylabel("Tiempo por lote (s)")
    _configurar_ejes(ax)
    ruta = carpeta / "busqueda_vs_m.png"
    _guardar(fig, ruta)
    return ruta


def _guardar_altura(datos: pd.DataFrame, carpeta: Path) -> Path:
    alturas = _preparar_figura(datos, "Altura")
    tiempos = _preparar_figura(datos, "Busqueda")
    tiempos = _filtrar_m(tiempos, 1_000)
    fig, (ax_altura, ax_tiempo) = plt.subplots(
        1,
        2,
        figsize=(15, 6),
        constrained_layout=True,
    )
    if alturas.empty or alturas["Altura_Promedio"].isna().all():
        _mensaje_sin_datos(ax_altura, "Sin mediciones de altura en el CSV.")
    else:
        _dibujar_series(ax_altura, alturas, x="N", y="Altura_Promedio", modo_en_estilo=True)
        _leyenda(ax_altura, titulo="Estructura y escenario")
    ax_altura.set_title("Altura frente a N")
    ax_altura.set_xlabel("N (registros)")
    ax_altura.set_ylabel("Altura (niveles)")
    _configurar_ejes(ax_altura)

    combinada = (
        tiempos[["N", "Modo", "Estructura", "Tiempo_Promedio_s"]]
        .drop_duplicates()
        .merge(
            alturas[["N", "Modo", "Estructura", "Altura_Promedio"]]
            .drop_duplicates(),
            on=["N", "Modo", "Estructura"],
            how="inner",
            suffixes=("", "_altura"),
        )
        if not alturas.empty
        else pd.DataFrame()
    )
    if combinada.empty or combinada["Altura_Promedio"].isna().all():
        _mensaje_sin_datos(ax_tiempo, "Sin datos compatibles de tiempo y altura.")
    else:
        for (estructura, modo), grupo in combinada.groupby(
            ["Estructura", "Modo"],
            sort=False,
        ):
            grupo = grupo.sort_values("N")
            ax_tiempo.plot(
                grupo["Altura_Promedio"],
                grupo["Tiempo_Promedio_s"],
                color=_PALETA_ESTRUCTURAS.get(str(estructura)),
                linestyle="-",
                marker="o",
                label=_etiqueta_serie(str(estructura), str(modo)),
            )
        _leyenda(ax_tiempo, titulo="Estructura y escenario")
    ax_tiempo.set_title("Búsqueda M = 1000 frente a altura")
    ax_tiempo.set_xlabel("Altura (niveles)")
    ax_tiempo.set_ylabel("Tiempo por lote (s)")
    _configurar_ejes(ax_tiempo)
    fig.suptitle("Altura y tiempo de búsqueda")
    ruta = carpeta / "altura.png"
    ruta_alias = carpeta / "altura_y_busqueda.png"
    fig.savefig(ruta, dpi=_DPI, bbox_inches="tight")
    fig.savefig(ruta_alias, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    return ruta


def _guardar_listar(datos: pd.DataFrame, carpeta: Path) -> Path:
    seleccion = _preparar_figura(datos, "Listar")
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    if seleccion.empty:
        _mensaje_sin_datos(ax, "Sin mediciones de listar() en el CSV.")
    else:
        _dibujar_series(ax, seleccion, x="N", y="Tiempo_Promedio_s", modo_en_estilo=True)
        _leyenda(ax, titulo="Estructura y escenario")
    ax.set_title("Tiempo de listar() frente a N")
    ax.set_xlabel("N (registros)")
    ax.set_ylabel("Tiempo de listar() (s)")
    _configurar_ejes(ax)
    ruta = carpeta / "listar_vs_n.png"
    _guardar(fig, ruta)
    return ruta


def _guardar_memoria(datos: pd.DataFrame, carpeta: Path) -> Path:
    seleccion = _preparar_figura(datos, "Memoria")
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    if seleccion.empty or seleccion["Memoria_Promedio_bytes"].isna().all():
        _mensaje_sin_datos(ax, "Sin mediciones de memoria en el CSV.")
    else:
        _dibujar_series(
            ax,
            seleccion,
            x="N",
            y="Memoria_Promedio_bytes",
            modo_en_estilo=True,
        )
        _leyenda(ax, titulo="Estructura y escenario")
    ax.set_title("Memoria pico frente a N")
    ax.set_xlabel("N (registros)")
    ax.set_ylabel("Memoria pico (bytes)")
    _configurar_ejes(ax)
    ruta = carpeta / "memoria_vs_n.png"
    _guardar(fig, ruta)
    return ruta


def _guardar_orden_bplus(datos: pd.DataFrame, carpeta: Path) -> Path:
    seleccion = datos.loc[
        (datos["Estructura"] == "ArbolBPlus")
        & (datos["N"] == _N_BARRIDO_ORDEN)
    ]
    experimentos = (
        ("Insercion", None, "Inserción"),
        ("Busqueda", 1_000, "Búsqueda (M=1000)"),
        ("Listar", None, "Listar"),
        ("Rango", None, "Rango"),
        ("Altura", None, "Altura"),
        ("Memoria", None, "Memoria"),
    )
    fig, ejes = plt.subplots(2, 3, figsize=(17, 10), constrained_layout=True)
    for ax, (experimento, m, titulo) in zip(ejes.flat, experimentos):
        grupo = _filtrar_experimento(seleccion, experimento)
        if m is not None:
            grupo = _filtrar_m(grupo, m)
        if grupo.empty:
            _mensaje_sin_datos(ax, "Sin datos de barrido para orden B+.")
        elif experimento == "Memoria":
            for modo, filas in grupo.groupby("Modo", sort=False):
                ax.plot(
                    filas["Orden_BPlus"],
                    filas["Memoria_Promedio_bytes"],
                    marker=_MARCADORES_MODO.get(str(modo), "o"),
                    linestyle=_ESTILOS_MODO.get(str(modo), "-"),
                    label=str(modo).removeprefix("IDs "),
                )
            ax.set_ylabel("Memoria pico (bytes)")
            _leyenda(ax, titulo="Escenario")
        elif experimento == "Altura":
            for modo, filas in grupo.groupby("Modo", sort=False):
                ax.plot(
                    filas["Orden_BPlus"],
                    filas["Altura_Promedio"],
                    marker=_MARCADORES_MODO.get(str(modo), "o"),
                    linestyle=_ESTILOS_MODO.get(str(modo), "-"),
                    label=str(modo).removeprefix("IDs "),
                )
            ax.set_ylabel("Altura (niveles)")
            _leyenda(ax, titulo="Escenario")
        else:
            _dibujar_series(ax, grupo, x="Orden_BPlus", y="Tiempo_Promedio_s", modo_en_estilo=True)
            ax.set_ylabel("Tiempo (s)")
            _leyenda(ax, titulo="Escenario")
        ax.set_title(titulo)
        ax.set_xlabel("Orden del árbol B+")
        _configurar_ejes(ax)
    fig.suptitle("Efecto del orden del árbol B+ (N = 100.000)", fontsize=15)
    ruta = carpeta / "orden_bplus.png"
    _guardar(fig, ruta)
    return ruta


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

    return [
        _guardar_matriz_comparativa(datos, carpeta),
        _guardar_semilog_busquedas(datos, carpeta),
        _guardar_loglog_insercion(datos, carpeta),
        _guardar_extrapolacion(datos, carpeta),
        _guardar_busqueda_vs_m(datos, carpeta),
        _guardar_altura(datos, carpeta),
        _guardar_listar(datos, carpeta),
        _guardar_memoria(datos, carpeta),
        _guardar_orden_bplus(datos, carpeta),
    ]
