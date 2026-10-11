from __future__ import annotations

import gc
import importlib.metadata
import multiprocessing
import json
import os
import platform
import random
import statistics
import sys
import time
import tracemalloc
import traceback
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

from .structures import ABB, ArbolBPlus, Estudiante, ListaEnlazada


TAMANIOS_N: tuple[int, ...] = (
    1_000,
    2_500,
    5_000,
    7_500,
    10_000,
    50_000,
    100_000,
    500_000,
    1_000_000,
)
CANTIDADES_M: tuple[int, ...] = (10, 100, 1_000, 10_000)
ORDENES_BPLUS: tuple[int, ...] = (4, 16, 64)
N_RAPIDO: tuple[int, ...] = (100,)
M_RAPIDO: tuple[int, ...] = (10,)
ORDEN_BPLUS = 16
SEMILLA_BENCHMARK = 2026
VENTANA_MINIMA_S = 1.0
PRESUPUESTO_CONFIGURACION_S = 300.0
TIMEOUT_CONFIGURACION_S = 600.0
_NOMBRES_ESTRUCTURAS = ("ListaEnlazada", "ABB", "ArbolBPlus")
_COLUMNAS_CRUDAS = (
    "Experimento",
    "N",
    "Modo",
    "Estructura",
    "M",
    "Orden_BPlus",
    "K",
    "Repeticion",
    "Estado",
    "Tiempo_s",
    "Ventana_real_s",
    "Repeticiones_ventana",
    "Memoria_Peak_bytes",
    "Altura_niveles",
    "Detalle",
)
_VALORES_T_TAIL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
}


class _Estructura(Protocol):
    def insertar(self, registro: Estudiante) -> None: ...

    def buscar(self, target_id: int) -> Estudiante | None: ...

    def listar(self) -> list[Estudiante]: ...

    def altura(self) -> int: ...


class _PresupuestoExcedido(RuntimeError):
    pass


def _repeticiones(
    n: int,
    rapido: bool,
    nombre: str | None = None,
    modo: str | None = None,
) -> int:
    if rapido:
        return 2
    if nombre == "ABB" and modo == "IDs Ordenados" and n == 100_000:
        return 3
    if n <= 10_000:
        return 10
    if n <= 100_000:
        return 5
    return 3


def _crear_estructura(nombre: str, orden_bplus: int = ORDEN_BPLUS) -> _Estructura:
    if nombre == "ListaEnlazada":
        return ListaEnlazada()
    if nombre == "ABB":
        return ABB()
    if nombre == "ArbolBPlus":
        return ArbolBPlus(orden=orden_bplus)
    raise ValueError(f"Estructura no reconocida: {nombre!r}.")


def _crear_registros(identificadores: Iterable[int]) -> list[Estudiante]:
    return [
        Estudiante(
            id=identificador,
            nombre=f"Estudiante {identificador}",
            edad=18 + identificador % 11,
            promedio=round(3.0 + (identificador % 21) / 10, 1),
        )
        for identificador in identificadores
    ]


def _construir(
    nombre: str,
    registros: list[Estudiante],
    orden_bplus: int,
) -> _Estructura:
    estructura = _crear_estructura(nombre, orden_bplus)
    for registro in registros:
        estructura.insertar(registro)
    return estructura


def _validar_estructura(
    estructura: _Estructura,
    identificadores: list[int],
    consultas: list[int],
) -> None:
    esperados = sorted(identificadores)
    encontrados = estructura.listar()
    ids_listados = [registro.id for registro in encontrados]
    if ids_listados != esperados:
        raise AssertionError("listar() no devolvió todos los IDs en orden.")

    # Verifica todo el lote de consultas de manera acotada; listar() ya confirma
    # que la colección completa contiene los N IDs, sin forzar O(N²) en la lista.
    for identificador in consultas[: min(1_000, len(consultas))]:
        registro = estructura.buscar(identificador)
        if registro is None or registro.id != identificador:
            raise AssertionError(f"No se encontró el ID {identificador}.")
    limite_faltantes = 10 if isinstance(estructura, ListaEnlazada) else 1_000
    for identificador in range(
        len(identificadores) + 1,
        len(identificadores) + limite_faltantes + 1,
    ):
        if estructura.buscar(identificador) is not None:
            raise AssertionError(f"Se encontró inesperadamente el ID {identificador}.")

    id_min = max(1, int(len(identificadores) * 0.4))
    id_max = max(id_min, int(len(identificadores) * 0.6))
    rango_esperado = [
        identificador
        for identificador in esperados
        if id_min <= identificador <= id_max
    ]
    if isinstance(estructura, ArbolBPlus):
        rango_obtenido = [registro.id for registro in estructura.rango(id_min, id_max)]
    elif isinstance(estructura, ListaEnlazada):
        rango_obtenido = sorted(
            registro.id
            for registro in _buscar_rango_completo(estructura, id_min, id_max)
        )
    else:
        rango_obtenido = [
            registro.id
            for registro in _buscar_rango_completo(estructura, id_min, id_max)
        ]
    if rango_obtenido != rango_esperado:
        raise AssertionError("El recorrido de rango no devolvió los IDs esperados.")
    if estructura.altura() < 1:
        raise AssertionError("La altura debe ser positiva para una estructura no vacía.")


