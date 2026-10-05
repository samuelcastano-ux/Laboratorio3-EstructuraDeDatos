# Laboratorio 3: Sistema de Búsqueda y Estudio de Escalabilidad Experimental

## 1. Resumen y objetivos

Este laboratorio compara el rendimiento de tres estructuras de datos implementadas
en Python para almacenar y buscar registros de estudiantes:

- **Lista enlazada**, con inserción al final y búsqueda secuencial por ID.
- **Árbol binario de búsqueda (ABB)**, sin balanceo automático.
- **Árbol B+ de orden 16**, con nodos internos, hojas enlazadas y divisiones
  durante la inserción.

El experimento mide el tiempo de construcción de cada estructura y el tiempo
total de ráfagas de búsquedas. Se comparan entradas de distintos tamaños y dos
órdenes de inserción: IDs permutados aleatoriamente y IDs ordenados de forma
ascendente. Las búsquedas consultan IDs aleatorios existentes, con reemplazo.

Los objetivos son:

1. Observar cómo crecen los tiempos al aumentar el número de registros \(N\).
2. Contrastar el efecto del orden de inserción, especialmente en el ABB
   desbalanceado.
3. Comparar el costo de búsqueda de una estructura lineal con el de árboles.
4. Producir resultados reproducibles en CSV y representaciones gráficas que
   permitan examinar las tendencias experimentales.

## 2. Metodología experimental

### Parámetros

- Tamaños: \(N \in \{1.000,\ 2.500,\ 5.000,\ 7.500,\ 10.000\}\).
- Consultas por ráfaga: \(Q \in \{10,\ 100,\ 1.000,\ 10.000\}\).
- Repeticiones por configuración: \(K = 5\).
- Orden del árbol B+: \(M = 16\).
- Semilla del generador pseudoaleatorio: 2026.
- Escenarios de construcción: IDs aleatorios (permutación uniforme de
  \(1\) a \(N\)) e IDs ordenados de \(1\) a \(N\).

Los registros de estudiantes se preparan antes de iniciar el cronómetro. Para
cada estructura y escenario, el benchmark construye una instancia nueva en
cada repetición. En búsqueda se mide el tiempo conjunto para completar \(Q\)
consultas; los IDs consultados se eligen aleatoriamente entre los registros
existentes y pueden repetirse.

La columna `Modo` identifica **el orden con que se construyó la estructura**.
No representa el orden de las consultas: estas son aleatorias en ambos modos.

### Procedimiento de medición y estadística

1. El cronómetro se consulta con `time.perf_counter()`, un reloj de alta
   resolución. Cada duración se almacena directamente en segundos en el CSV.
2. Antes de cada bloque cronometrado se desactiva explícitamente el recolector
   de basura con `gc.disable()`. Al salir del bloque, incluso si ocurre una
   excepción, se llama a `gc.enable()`.
3. La generación de registros y de consultas, así como la creación de cada
   estructura, ocurre fuera del intervalo cronometrado. Se mide la inserción
   completa o la ráfaga completa de búsquedas.
4. Cada configuración se ejecuta cinco veces. Se descartan valores fuera del
   intervalo \([Q_1 - 1{,}5\,IQR,\ Q_3 + 1{,}5\,IQR]\), donde
   \(IQR = Q_3 - Q_1\).
5. El CSV contiene el promedio (`Tiempo_Promedio_s`) y la desviación estándar
   poblacional (`Desviacion_Estandar_s`) de las repeticiones que permanecen
   tras el filtro, junto con el número de mediciones válidas.

Con \(K=5\), el filtrado IQR debe interpretarse como una defensa básica frente
a valores extremos, no como garantía de una estimación estadística precisa.
Además, el recolector se rehabilita después de cada bloque; por ello puede
actuar entre mediciones, aunque no durante el intervalo cronometrado.

### Complejidades esperadas

| Estructura | Inserción individual | Construcción de \(N\) registros | Búsqueda |
| Lista enlazada | \(O(1)\) al final | \(O(N)\) | \(O(N)\) |
| ABB balanceado / caso promedio | \(O(\log N)\) | \(O(N\log N)\) | \(O(\log N)\) |
| ABB degenerado por IDs ordenados | hasta \(O(N)\) | \(O(N^2)\) | hasta \(O(N)\) |
| Árbol B+ de orden fijo \(M=16\) | \(O(\log_M N)\) | \(O(N\log_M N)\) | \(O(\log_M N)\) |

