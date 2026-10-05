from __future__ import annotations

import gc
import random
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from pathlib import Path
from statistics import mean, pstdev
from typing import Generator, Protocol

import numpy as np
import pandas as pd

from .structures import ABB, ArbolBPlus, Estudiante, ListaEnlazada


TAMANIOS_N: tuple[int, ...] = (1000, 2500, 5000, 7500, 10000)
CANTIDADES_Q: tuple[int, ...] = (10, 100, 1000, 10000)
ITERACIONES_K = 5
ORDEN_BPLUS = 16
SEMILLA_BENCHMARK = 2026


class _Estructura(Protocol):
    def insertar(self, registro: Estudiante) -> None: ...

    def buscar(self, target_id: int) -> Estudiante | None: ...


_NOMBRES_ESTRUCTURAS: tuple[str, ...] = (
    "ListaEnlazada",
    "ABB",
    "ArbolBPlus",
)


@contextmanager
def _gc_desactivado() -> Generator[None, None, None]:
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def _medir_bloque(operacion: Callable[[], None]) -> float:
    with _gc_desactivado():
        inicio = time.perf_counter()
        operacion()
        fin = time.perf_counter()
    return (fin - inicio) * 1_000_000


def filtrar_outliers_iqr(datos: Iterable[float]) -> list[float]:
    valores = np.asarray(list(datos), dtype=float)
    if valores.ndim != 1:
        raise ValueError("Los datos deben ser una secuencia unidimensional.")
    if not np.isfinite(valores).all():
        raise ValueError("Los datos deben contener únicamente valores finitos.")
    if valores.size == 0:
        return []

    q1, q3 = np.percentile(valores, [25, 75])
    rango_intercuartilico = q3 - q1
    limite_inferior = q1 - 1.5 * rango_intercuartilico
    limite_superior = q3 + 1.5 * rango_intercuartilico
    return [
        float(valor)
        for valor in valores
        if limite_inferior <= valor <= limite_superior
    ]


def _crear_estructura(nombre: str) -> _Estructura:
    if nombre == "ListaEnlazada":
        return ListaEnlazada()
    if nombre == "ABB":
        return ABB()
    if nombre == "ArbolBPlus":
        return ArbolBPlus(M=ORDEN_BPLUS)
    raise ValueError(f"Estructura no reconocida: {nombre!r}.")


def _resumir_tiempos(tiempos_us: list[float]) -> dict[str, float | int]:
    tiempos_filtrados = filtrar_outliers_iqr(tiempos_us)
    if not tiempos_filtrados:
        raise RuntimeError("El filtrado IQR descartó todas las mediciones.")

    desviacion = pstdev(tiempos_filtrados) if len(tiempos_filtrados) > 1 else 0.0
    return {
        "Tiempo_Promedio_us": mean(tiempos_filtrados),
        "Desviacion_Estandar_us": desviacion,
        "Repeticiones": len(tiempos_us),
        "Repeticiones_Validas": len(tiempos_filtrados),
    }


def _crear_registros(identificadores: list[int]) -> list[Estudiante]:
    return [
        Estudiante(
            id=identificador,
            nombre=f"Estudiante {identificador}",
            edad=18 + identificador % 11,
            promedio=round(3.0 + (identificador % 21) / 10, 1),
        )
        for identificador in identificadores
    ]


def _medir_insercion(
    nombre_estructura: str,
    registros: list[Estudiante],
) -> tuple[list[float], _Estructura]:
    tiempos_us: list[float] = []
    ultima_estructura: _Estructura | None = None

    for _ in range(ITERACIONES_K):
        estructura = _crear_estructura(nombre_estructura)

        def insertar_todos() -> None:
            for registro in registros:
                estructura.insertar(registro)

        tiempos_us.append(_medir_bloque(insertar_todos))
        ultima_estructura = estructura

    if ultima_estructura is None:
        raise RuntimeError("No se realizaron repeticiones de inserción.")
    return tiempos_us, ultima_estructura


def _medir_busqueda(
    estructura: _Estructura,
    identificadores: list[int],
    cantidad_consultas: int,
    generador: random.Random,
) -> list[float]:
    tiempos_us: list[float] = []
    for _ in range(ITERACIONES_K):
        consultas = [
            generador.choice(identificadores)
            for _ in range(cantidad_consultas)
        ]

        def buscar_todos() -> None:
            for identificador in consultas:
                estructura.buscar(identificador)

        tiempos_us.append(_medir_bloque(buscar_todos))
    return tiempos_us


def ejecutar_benchmark_completo() -> pd.DataFrame:
    generador = random.Random(SEMILLA_BENCHMARK)
    resultados: list[dict[str, str | int | float | None]] = []

    for n in TAMANIOS_N:
        identificadores_aleatorios = list(range(1, n + 1))
        generador.shuffle(identificadores_aleatorios)
        escenarios = (
            ("IDs Aleatorios", identificadores_aleatorios),
            ("IDs Ordenados", list(range(1, n + 1))),
        )

        for modo, identificadores in escenarios:
            registros = _crear_registros(identificadores)

            for nombre_estructura in _NOMBRES_ESTRUCTURAS:
                tiempos_insercion, estructura = _medir_insercion(
                    nombre_estructura,
                    registros,
                )
                resultados.append(
                    {
                        "Experimento": "Insercion",
                        "N": n,
                        "Modo": modo,
                        "Estructura": nombre_estructura,
                        "Q": None,
                        **_resumir_tiempos(tiempos_insercion),
                    }
                )

                for cantidad_consultas in CANTIDADES_Q:
                    tiempos_busqueda = _medir_busqueda(
                        estructura,
                        identificadores,
                        cantidad_consultas,
                        generador,
                    )
                    resultados.append(
                        {
                            "Experimento": "Busqueda",
                            "N": n,
                            "Modo": modo,
                            "Estructura": nombre_estructura,
                            "Q": cantidad_consultas,
                            **_resumir_tiempos(tiempos_busqueda),
                        }
                    )

    dataframe = pd.DataFrame(resultados)
    ruta_salida = (
        Path(__file__).resolve().parent.parent
        / "resultados"
        / "resultados_benchmark.csv"
    )
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(ruta_salida, index=False, encoding="utf-8")
    return dataframe