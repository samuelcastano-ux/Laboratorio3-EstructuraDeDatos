from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from src.benchmark import ejecutar_benchmark_completo
from src.plots import generar_todas_las_graficas


_TAMANOS_RESUMEN = (10_000, 100_000, 1_000_000)
_COLUMNAS_TABLA = (
    "Experimento",
    "Modo",
    "Estructura",
    "M",
    "Tiempo (s), media ± desviación",
    "Estado",
)


def _markdown_table(tabla: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(tabla.columns) + " |"
    separador = "| " + " | ".join("---" for _ in tabla.columns) + " |"
    filas = [
        "| " + " | ".join(str(valor) for valor in fila) + " |"
        for fila in tabla.itertuples(index=False, name=None)
    ]
    return "\n".join((encabezado, separador, *filas))


def _formatear_numero(valor: object) -> str:
    numero = pd.to_numeric(valor, errors="coerce")
    return f"{numero:.6f}" if pd.notna(numero) else "—"


def _crear_tablas(resultados: pd.DataFrame) -> tuple[str, list[int]]:
    tamanos_disponibles = [
        n
        for n in _TAMANOS_RESUMEN
        if (pd.to_numeric(resultados["N"], errors="coerce") == n).any()
    ]
    secciones: list[str] = []

    for n in tamanos_disponibles:
        tabla = resultados.loc[
            pd.to_numeric(resultados["N"], errors="coerce") == n
        ].copy()
        filas: list[dict[str, str]] = []
        for _, fila in tabla.iterrows():
            estado = str(fila.get("Estado", "medido"))
            promedio = fila.get("Tiempo_Promedio_s")
            desviacion = fila.get(
                "Desviacion_Muestral_s",
                fila.get("Desviacion_Estandar_s"),
            )
            if estado == "no medido" or str(promedio) == "no medido":
                tiempo = "no medido"
                estado = "no medido"
            elif str(promedio) == "no aplica":
                tiempo = "no aplica"
            else:
                tiempo = (
                    f"{_formatear_numero(promedio)} ± "
                    f"{_formatear_numero(desviacion)}"
                )
            valor_m = pd.to_numeric(fila.get("M"), errors="coerce")
            filas.append(
                {
                    "Experimento": str(fila.get("Experimento", "")),
                    "Modo": str(fila.get("Modo", "")),
                    "Estructura": str(fila.get("Estructura", "")),
                    "M": f"{int(valor_m):,}" if pd.notna(valor_m) else "—",
                    "Tiempo (s), media ± desviación": tiempo,
                    "Estado": estado,
                }
            )

        tabla_formateada = pd.DataFrame(filas, columns=_COLUMNAS_TABLA)
        secciones.extend(
            [
                f"## N = {n:,}",
                "",
                _markdown_table(tabla_formateada),
                "",
            ]
        )

    if not secciones:
        return (
            "No hay resultados para N = 10.000, 100.000 o 1.000.000.\n",
            [],
        )
    return "\n".join(secciones), tamanos_disponibles


def _imprimir_tablas(resultados: pd.DataFrame, ruta_tabla: Path) -> None:
    contenido, tamanos_disponibles = _crear_tablas(resultados)
    ruta_tabla.write_text(
        "# Resultados del benchmark\n\n"
        "Los tiempos están expresados en segundos como media ± desviación "
        "estándar muestral.\n\n"
        + contenido,
        encoding="utf-8",
    )
    print(contenido)
    print(f"Tabla guardada en: {ruta_tabla}")
    if not tamanos_disponibles:
        print("Aviso: el resumen no contiene ninguno de los tamaños solicitados.")


def _avisar_no_medidas(resultados: pd.DataFrame) -> None:
    if "Estado" not in resultados.columns:
        return
    no_medidas = resultados.loc[resultados["Estado"] == "no medido"]
    if no_medidas.empty:
        print("No hay configuraciones marcadas como «no medido».")
        return

    print(
        f"Aviso: {len(no_medidas)} configuraciones aparecen como «no medido»."
    )
    columnas = [
        columna
        for columna in (
            "Experimento",
            "N",
            "Modo",
            "Estructura",
            "M",
            "Orden_BPlus",
            "Detalle",
        )
        if columna in no_medidas.columns
    ]
    print(no_medidas.loc[:, columnas].drop_duplicates().to_string(index=False))


def _leer_resumen(ruta_csv: Path) -> pd.DataFrame:
    if not ruta_csv.is_file():
        raise FileNotFoundError(
            f"No se encontró el resumen del benchmark para generar gráficas: {ruta_csv}"
        )
    return pd.read_csv(ruta_csv)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de estructuras de datos.")
    parser.add_argument(
        "--rapido",
        action="store_true",
        help="Ejecuta una prueba corta con N pequeño y K=2.",
    )
    parser.add_argument(
        "--solo-graficas",
        action="store_true",
        help="Genera las gráficas usando el CSV de resumen existente, sin medir.",
    )
    parser.add_argument(
        "--reanudar",
        action="store_true",
        help=(
            "Reanuda desde resultados/resultados_benchmark.csv y omite las "
            "combinaciones que ya estén medidas."
        ),
    )
    argumentos = parser.parse_args()

    inicio = time.perf_counter()
    raiz_proyecto = Path(__file__).resolve().parent
    carpeta_resultados = raiz_proyecto / "resultados"
    carpeta_graficas = raiz_proyecto / "graficas"
    ruta_csv = carpeta_resultados / "resultados_benchmark.csv"
    ruta_tabla = carpeta_resultados / "tabla_N.md"

    carpeta_resultados.mkdir(parents=True, exist_ok=True)
    carpeta_graficas.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("EXPERIMENTO DE RENDIMIENTO DE ESTRUCTURAS DE DATOS")
    if argumentos.solo_graficas:
        resultados = _leer_resumen(ruta_csv)
    else:
        print("Inicio del benchmark algorítmico y generación de visualizaciones")
        resultados = ejecutar_benchmark_completo(
            rapido=argumentos.rapido,
            reanudar=argumentos.reanudar,
        )

    archivos_graficos = generar_todas_las_graficas(
        ruta_csv=ruta_csv,
        carpeta_salida=carpeta_graficas,
    )

    _imprimir_tablas(resultados, ruta_tabla)
    _avisar_no_medidas(resultados)
    if not argumentos.solo_graficas:
        print(f"\nArchivo CSV guardado en: {ruta_csv}")
        print(f"Resultados crudos: {carpeta_resultados / 'resultados_crudos.csv'}")
        print(f"Ficha de hardware/software: {carpeta_resultados / 'ficha.json'}")
    print("Archivos PNG guardados:")
    for archivo in archivos_graficos:
        print(f"  - {archivo}")
    print(f"Tiempo transcurrido: {time.perf_counter() - inicio:.3f} s")


if __name__ == "__main__":
    main()