def _medir_ventana(
    operacion: Callable[[], Any],
    ventana_minima_s: float = VENTANA_MINIMA_S,
    presupuesto_s: float = PRESUPUESTO_CONFIGURACION_S,
) -> tuple[float, float, int]:
    gc_estaba_habilitado = gc.isenabled()
    gc.disable()
    try:
        inicio = time.perf_counter()
        repeticiones = 0
        while True:
            operacion()
            repeticiones += 1
            ventana_real_s = time.perf_counter() - inicio
            if ventana_real_s >= presupuesto_s:
                raise _PresupuestoExcedido(
                    f"La ventana superó {presupuesto_s:.0f} segundos."
                )
            if ventana_real_s >= ventana_minima_s:
                return ventana_real_s / repeticiones, ventana_real_s, repeticiones
    finally:
        if gc_estaba_habilitado:
            gc.enable()
        else:
            gc.disable()


def _crear_fila(
    *,
    experimento: str,
    n: int,
    modo: str,
    estructura: str,
    m: int | None,
    orden_bplus: int | None,
    k: int,
    repeticion: int | None,
    estado: str,
    tiempo_s: float | str | None = None,
    ventana_real_s: float | str | None = None,
    repeticiones_ventana: int | None = None,
    memoria_peak_bytes: int | None = None,
    altura_niveles: int | None = None,
    detalle: str | None = None,
) -> dict[str, Any]:
    return {
        "Experimento": experimento,
        "N": n,
        "Modo": modo,
        "Estructura": estructura,
        "M": m,
        "Orden_BPlus": orden_bplus,
        "K": k,
        "Repeticion": repeticion,
        "Estado": estado,
        "Tiempo_s": tiempo_s,
        "Ventana_real_s": ventana_real_s,
        "Repeticiones_ventana": repeticiones_ventana,
        "Memoria_Peak_bytes": memoria_peak_bytes,
        "Altura_niveles": altura_niveles,
        "Detalle": detalle,
    }


def _agregar_no_medido(
    resultados: list[dict[str, Any]],
    *,
    experimento: str,
    n: int,
    modo: str,
    estructura: str,
    m: int | None,
    orden_bplus: int | None,
    k: int,
    detalle: str,
) -> None:
    resultados.append(
        _crear_fila(
            experimento=experimento,
            n=n,
            modo=modo,
            estructura=estructura,
            m=m,
            orden_bplus=orden_bplus,
            k=k,
            repeticion=None,
            estado="no medido",
            tiempo_s="no medido",
            ventana_real_s="no medido",
            detalle=detalle,
        )
    )


def es_viable(estructura: str, orden: str, N: int, M: int | None) -> bool:
    if estructura == "ABB" and orden == "IDs Ordenados" and N > 100_000:
        return False
    if estructura == "ListaEnlazada" and N >= 500_000 and M is not None and M > 1_000:
        return False
    return True


def _motivo_no_viable(
    estructura: str,
    orden: str,
    n: int,
    m: int | None,
) -> str:
    if estructura == "ABB" and orden == "IDs Ordenados" and n > 100_000:
        return "ABB con IDs ordenados se limita a N <= 100000 (K=3 en N=100000)."
    if estructura == "ListaEnlazada" and n >= 500_000 and m is not None and m > 1_000:
        return "ListaEnlazada con N >= 500000 se limita a M <= 1000."
    return "Configuración no viable."


def _memoria_viable(estructura: str, orden: str, n: int, m: int | None) -> bool:
    if not es_viable(estructura, orden, n, m):
        return False
    if n >= 500_000:
        return estructura == "ArbolBPlus" or (
            estructura == "ABB" and orden == "IDs Aleatorios"
        )
    return True


def _m_max_viable(
    estructura: str,
    orden: str,
    n: int,
    cantidades_m: tuple[int, ...],
) -> int:
    cantidades_viables = [
        m for m in cantidades_m if es_viable(estructura, orden, n, m)
    ]
    return max(cantidades_viables, default=1)


def _imprimir_configuracion(
    estructura: str,
    orden: str,
    n: int,
    m: int | None,
    inicio: float,
) -> None:
    m_texto = "—" if m is None else str(m)
    print(
        f"[{time.perf_counter() - inicio:8.1f} s] "
        f"Estructura={estructura} | Orden={orden} | N={n} | M={m_texto}",
        flush=True,
    )


