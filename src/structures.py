from __future__ import annotations

import bisect
import sys
from collections.abc import Iterator, Mapping
from typing import TypeAlias


sys.setrecursionlimit(50000)


class Estudiante:
    def __init__(self, id: int, nombre: str, edad: int, promedio: float) -> None:
        self.id = id
        self.nombre = nombre
        self.edad = edad
        self.promedio = promedio

    def __lt__(self, otro: object) -> bool:
        if not isinstance(otro, Estudiante):
            return NotImplemented
        return self.id < otro.id

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Estudiante):
            return NotImplemented
        return (
            self.id == otro.id
            and self.nombre == otro.nombre
            and self.edad == otro.edad
            and self.promedio == otro.promedio
        )

    def __repr__(self) -> str:
        return (
            f"Estudiante(id={self.id!r}, nombre={self.nombre!r}, "
            f"edad={self.edad!r}, promedio={self.promedio!r})"
        )


Registro: TypeAlias = Estudiante | Mapping[str, object]


def _obtener_id(registro: Registro) -> int:
    if isinstance(registro, Estudiante):
        identificador = registro.id
    elif isinstance(registro, Mapping):
        identificador = registro.get("id")
    else:
        raise TypeError("El registro debe ser un Estudiante o un mapping con clave 'id'.")

    if not isinstance(identificador, int) or isinstance(identificador, bool):
        raise TypeError("El ID del registro debe ser un entero.")
    return identificador


class _NodoLista:
    def __init__(self, registro: Registro) -> None:
        self.registro = registro
        self.siguiente: _NodoLista | None = None


class ListaEnlazada:
    def __init__(self) -> None:
        self.cabeza: _NodoLista | None = None
        self.cola: _NodoLista | None = None
        self._longitud = 0

    def insertar(self, registro: Registro) -> None:
        _obtener_id(registro)
        nodo = _NodoLista(registro)
        if self.cola is None:
            self.cabeza = nodo
        else:
            self.cola.siguiente = nodo
        self.cola = nodo
        self._longitud += 1

    def buscar(self, target_id: int) -> Registro | None:
        if not isinstance(target_id, int) or isinstance(target_id, bool):
            raise TypeError("El ID de búsqueda debe ser un entero.")

        actual = self.cabeza
        while actual is not None:
            if _obtener_id(actual.registro) == target_id:
                return actual.registro
            actual = actual.siguiente
        return None

    def listar(self) -> list[Registro]:
        return list(self)

    def listar_ordenado(self) -> list[Registro]:
        return sorted(self, key=_obtener_id)

    def __iter__(self) -> Iterator[Registro]:
        actual = self.cabeza
        while actual is not None:
            yield actual.registro
            actual = actual.siguiente

    def __len__(self) -> int:
        return self._longitud


class _NodoABB:
    def __init__(self, registro: Registro, identificador: int) -> None:
        self.registro = registro
        self.id = identificador
        self.izq: _NodoABB | None = None
        self.der: _NodoABB | None = None


class ABB:
    def __init__(self) -> None:
        self.raiz: _NodoABB | None = None
        self._longitud = 0

    def insertar(self, registro: Registro) -> None:
        identificador = _obtener_id(registro)
        nodo = _NodoABB(registro, identificador)

        if self.raiz is None:
            self.raiz = nodo
            self._longitud += 1
            return

        actual = self.raiz
        while True:
            if identificador < actual.id:
                if actual.izq is None:
                    actual.izq = nodo
                    break
                actual = actual.izq
            else:
                if actual.der is None:
                    actual.der = nodo
                    break
                actual = actual.der
        self._longitud += 1

    def insertar_recursivo(self, registro: Registro) -> None:
        identificador = _obtener_id(registro)

        def insertar_en(nodo: _NodoABB | None) -> _NodoABB:
            if nodo is None:
                return _NodoABB(registro, identificador)
            if identificador < nodo.id:
                nodo.izq = insertar_en(nodo.izq)
            else:
                nodo.der = insertar_en(nodo.der)
            return nodo

        self.raiz = insertar_en(self.raiz)
        self._longitud += 1

    def buscar(self, target_id: int) -> Registro | None:
        if not isinstance(target_id, int) or isinstance(target_id, bool):
            raise TypeError("El ID de búsqueda debe ser un entero.")

        actual = self.raiz
        while actual is not None:
            if target_id == actual.id:
                return actual.registro
            actual = actual.izq if target_id < actual.id else actual.der
        return None

    def listar(self) -> list[Registro]:
        registros: list[Registro] = []
        pendientes: list[_NodoABB] = []
        actual = self.raiz

        while actual is not None or pendientes:
            while actual is not None:
                pendientes.append(actual)
                actual = actual.izq
            actual = pendientes.pop()
            registros.append(actual.registro)
            actual = actual.der
        return registros

    def __len__(self) -> int:
        return self._longitud