El ABB no realiza balanceo automático. Con inserciones ascendentes se convierte
en una cadena; por tanto, su búsqueda e inserción pueden degradarse a tiempo
lineal por operación. La lista mantiene inserción al final constante, pero cada
búsqueda recorre secuencialmente los nodos. El B+ conserva un índice
multinivel y enlaza sus hojas para el recorrido ordenado.

## 3. Tabla de resultados representativos para \(N=10.000\)

Los tiempos de inserción corresponden a construir la estructura completa. Los
tiempos de búsqueda corresponden al total de una ráfaga de \(Q=1.000\)
consultas aleatorias. Se expresan como promedio ± desviación estándar simulados
en segundos.

| Orden de inserción | Estructura | Inserción completa (s) | Búsqueda, Q = 1.000 (s) |
| --- | --- | ---: | ---: |
| Aleatorio | Lista enlazada | 0,0058 ± 0,0003 | 1,840 ± 0,095 |
| Aleatorio | ABB | 0,0126 ± 0,0009 | 0,00125 ± 0,00010 |
| Aleatorio | Árbol B+ | 0,0208 ± 0,0011 | 0,00082 ± 0,00006 |
| Ordenado | Lista enlazada | 0,0057 ± 0,0004 | 1,820 ± 0,110 |
| Ordenado | ABB | 2,180 ± 0,075 | 1,290 ± 0,044 |
| Ordenado | Árbol B+ | 0,0195 ± 0,0010 | 0,00084 ± 0,00005 |

Las cifras ilustran el comportamiento relativo esperado: el orden ascendente
penaliza severamente al ABB, mientras que no convierte el B+ en una estructura
lineal. La lista conserva una búsqueda costosa en ambos escenarios. Las
constantes exactas dependen del hardware, el intérprete, la carga del equipo y
la implementación.

## 4. Análisis gráfico

La función `generar_todas_las_graficas()` lee
`resultados/resultados_benchmark.csv`, grafica directamente los tiempos
almacenados en segundos y guarda imágenes PNG a 300 DPI
en `graficas/`.

### Matriz comparativa 2 × 2

El archivo `graficas/matriz_comparativa.png` presenta:

1. **Inserción aleatoria frente a \(N\):** permite comparar el costo de
   construir las estructuras cuando el ABB recibe una permutación aleatoria.
   Su altura suele ser mucho menor que en el peor caso, aunque no tiene
   garantía de balance.
2. **Inserción ordenada frente a \(N\):** el crecimiento pronunciado del ABB
   muestra su degradación al formar una cadena. La anotación destaca esta
   tendencia; lista y B+ permiten contrastar sus costos de construcción.
3. **Búsqueda aleatoria frente a \(N\):** compara ráfagas de \(Q=1.000\)
   búsquedas sobre estructuras construidas con IDs aleatorios.
4. **Búsqueda ordenada frente a \(N\):** utiliza consultas aleatorias sobre
   estructuras construidas con IDs ordenados. La búsqueda del ABB es lenta
   porque conserva la forma degenerada creada durante la inserción.

Las gráficas de búsqueda de la matriz fijan \(Q=1.000\) para mantener
comparable el volumen de consultas entre tamaños. Un crecimiento visual debe
interpretarse teniendo en cuenta que cada punto representa el tiempo total de
la ráfaga, no una sola búsqueda.

### Gráfico semilogarítmico

`graficas/semilog_busquedas.png` muestra la búsqueda aleatoria con \(Q=1.000\):
el eje \(X\) (tamaño \(N\)) es lineal y el eje \(Y\) (tiempo total en s) es
logarítmico. La escala vertical ayuda a visualizar simultáneamente las
estructuras rápidas, como el B+, y el costo lineal de la lista. Como este
gráfico selecciona estructuras construidas con IDs aleatorios, el ABB refleja
ese escenario y no el caso degenerado por inserción ordenada. Una separación
vertical entre curvas representa una diferencia multiplicativa de tiempos.

### Gráfico log-log de inserción ordenada

`graficas/loglog_insercion.png` representa la inserción completa de IDs
ordenados con ambos ejes en escala logarítmica base 10. En una relación
aproximada \(T(N)=cN^m\), la pendiente de la curva en coordenadas log-log es
\(m\). La referencia teórica indicada en el gráfico es:

- **ABB degenerado:** \(T(N)=O(N^2)\), por lo que se espera una pendiente
  aproximada \(m \approx 2\).
- **Lista enlazada:** \(N\) inserciones al final cuestan \(O(N)\) en conjunto;
  se espera \(m \approx 1\).
- **Árbol B+:** con orden fijo, la construcción es \(O(N\log_M N)\). En el
  rango experimental puede parecer cercana a lineal, pero no es estrictamente
  \(O(N)\); la anotación \(m \approx 1\) es una referencia visual de corto
  rango, no una cota asintótica exacta.

La pendiente observada en cinco tamaños finitos no prueba por sí sola una
complejidad. Debe interpretarse junto con el algoritmo, la variabilidad entre
corridas y los valores reales del CSV.

## 5. Respuestas a preguntas clave

### ¿Cuándo el ABB deja de comportarse como \(O(\log N)\)?

El ABB implementado no se autoequilibra. Puede presentar búsqueda promedio
cercana a \(O(\log N)\) si sus inserciones producen una forma razonablemente
equilibrada; esto es una expectativa del caso promedio, no una garantía. Si se
insertan IDs ya ordenados, cada nuevo nodo queda sucesivamente a la derecha
del anterior. La altura puede llegar a \(h=N-1\), y tanto la inserción como la
búsqueda pasan a tener costo \(O(N)\). Construir el árbol completo en ese orden
requiere \(O(N^2)\).

### ¿Qué relación hay entre la altura \(h\) y el tiempo de búsqueda?

En el ABB, una búsqueda sigue como máximo un camino desde la raíz hasta un
nodo o una hoja ausente. Su costo es \(O(h)\): un árbol equilibrado tiene
\(h=O(\log N)\), mientras que uno degenerado puede tener \(h=O(N)\). En la
lista enlazada, la búsqueda puede recorrer hasta \(N\) nodos. En el B+, la
altura es aproximadamente logarítmica en base al orden del árbol, y la
búsqueda desciende por nodos internos hasta una hoja.

### ¿Cuál es el impacto del costo constante inicial en entradas pequeñas?

Para \(N\) pequeño, costos constantes como crear nodos, preparar el entorno,
invocar funciones y acceder a atributos pueden representar una parte
importante del tiempo medido. Por ello una estructura con mejor crecimiento
asintótico no necesariamente gana en todos los tamaños pequeños. Al crecer
\(N\), la forma del árbol y el número de operaciones tienden a dominar. El
benchmark excluye la generación de registros y la creación de la estructura
del intervalo cronometrado, pero el costo de inserción de nodos sí forma parte
de la medición.

## 6. Reproducción en Visual Studio Code

1. Abra en VS Code la carpeta raíz del repositorio, la que contiene
   `main.py`, `requirements.txt` y `src/`.
2. Abra una terminal integrada en esa carpeta y cree un entorno virtual:

   ```powershell
   py -3.11 -m venv .venv
   ```

3. Active el entorno en PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Si la política local de ejecución no permite activar scripts, use el
   ejecutable del entorno directamente en los siguientes comandos.
4. Instale las dependencias declaradas:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

5. En VS Code, seleccione como intérprete de Python el ejecutable
   `.venv\Scripts\python.exe`.
6. Cierre cargas intensivas y ejecute desde la raíz del proyecto:

   ```powershell
   python main.py
   ```

7. Espere a que terminen todas las configuraciones. El ABB con inserción
   ordenada realiza trabajo cuadrático y puede tomar bastante más tiempo que
   los otros casos. No interrumpa la ejecución si necesita que se guarden todos
   los resultados.
8. Revise la tabla resumen que imprime la consola para \(N=10.000\), el CSV
   `resultados/resultados_benchmark.csv` y las imágenes:

   - `graficas/matriz_comparativa.png`
   - `graficas/semilog_busquedas.png`
   - `graficas/loglog_insercion.png`

Para que dos corridas sean comparables, conserve el mismo equipo, intérprete y
versiones de dependencias; registre cambios de entorno y evite ejecutar otras
tareas exigentes durante las mediciones. La semilla fija hace reproducible la
secuencia pseudoaleatoria, pero no elimina la variación causada por el sistema
operativo y la carga del hardware.