def _agregar_medicion(
    resultados: list[dict[str, Any]],
    *,
    experimento: str,
    n: int,
    modo: str,
    estructura: str,
    m: int | None,
    orden_bplus: int | None,
    k: int,
    repeticion: int,
    operacion: Callable[[], Any],
    presupuesto_s: float = PRESUPUESTO_CONFIGURACION_S,
    altura_niveles: int | None = None,
) -> None:
    def misma_configuracion(fila: dict[str, Any]) -> bool:
        return (
            fila["Experimento"] == experimento
            and fila["N"] == n
            and fila["Modo"] == modo
            and fila["Estructura"] == estructura
            and fila["M"] == m
            and fila["Orden_BPlus"] == orden_bplus
        )

    if any(
        misma_configuracion(fila)
        and fila["Repeticion"] == repeticion
        for fila in resultados
    ):
        return

    mediciones_previas = [
        fila
        for fila in resultados
        if misma_configuracion(fila) and fila["Estado"] == "medido"
    ]
    timeout_previo = next(
        (
            str(fila["Detalle"])
            for fila in resultados
            if misma_configuracion(fila)
            and fila["Estado"] == "no medido"
            and fila["Detalle"]
            and "superó" in str(fila["Detalle"])
        ),
        None,
    )
    if timeout_previo:
        _agregar_no_medido(
            resultados,
            experimento=experimento,
            n=n,
            modo=modo,
            estructura=estructura,
            m=m,
            orden_bplus=orden_bplus,
            k=k,
            detalle=timeout_previo,
        )
        return

    tiempo_previo_s = sum(
        float(fila["Ventana_real_s"]) for fila in mediciones_previas
    )
    presupuesto_s = min(
        presupuesto_s,
        PRESUPUESTO_CONFIGURACION_S - tiempo_previo_s,
    )
    if presupuesto_s <= 0:
        detalle = "La configuración superó el presupuesto de cinco minutos."
        _agregar_no_medido(
            resultados,
            experimento=experimento,
            n=n,
            modo=modo,
            estructura=estructura,
            m=m,
            orden_bplus=orden_bplus,
            k=k,
            detalle=detalle,
        )
        return
    try:
        tiempo_s, ventana_real_s, repeticiones_ventana = _medir_ventana(
            operacion,
            presupuesto_s=presupuesto_s,
        )
    except _PresupuestoExcedido as error:
        _agregar_no_medido(
            resultados,
            experimento=experimento,
            n=n,
            modo=modo,
            estructura=estructura,
            m=m,
            orden_bplus=orden_bplus,
            k=k,
            detalle=str(error),
        )
        for fila in mediciones_previas:
            fila["Estado"] = "no medido"
            fila["Tiempo_s"] = "no medido"
            fila["Ventana_real_s"] = "no medido"
            fila["Repeticiones_ventana"] = None
            fila["Detalle"] = str(error)
        return
    resultados.append(
        _crear_fila(
            experimento=experimento,
            n=n,
            modo=modo,
            estructura=estructura,
            m=m,
            orden_bplus=orden_bplus,
            k=k,
            repeticion=repeticion,
            estado="medido",
            tiempo_s=tiempo_s,
            ventana_real_s=ventana_real_s,
            repeticiones_ventana=repeticiones_ventana,
            altura_niveles=altura_niveles,
        )
    )


def _medir_memoria(
    nombre: str,
    registros: list[Estudiante],
    orden_bplus: int,
) -> int:
    tracemalloc.start()
    try:
        estructura = _construir(nombre, registros, orden_bplus)
        _, memoria_peak_bytes = tracemalloc.get_traced_memory()
        del estructura
        return memoria_peak_bytes
    finally:
        tracemalloc.stop()


def _buscar_rango_completo(
    estructura: _Estructura,
    id_min: int,
    id_max: int,
) -> list[Estudiante]:
    registros = (
        list(estructura)
        if isinstance(estructura, ListaEnlazada)
        else estructura.listar()
    )
    return [
        registro
        for registro in registros
        if id_min <= registro.id <= id_max
    ]