class _NodoBPlus:
    def __init__(self, hoja: bool) -> None:
        self.hoja = hoja
        self.claves: list[int] = []
        self.valores: list[Registro] = []
        self.hijos: list[_NodoBPlus] = []
        self.next: _NodoBPlus | None = None


class ArbolBPlus:
    def __init__(self, M: int = 16) -> None:
        if not isinstance(M, int) or isinstance(M, bool) or M < 3:
            raise ValueError("El orden M del árbol B+ debe ser un entero mayor o igual a 3.")
        self.M = M
        self.raiz = _NodoBPlus(hoja=True)
        self._longitud = 0

    def buscar(self, target_id: int) -> Registro | None:
        if not isinstance(target_id, int) or isinstance(target_id, bool):
            raise TypeError("El ID de búsqueda debe ser un entero.")

        nodo = self.raiz
        while not nodo.hoja:
            indice = bisect.bisect_right(nodo.claves, target_id)
            nodo = nodo.hijos[indice]

        indice = bisect.bisect_left(nodo.claves, target_id)
        if indice < len(nodo.claves) and nodo.claves[indice] == target_id:
            return nodo.valores[indice]
        return None

    def insertar(self, registro: Registro) -> None:
        identificador = _obtener_id(registro)
        max_claves = self.M - 1

        if len(self.raiz.claves) == max_claves:
            nueva_raiz = _NodoBPlus(hoja=False)
            nueva_raiz.hijos.append(self.raiz)
            self._dividir_hijo(nueva_raiz, 0)
            self.raiz = nueva_raiz

        self._insertar_no_lleno(self.raiz, identificador, registro)
        self._longitud += 1

    def _dividir_hijo(self, padre: _NodoBPlus, indice: int) -> None:
        hijo = padre.hijos[indice]
        nuevo = _NodoBPlus(hoja=hijo.hoja)
        medio = len(hijo.claves) // 2

        if hijo.hoja:
            nuevo.claves = hijo.claves[medio:]
            nuevo.valores = hijo.valores[medio:]
            hijo.claves = hijo.claves[:medio]
            hijo.valores = hijo.valores[:medio]
            nuevo.next = hijo.next
            hijo.next = nuevo
            padre.claves.insert(indice, nuevo.claves[0])
        else:
            separador = hijo.claves[medio]
            nuevo.claves = hijo.claves[medio + 1:]
            nuevo.hijos = hijo.hijos[medio + 1:]
            hijo.claves = hijo.claves[:medio]
            hijo.hijos = hijo.hijos[:medio + 1]
            padre.claves.insert(indice, separador)

        padre.hijos.insert(indice + 1, nuevo)

    def _insertar_no_lleno(
        self,
        nodo: _NodoBPlus,
        identificador: int,
        registro: Registro,
    ) -> None:
        if nodo.hoja:
            indice = bisect.bisect_right(nodo.claves, identificador)
            nodo.claves.insert(indice, identificador)
            nodo.valores.insert(indice, registro)
            return

        indice = bisect.bisect_right(nodo.claves, identificador)
        hijo = nodo.hijos[indice]
        if len(hijo.claves) == self.M - 1:
            self._dividir_hijo(nodo, indice)
            if identificador >= nodo.claves[indice]:
                indice += 1
        self._insertar_no_lleno(nodo.hijos[indice], identificador, registro)

    def listar(self) -> list[Registro]:
        nodo = self.raiz
        while not nodo.hoja:
            nodo = nodo.hijos[0]

        registros: list[Registro] = []
        while nodo is not None:
            registros.extend(nodo.valores)
            nodo = nodo.next
        return registros

    def __len__(self) -> int:
        return self._longitud