from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.benchmark import ejecutar_benchmark_completo
from src.plots import generar_todas_las_graficas


_TAMANO_RESUMEN = 10_000
_COLUMNAS_RESUMEN = (
    "Experimento",
    "Modo",
    "Estructura",
    "Q",
    "Tiempo promedio (ms)",
    "Desviación estándar (ms)",
)


def _mostrar_resumen(resultados: pd.DataFrame) -> None:
    resumen = resultados.loc[resultados["N"] == _TAMANO_RESUMEN].copy()
    if resumen.empty:
        raise ValueError(
            f"El benchmark no produjo resultados para N = {_TAMANO_RESUMEN:,}."
        )

    resumen["Tiempo promedio (ms)"] = resumen["Tiempo_Promedio_us"] / 1000
    resumen["Desviación estándar (ms)"] = (
        resumen["Desviacion_Estandar_us"] / 1000
    )
    resumen["Q"] = resumen["Q"].apply(
        lambda cantidad: "-" if pd.isna(cantidad) else f"{int(cantidad):,}"
    )
    print(f"\nResumen de resultados para N = {_TAMANO_RESUMEN:,}")
    print(
        resumen.loc[:, _COLUMNAS_RESUMEN].to_string(
            index=False,
            formatters={
                "Tiempo promedio (ms)": "{:.3f}".format,
                "Desviación estándar (ms)": "{:.3f}".format,
            },
        )
    )


def main() -> None:
    raiz_proyecto = Path(__file__).resolve().parent
    carpeta_resultados = raiz_proyecto / "resultados"
    carpeta_graficas = raiz_proyecto / "graficas"
    ruta_csv = carpeta_resultados / "resultados_benchmark.csv"

    carpeta_resultados.mkdir(parents=True, exist_ok=True)
    carpeta_graficas.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("EXPERIMENTO DE RENDIMIENTO DE ESTRUCTURAS DE DATOS")
    print("Inicio del benchmark algorítmico y generación de visualizaciones")
    print("=" * 72)

    resultados = ejecutar_benchmark_completo()
    archivos_graficos = generar_todas_las_graficas(
        ruta_csv=ruta_csv,
        carpeta_salida=carpeta_graficas,
    )

    _mostrar_resumen(resultados)
    print(f"\nArchivo CSV guardado en: {ruta_csv}")
    print("Archivos PNG guardados:")
    for archivo in archivos_graficos:
        print(f"  - {archivo}")


if __name__ == "__main__":
    main()