def _medir_configuracion(
    resultados: list[dict[str, Any]],
    *,
    nombre: str,
    n: int,
    modo: str,
    registros: list[Estudiante],
    identificadores: list[int],
    consultas: list[int],
    faltantes: list[int],
    k: int,
    repeticion: int,
    orden_bplus: int,
    cantidades_m: tuple[int, ...],
    inicio_benchmark: float,
) -> None:
    m_configuracion = _m_max_viable(nombre, modo, n, cantidades_m)
    _imprimir_configuracion(nombre, modo, n, m_configuracion, inicio_benchmark)
    if not es_viable(nombre, modo, n, m_configuracion):
        exclusion_general = _motivo_no_viable(
            nombre,
            modo,
            n,
            m_configuracion,
        )
        for experimento, m in (
            [("Insercion", None)]
            + [("Busqueda", cantidad_m) for cantidad_m in cantidades_m]
            + [
                ("BusquedaInexistente", 1_000),
                ("Listar", None),
                ("Altura", None),
                ("Rango", None),
                ("Memoria", None),
            ]
        ):
            _agregar_no_medido(
                resultados,
                experimento=experimento,
                n=n,
                modo=modo,
                estructura=nombre,
                m=m,
                orden_bplus=orden_bplus if nombre == "ArbolBPlus" else None,
                k=k,
                detalle=exclusion_general,
            )
        return

    _imprimir_configuracion(nombre, modo, n, m_configuracion, inicio_benchmark)
    estructura = _construir(nombre, registros, orden_bplus)
    _validar_estructura(estructura, identificadores, consultas)

    def medir(
        experimento: str,
        operacion: Callable[[], Any],
        m: int | None = None,
        altura_niveles: int | None = None,
    ) -> None:
        m_viabilidad = m if m is not None else m_configuracion
        _imprimir_configuracion(
            nombre,
            modo,
            n,
            m if m is not None else m_configuracion,
            inicio_benchmark,
        )
        if not es_viable(nombre, modo, n, m_viabilidad):
            _agregar_no_medido(
                resultados,
                experimento=experimento,
                n=n,
                modo=modo,
                estructura=nombre,
                m=m,
                orden_bplus=orden_bplus if nombre == "ArbolBPlus" else None,
                k=k,
                detalle=_motivo_no_viable(nombre, modo, n, m_viabilidad),
            )
            return
        orden_registro = orden_bplus if nombre == "ArbolBPlus" else None
        tiempo_previo_s = sum(
            float(fila["Ventana_real_s"])
            for fila in resultados
            if fila["Estado"] == "medido"
            and fila["Experimento"] == experimento
            and fila["N"] == n
            and fila["Modo"] == modo
            and fila["Estructura"] == nombre
            and fila["M"] == m
            and fila["Orden_BPlus"] == orden_registro
        )
        presupuesto_restante_s = PRESUPUESTO_CONFIGURACION_S - tiempo_previo_s
        if presupuesto_restante_s <= 0:
            _agregar_no_medido(
                resultados,
                experimento=experimento,
                n=n,
                modo=modo,
                estructura=nombre,
                m=m,
                orden_bplus=orden_registro,
                k=k,
                detalle="La configuración superó el presupuesto de cinco minutos.",
            )
            return
        antes = len(resultados)
        _agregar_medicion(
            resultados,
            experimento=experimento,
            n=n,
            modo=modo,
            estructura=nombre,
            m=m,
            orden_bplus=orden_bplus if nombre == "ArbolBPlus" else None,
            k=k,
            repeticion=repeticion,
            operacion=operacion,
            presupuesto_s=presupuesto_restante_s,
            altura_niveles=altura_niveles,
        )
        if resultados[antes]["Estado"] == "no medido":
            detalle = str(resultados[antes]["Detalle"])
            if "superó" in detalle:
                for fila in resultados:
                    if (
                        fila["Experimento"] == experimento
                        and fila["N"] == n
                        and fila["Modo"] == modo
                        and fila["Estructura"] == nombre
                        and fila["M"] == m
                        and fila["Orden_BPlus"] == orden_registro
                        and fila["Estado"] == "medido"
                    ):
                        fila["Estado"] = "no medido"
                        fila["Tiempo_s"] = "no medido"
                        fila["Ventana_real_s"] = "no medido"
                        fila["Repeticiones_ventana"] = None
                        fila["Detalle"] = detalle

    def construir_una_vez() -> None:
        _construir(nombre, registros, orden_bplus)

    medir("Insercion", construir_una_vez)

    for cantidad_m in cantidades_m:
        consultas_m = consultas[:cantidad_m]

        def buscar_existentes() -> None:
            for identificador in consultas_m:
                estructura.buscar(identificador)

        medir("Busqueda", buscar_existentes, cantidad_m)

    def buscar_inexistentes() -> None:
        for identificador in faltantes:
            estructura.buscar(identificador)

    medir("BusquedaInexistente", buscar_inexistentes, 1_000)
    medir("Listar", estructura.listar)
    medir("Altura", estructura.altura, altura_niveles=estructura.altura())

    id_min = max(1, int(n * 0.4))
    id_max = max(id_min, int(n * 0.6))
    if isinstance(estructura, ArbolBPlus):
        medir("Rango", lambda: estructura.rango(id_min, id_max))
    else:
        medir("Rango", lambda: _buscar_rango_completo(estructura, id_min, id_max))

    if repeticion == 1:
        _imprimir_configuracion(
            nombre,
            modo,
            n,
            m_configuracion,
            inicio_benchmark,
        )
        if not _memoria_viable(nombre, modo, n, m_configuracion):
            memoria_exclusion = (
                _motivo_no_viable(nombre, modo, n, m_configuracion)
                if not es_viable(nombre, modo, n, m_configuracion)
                else "Para N >= 500000 la memoria se mide solo con B+ y ABB aleatorio."
            )
            _agregar_no_medido(
                resultados,
                experimento="Memoria",
                n=n,
                modo=modo,
                estructura=nombre,
                m=None,
                orden_bplus=orden_bplus if nombre == "ArbolBPlus" else None,
                k=k,
                detalle=memoria_exclusion,
            )
        elif not any(
            fila["Experimento"] == "Memoria"
            and fila["N"] == n
            and fila["Modo"] == modo
            and fila["Estructura"] == nombre
            and fila["Orden_BPlus"]
            == (orden_bplus if nombre == "ArbolBPlus" else None)
            for fila in resultados
        ):
            memoria_peak_bytes = _medir_memoria(nombre, registros, orden_bplus)
            resultados.append(
                _crear_fila(
                    experimento="Memoria",
                    n=n,
                    modo=modo,
                    estructura=nombre,
                    m=None,
                    orden_bplus=orden_bplus if nombre == "ArbolBPlus" else None,
                    k=k,
                    repeticion=None,
                    estado="medido",
                    memoria_peak_bytes=memoria_peak_bytes,
                    detalle="Pico tracemalloc en bytes; construcción fuera del cronómetro.",
                )
            )


def _trabajador_configuracion(
    canal: Any,
    nombre: str,
    modo: str,
    n: int,
    k: int,
    cantidades_m: tuple[int, ...],
    inicio_benchmark: float,
) -> None:
    try:
        resultados: list[dict[str, Any]] = []
        repeticiones = 1 if not es_viable(
            nombre,
            modo,
            n,
            _m_max_viable(nombre, modo, n, cantidades_m),
        ) else k
        for indice_repeticion in range(repeticiones):
            generador = random.Random(
                SEMILLA_BENCHMARK
                + n
                + (0 if modo == "IDs Aleatorios" else 1_000_003)
                + indice_repeticion
            )
            identificadores = list(range(1, n + 1))
            if modo == "IDs Aleatorios":
                generador.shuffle(identificadores)
            registros = _crear_registros(identificadores)
            consultas = [
                generador.randint(1, n)
                for _ in range(max(cantidades_m, default=1))
            ]
            faltantes = list(range(n + 1, n + 1_001))
            _medir_configuracion(
                resultados,
                nombre=nombre,
                n=n,
                modo=modo,
                registros=registros,
                identificadores=identificadores,
                consultas=consultas,
                faltantes=faltantes,
                k=k,
                repeticion=indice_repeticion + 1,
                orden_bplus=ORDEN_BPLUS,
                cantidades_m=cantidades_m,
                inicio_benchmark=inicio_benchmark,
            )
        canal.send(("ok", resultados))
    except Exception:
        canal.send(("error", traceback.format_exc()))


