from importlib import import_module

from .structures import ABB, ArbolBPlus, Estudiante, ListaEnlazada

__all__ = [
    "Estudiante",
    "ListaEnlazada",
    "ABB",
    "ArbolBPlus",
    "ejecutar_benchmark_completo",
    "generar_todas_las_graficas",
]


def __getattr__(nombre: str) -> object:
    if nombre == "ejecutar_benchmark_completo":
        return getattr(import_module(".benchmark", __name__), nombre)
    if nombre == "generar_todas_las_graficas":
        return getattr(import_module(".plots", __name__), nombre)
    raise AttributeError(f"el módulo {__name__!r} no tiene el atributo {nombre!r}")