def _ejecutar_configuracion_con_timeout(
    nombre: str,
    modo: str,
    n: int,
    k: int,
    cantidades_m: tuple[int, ...],
    inicio_benchmark: float,
) -> list[dict[str, Any]] | None:
    contexto = multiprocessing.get_context("spawn")
    canal_receptor, canal_emisor = contexto.Pipe(duplex=False)
    proceso = contexto.Process(
        target=_trabajador_configuracion,
        args=(canal_emisor, nombre, modo, n, k, cantidades_m, inicio_benchmark),
    )
    proceso.start()
    canal_emisor.close()
    if not canal_receptor.poll(TIMEOUT_CONFIGURACION_S):
        proceso.terminate()
        proceso.join()
        canal_receptor.close()
        return None
    try:
        estado, contenido = canal_receptor.recv()
    except (EOFError, OSError) as error:
        proceso.join()
        canal_receptor.close()
        raise RuntimeError(
            f"El proceso de benchmark terminó sin resultados para "
            f"{nombre}, {modo}, N={n}."
        ) from error
    proceso.join()
    canal_receptor.close()
    if proceso.exitcode != 0:
        raise RuntimeError(
            f"El proceso de benchmark falló para {nombre}, {modo}, N={n} "
            f"(código {proceso.exitcode})."
        )
    if estado == "error":
        raise RuntimeError(contenido)
    return contenido


def _agregar_configuracion_no_medida(
    resultados: list[dict[str, Any]],
    *,
    nombre: str,
    modo: str,
    n: int,
    k: int,
    cantidades_m: tuple[int, ...],
    detalle_timeout: str | None = None,
) -> None:
    m_configuracion = _m_max_viable(nombre, modo, n, cantidades_m)
    mediciones = (
        ("Insercion", None, m_configuracion),
        *(("Busqueda", m, m) for m in cantidades_m),
        ("BusquedaInexistente", 1_000, 1_000),
        ("Listar", None, m_configuracion),
        ("Altura", None, m_configuracion),
        ("Rango", None, m_configuracion),
        ("Memoria", None, m_configuracion),
    )
    for experimento, m_fila, m_viabilidad in mediciones:
        orden_bplus = ORDEN_BPLUS if nombre == "ArbolBPlus" else None
        viable = es_viable(nombre, modo, n, m_viabilidad)
        if experimento == "Memoria":
            viable = _memoria_viable(nombre, modo, n, m_viabilidad)
        if viable:
            detalle = detalle_timeout or "La configuración superó 600 segundos."
        elif experimento == "Memoria" and es_viable(
            nombre,
            modo,
            n,
            m_viabilidad,
        ):
            detalle = "Para N >= 500000 la memoria se mide solo con B+ y ABB aleatorio."
        else:
            detalle = _motivo_no_viable(nombre, modo, n, m_viabilidad)
        _agregar_no_medido(
            resultados,
            experimento=experimento,
            n=n,
            modo=modo,
            estructura=nombre,
            m=m_fila,
            orden_bplus=orden_bplus,
            k=k,
            detalle=detalle,
        )


def _trabajador_barrido_configuracion(
    canal: Any,
    canal_receptor_copia: Any,
    modo: str,
    orden_bplus: int,
    k: int,
    cantidades_m: tuple[int, ...],
    semilla: int,
    inicio_benchmark: float,
) -> None:
    try:
        resultados = list(canal_receptor_copia)
        longitud_inicial = len(resultados)
        generador = random.Random(semilla)
        n = 100_000
        faltantes = list(range(n + 1, n + 1_001))
        m_configuracion = max(cantidades_m, default=1)
        for repeticion in range(k):
            identificadores = list(range(1, n + 1))
            if modo == "IDs Aleatorios":
                generador.shuffle(identificadores)
            registros = _crear_registros(identificadores)
            consultas = [
                generador.randint(1, n)
                for _ in range(max(cantidades_m, default=1))
            ]
            estructura = _construir("ArbolBPlus", registros, orden_bplus)
            _validar_estructura(estructura, identificadores, consultas)
            numero_repeticion = k + repeticion + 1

            def insertar_todos() -> None:
                _construir("ArbolBPlus", registros, orden_bplus)

            _imprimir_configuracion(
                "ArbolBPlus",
                modo,
                n,
                m_configuracion,
                inicio_benchmark,
            )
            _agregar_medicion(
                resultados,
                experimento="Insercion",
                n=n,
                modo=modo,
                estructura="ArbolBPlus",
                m=None,
                orden_bplus=orden_bplus,
                k=k,
                repeticion=numero_repeticion,
                operacion=insertar_todos,
            )
            for cantidad_m in cantidades_m:
                consultas_m = consultas[:cantidad_m]

                def buscar_todos() -> None:
                    for identificador in consultas_m:
                        estructura.buscar(identificador)

                _imprimir_configuracion(
                    "ArbolBPlus",
                    modo,
                    n,
                    cantidad_m,
                    inicio_benchmark,
                )
                _agregar_medicion(
                    resultados,
                    experimento="Busqueda",
                    n=n,
                    modo=modo,
                    estructura="ArbolBPlus",
                    m=cantidad_m,
                    orden_bplus=orden_bplus,
                    k=k,
                    repeticion=numero_repeticion,
                    operacion=buscar_todos,
                )
            for experimento, operacion, m in (
                (
                    "BusquedaInexistente",
                    lambda: [estructura.buscar(identificador) for identificador in faltantes],
                    1_000,
                ),
                ("Listar", estructura.listar, None),
                ("Altura", estructura.altura, None),
                (
                    "Rango",
                    lambda: estructura.rango(int(n * 0.4), int(n * 0.6)),
                    None,
                ),
            ):
                _imprimir_configuracion(
                    "ArbolBPlus",
                    modo,
                    n,
                    m if m is not None else m_configuracion,
                    inicio_benchmark,
                )
                _agregar_medicion(
                    resultados,
                    experimento=experimento,
                    n=n,
                    modo=modo,
                    estructura="ArbolBPlus",
                    m=m,
                    orden_bplus=orden_bplus,
                    k=k,
                    repeticion=numero_repeticion,
                    operacion=operacion,
                    altura_niveles=(
                        estructura.altura() if experimento == "Altura" else None
                    ),
                )
        memoria_existente = any(
            fila["Experimento"] == "Memoria"
            and fila["N"] == n
            and fila["Modo"] == modo
            and fila["Estructura"] == "ArbolBPlus"
            and fila["Orden_BPlus"] == orden_bplus
            for fila in resultados
        )
        if not memoria_existente and _memoria_viable(
            "ArbolBPlus",
            modo,
            n,
            m_configuracion,
        ):
            _imprimir_configuracion(
                "ArbolBPlus",
                modo,
                n,
                None,
                inicio_benchmark,
            )
            memoria_peak_bytes = _medir_memoria(
                "ArbolBPlus",
                registros,
                orden_bplus,
            )
            resultados.append(
                _crear_fila(
                    experimento="Memoria",
                    n=n,
                    modo=modo,
                    estructura="ArbolBPlus",
                    m=None,
                    orden_bplus=orden_bplus,
                    k=k,
                    repeticion=None,
                    estado="medido",
                    memoria_peak_bytes=memoria_peak_bytes,
                    detalle="Pico tracemalloc en bytes; construcción fuera del cronómetro.",
                )
            )
        canal.send(("ok", resultados[longitud_inicial:]))
    except Exception:
        canal.send(("error", traceback.format_exc()))


def _agregar_barrido_orden(
    resultados: list[dict[str, Any]],
    generador: random.Random,
    cantidades_m: tuple[int, ...],
    carpeta_resultados: Path | None = None,
) -> None:
    n = 100_000
    k = 2 if cantidades_m == M_RAPIDO else 5
    inicio_benchmark = time.perf_counter()
    for modo in ("IDs Aleatorios", "IDs Ordenados"):
        for orden_bplus in ORDENES_BPLUS:
            previas = [
                fila
                for fila in resultados
                if fila["N"] == n
                and fila["Modo"] == modo
                and fila["Estructura"] == "ArbolBPlus"
                and fila["Orden_BPlus"] == orden_bplus
            ]
            repeticiones_esperadas = range(k + 1, 2 * k + 1)
            mediciones_esperadas = (
                [("Insercion", None)]
                + [("Busqueda", m) for m in cantidades_m]
                + [
                    ("BusquedaInexistente", 1_000),
                    ("Listar", None),
                    ("Altura", None),
                    ("Rango", None),
                ]
            )
            completo = all(
                any(
                    fila["Experimento"] == experimento
                    and fila["M"] == m
                    and fila["Repeticion"] == numero_repeticion
                    for fila in previas
                )
                for experimento, m in mediciones_esperadas
                for numero_repeticion in repeticiones_esperadas
            ) and any(fila["Experimento"] == "Memoria" for fila in previas)
            timeout_previo = any(
                fila["Estado"] == "no medido"
                and fila["Detalle"]
                and "timeout de" in str(fila["Detalle"])
                for fila in previas
            )
            if completo or timeout_previo:
                continue

            _imprimir_configuracion(
                "ArbolBPlus",
                modo,
                n,
                max(cantidades_m, default=1),
                inicio_benchmark,
            )
            contexto = multiprocessing.get_context("spawn")
            canal_receptor, canal_emisor = contexto.Pipe(duplex=False)
            proceso = contexto.Process(
                target=_trabajador_barrido_configuracion,
                args=(
                    canal_emisor,
                    previas,
                    modo,
                    orden_bplus,
                    k,
                    cantidades_m,
                    generador.randrange(1, 2**31),
                    inicio_benchmark,
                ),
            )
            proceso.start()
            canal_emisor.close()
            if not canal_receptor.poll(TIMEOUT_CONFIGURACION_S):
                proceso.terminate()
                proceso.join()
                detalle = (
                    "La configuración superó el timeout de "
                    f"{TIMEOUT_CONFIGURACION_S:.0f} segundos; se abortó."
                )
                mediciones = (
                    [("Insercion", None)]
                    + [("Busqueda", m) for m in cantidades_m]
                    + [
                        ("BusquedaInexistente", 1_000),
                        ("Listar", None),
                        ("Altura", None),
                        ("Rango", None),
                    ]
                )
                for experimento, m in mediciones:
                    _agregar_no_medido(
                        resultados,
                        experimento=experimento,
                        n=n,
                        modo=modo,
                        estructura="ArbolBPlus",
                        m=m,
                        orden_bplus=orden_bplus,
                        k=k,
                        detalle=detalle,
                    )
                if not any(fila["Experimento"] == "Memoria" for fila in previas):
                    _agregar_no_medido(
                        resultados,
                        experimento="Memoria",
                        n=n,
                        modo=modo,
                        estructura="ArbolBPlus",
                        m=None,
                        orden_bplus=orden_bplus,
                        k=k,
                        detalle=detalle,
                    )
                canal_receptor.close()
                print(f"Timeout tras {TIMEOUT_CONFIGURACION_S:.0f} s; no medido.")
            else:
                try:
                    estado, contenido = canal_receptor.recv()
                except (EOFError, OSError) as error:
                    proceso.join()
                    canal_receptor.close()
                    raise RuntimeError(
                        f"El barrido B+ terminó sin resultados para {modo}, "
                        f"N={n}, orden={orden_bplus}."
                    ) from error
                proceso.join()
                canal_receptor.close()
                if proceso.exitcode != 0:
                    raise RuntimeError(
                        f"El barrido B+ falló para {modo}, N={n}, "
                        f"orden={orden_bplus} (código {proceso.exitcode})."
                    )
                if estado == "error":
                    raise RuntimeError(contenido)
                resultados.extend(contenido)
            if carpeta_resultados is not None:
                _guardar_resultados(resultados, carpeta_resultados)


def _identificar_atipicos(tiempos: list[float]) -> list[bool]:
    if len(tiempos) < 2:
        return [False] * len(tiempos)
    q1, q3 = np.percentile(tiempos, [25, 75])
    rango = q3 - q1
    inferior = q1 - 1.5 * rango
    superior = q3 + 1.5 * rango
    return [tiempo < inferior or tiempo > superior for tiempo in tiempos]


def _resumir(resultados_crudos: pd.DataFrame) -> pd.DataFrame:
    claves = [
        "Experimento",
        "N",
        "Modo",
        "Estructura",
        "M",
        "Orden_BPlus",
        "Estado",
        "Detalle",
    ]
    filas: list[dict[str, Any]] = []
    for valores_clave, grupo in resultados_crudos.groupby(
        claves,
        dropna=False,
        sort=False,
    ):
        fila = dict(zip(claves, valores_clave))
        medidos = grupo.loc[grupo["Estado"] == "medido"]
        tiempos = pd.to_numeric(medidos["Tiempo_s"], errors="coerce").dropna().tolist()
        memorias = pd.to_numeric(
            medidos["Memoria_Peak_bytes"],
            errors="coerce",
        ).dropna().tolist()
        alturas = pd.to_numeric(
            medidos["Altura_niveles"],
            errors="coerce",
        ).dropna().tolist()
        fila["K"] = int(grupo["K"].max())
        fila["Repeticiones"] = (
            len(memorias)
            if grupo["Experimento"].iloc[0] == "Memoria"
            else len(tiempos)
        )
        fila["Atipicos_n"] = 0
        valor_no_temporal = (
            "no aplica" if grupo["Experimento"].iloc[0] == "Memoria" else "no medido"
        )
        fila["Tiempo_Promedio_s"] = valor_no_temporal
        fila["Desviacion_Muestral_s"] = valor_no_temporal
        fila["IC95_Inferior_s"] = valor_no_temporal
        fila["IC95_Superior_s"] = valor_no_temporal
        fila["Media_sin_atipicos_s"] = valor_no_temporal
        fila["Memoria_Promedio_bytes"] = (
            statistics.mean(memorias) if memorias else None
        )
        fila["Altura_Promedio"] = statistics.mean(alturas) if alturas else None
        if tiempos:
            atipicos = _identificar_atipicos(tiempos)
            tiempos_sin_atipicos = [
                tiempo for tiempo, atipico in zip(tiempos, atipicos) if not atipico
            ]
            promedio = statistics.mean(tiempos)
            fila["Atipicos_n"] = sum(atipicos)
            fila["Tiempo_Promedio_s"] = promedio
            fila["Media_sin_atipicos_s"] = (
                statistics.mean(tiempos_sin_atipicos)
                if tiempos_sin_atipicos
                else "no disponible"
            )
            if len(tiempos) > 1:
                desviacion = statistics.stdev(tiempos)
                grados_libertad = len(tiempos) - 1
                t_critico = _VALORES_T_TAIL_95.get(grados_libertad, 1.96)
                margen = t_critico * desviacion / len(tiempos) ** 0.5
                fila["Desviacion_Muestral_s"] = desviacion
                fila["IC95_Inferior_s"] = promedio - margen
                fila["IC95_Superior_s"] = promedio + margen
            else:
                fila["Desviacion_Muestral_s"] = None
                fila["IC95_Inferior_s"] = None
                fila["IC95_Superior_s"] = None
        filas.append(fila)
    return pd.DataFrame(filas)


def _memoria_total_bytes() -> int | None:
    if os.name == "nt":
        import ctypes

        class _EstadoMemoria(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        estado = _EstadoMemoria()
        estado.dwLength = ctypes.sizeof(_EstadoMemoria)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
            return int(estado.ullTotalPhys)
        return None
    if hasattr(os, "sysconf"):
        paginas = os.sysconf("SC_PHYS_PAGES")
        tamano_pagina = os.sysconf("SC_PAGE_SIZE")
        return int(paginas * tamano_pagina)
    return None


def _ficha_hardware_software() -> dict[str, Any]:
    return {
        "cpu": (
            platform.processor()
            or os.environ.get("PROCESSOR_IDENTIFIER")
            or platform.machine()
        ),
        "nucleos_logicos": os.cpu_count(),
        "ram_total_bytes": _memoria_total_bytes(),
        "sistema_operativo": platform.platform(),
        "python": sys.version,
        "python_implementacion": platform.python_implementation(),
        "paquetes": {
            paquete: importlib.metadata.version(paquete)
            for paquete in ("numpy", "pandas", "matplotlib", "seaborn")
        },
        "semilla": SEMILLA_BENCHMARK,
        "fecha_unix": time.time(),
    }


def _segundos_estimados_minimos(
    tamanios: tuple[int, ...],
    cantidades_m: tuple[int, ...],
    rapido: bool,
) -> int:
    total = 0
    for n in tamanios:
        for modo in ("IDs Aleatorios", "IDs Ordenados"):
            for nombre in _NOMBRES_ESTRUCTURAS:
                m_configuracion = _m_max_viable(nombre, modo, n, cantidades_m)
                if not es_viable(nombre, modo, n, m_configuracion):
                    continue
                k = _repeticiones(n, rapido, nombre, modo)
                busquedas_viables = sum(
                    es_viable(nombre, modo, n, m) for m in cantidades_m
                )
                mediciones_tiempo = 1 + busquedas_viables + sum(
                    es_viable(nombre, modo, n, m_configuracion)
                    for _ in range(4)
                )
                total += k * mediciones_tiempo
                if _memoria_viable(nombre, modo, n, m_configuracion):
                    total += 1
    if not rapido:
        barrido = 2 * len(ORDENES_BPLUS)
        barrido_tiempo = 1 + sum(
            es_viable("ArbolBPlus", "IDs Aleatorios", 100_000, m)
            for m in cantidades_m
        ) + 4
        total += barrido * 5 * barrido_tiempo
        total += 2 * (len(ORDENES_BPLUS) - 1)
    return total


def _guardar_resultados(
    resultados: list[dict[str, Any]],
    carpeta_resultados: Path,
) -> pd.DataFrame:
    resultados_crudos = pd.DataFrame(resultados, columns=_COLUMNAS_CRUDAS)
    resultados_resumen = _resumir(resultados_crudos)
    resultados_crudos.to_csv(
        carpeta_resultados / "resultados_crudos.csv",
        index=False,
        encoding="utf-8",
    )
    resultados_resumen.to_csv(
        carpeta_resultados / "resultados_benchmark.csv",
        index=False,
        encoding="utf-8",
    )
    return resultados_resumen


def ejecutar_benchmark_completo(
    rapido: bool = False,
    reanudar: bool = False,
) -> pd.DataFrame:
    tamanios = N_RAPIDO if rapido else TAMANIOS_N
    cantidades_m = M_RAPIDO if rapido else CANTIDADES_M
    estimacion_s = _segundos_estimados_minimos(tamanios, cantidades_m, rapido)
    print(
        "Estimación mínima: "
        f"{estimacion_s} s ({estimacion_s / 60:.1f} min; "
        f"{estimacion_s / 3_600:.2f} h). Incluye tiempos (ventanas >= 1 s), "
        "memoria (1 s estimado por configuración), altura, listar y las "
        "exclusiones de viabilidad."
    )
    print(
        f"¿La estimación pasa de 2 horas?: {'Sí' if estimacion_s > 7_200 else 'No'}"
    )
    print(
        "Viabilidad: ABB ordenado hasta N=100000 (K=3 en ese límite); "
        "ListaEnlazada para N>=500000 solo con M<=1000; memoria para "
        "N>=500000 solo con B+ y ABB aleatorio."
    )

    inicio_benchmark = time.perf_counter()
    carpeta_resultados = Path(__file__).resolve().parent.parent / "resultados"
    carpeta_resultados.mkdir(parents=True, exist_ok=True)
    ruta_crudos = carpeta_resultados / "resultados_crudos.csv"
    resultados: list[dict[str, Any]] = []
    if reanudar and ruta_crudos.is_file():
        resultados = pd.read_csv(ruta_crudos).to_dict(orient="records")

    generador = random.Random(SEMILLA_BENCHMARK)
    tamanios_previos = {
        int(float(fila["N"]))
        for fila in resultados
        if pd.notna(fila.get("N"))
    }
    tamanios_orden = list(tamanios)
    generador.shuffle(tamanios_orden)
    for n in tamanios_orden:
        if reanudar and n in tamanios_previos:
            print(f"Reanudación: se omite N={n}; ya está guardado en el CSV.")
            continue
        modos = ["IDs Aleatorios", "IDs Ordenados"]
        generador.shuffle(modos)
        for modo in modos:
            estructuras = list(_NOMBRES_ESTRUCTURAS)
            generador.shuffle(estructuras)
            for nombre in estructuras:
                k = _repeticiones(n, rapido, nombre, modo)
                _imprimir_configuracion(
                    nombre,
                    modo,
                    n,
                    _m_max_viable(nombre, modo, n, cantidades_m),
                    inicio_benchmark,
                )
                mediciones = _ejecutar_configuracion_con_timeout(
                    nombre,
                    modo,
                    n,
                    k,
                    cantidades_m,
                    inicio_benchmark,
                )
                if mediciones is None:
                    detalle_timeout = (
                        "La configuración superó el timeout de "
                        f"{TIMEOUT_CONFIGURACION_S:.0f} segundos; se abortó."
                    )
                    _agregar_configuracion_no_medida(
                        resultados,
                        nombre=nombre,
                        modo=modo,
                        n=n,
                        k=k,
                        cantidades_m=cantidades_m,
                        detalle_timeout=detalle_timeout,
                    )
                    print(
                        f"Timeout tras {TIMEOUT_CONFIGURACION_S:.0f} s; "
                        "configuración marcada como no medida."
                    )
                else:
                    resultados.extend(mediciones)
        _guardar_resultados(resultados, carpeta_resultados)
        tamanios_previos.add(n)
        print(f"CSV parcial guardado al terminar N={n}.")

    if not rapido:
        _agregar_barrido_orden(
            resultados,
            generador,
            cantidades_m,
            carpeta_resultados,
        )
        _guardar_resultados(resultados, carpeta_resultados)
    (carpeta_resultados / "ficha.json").write_text(
        json.dumps(_ficha_hardware_software(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return _guardar_resultados(resultados, carpeta_resultados)
