# Guía de Sustentación Técnica — Laboratorio 3: Rendimiento de Estructuras de Datos

## 1. Ficha Técnica de Hardware y Entorno de Pruebas

- **Procesador (CPU):** [13th Gen Intel(R) Core(TM) i5-13420H (2.10 GHz)/NVIDIA GeForce RTX 3050 6GB Laptop GPU (6 GB)/Intel(R) UHD Graphics (128 MB)]
- **Memoria RAM:** [ 16 GB DDR4]
- **Sistema Operativo:** [Windows 11 Pro]  
- **Entorno de Ejecución:** Python 3.11+
- **Higiene Estadística:**
  - Desactivación explícita del Recolector de Basura (`gc.disable()`) durante las mediciones.
  - Temporizador de alta resolución `time.perf_counter()`.
  - Repetición de $K = 5$ ejecuciones independientes por prueba, calculando media ($\mu$) y desviación estándar ($\sigma$).

---

## 2. Matriz Comparativa de Complejidades Teóricas vs. Resultados Empíricos

| Estructura | Inserción Ordenada (Teórica) | Inserción Ordenada (Empírica, N=10,000) | Búsqueda Puntual (Teórica) | Búsqueda Q=10,000 (Empírica, N=10,000) |
| :--- | :---: | :---: | :---: | :---: |
| **Lista Enlazada** | $O(1)$ | **0.0081 s** | $O(N)$ | **18.4680 s** |
| **ABB (Desbalanceado)** | $O(N)$ por elem ($O(N^2)$ total) | **2.9058 s** | $O(N)$ (Degenerado) | **3.3310 s** |
| **Árbol B+ ($M=16$)** | $O(\log_M N)$ por elem | **0.0225 s** | $O(\log_M N)$ | **0.0143 s** |

---

## 3. Puntos Clave para Defender en la Sustentación

### A. Degeneración del ABB bajo Datos Ordenados

- **Fenómeno:** Al insertar datos secuenciales ($1, 2, 3 \dots N$), el Árbol Binario de Búsqueda no realiza rotaciones de balanceo. Cada elemento se inserta a la derecha del anterior, formando una línea recta de profundidad $h = N$.
- **Impacto:** Construir el árbol pasa de requerir $O(N \log N)$ a requerir $O(N^2)$ comparaciones ($\approx 50 \times 10^6$ operaciones para $N=10.000$), tardando **2.9058 s** frente a los **0.0081 s** de la Lista Enlazada.

### B. Escalabilidad en Ráfagas de Consulta ($Q$)

- Para la **Lista Enlazada**, incrementar $Q$ en un factor de 10 escala el tiempo de manera lineal estricta:
  - $Q=10 \implies 0.0170\text{ s}$
  - $Q=100 \implies 0.1864\text{ s}$
  - $Q=1.000 \implies 1.8598\text{ s}$
  - $Q=10.000 \implies 18.4680\text{ s}$
- En el **Árbol B+**, la profundidad de la estructura se mantiene en $h = \lceil \log_{16}(10.000) \rceil = 4$ niveles. Resolver $Q=10.000$ consultas solo requiere **0.0143 s**, siendo más de **1.200 veces más rápido** que la lista enlazada.

### C. Superioridad del Árbol B+ en Búsquedas por Rango

- En un escenario donde se soliciten estudiantes con IDs dentro de un rango $[ID_A, ID_B]$:
  - La **Lista Enlazada** o el **ABB** requieren recorrer recursivamente nodos dispersos en memoria ($O(N)$).
  - El **Árbol B+** localiza la hoja inicial en $O(\log_M N)$ y navega horizontalmente a través de los punteros `next` entre hojas adyacentes a velocidad de memoria contigua, optimizando la caché del procesador.

### D. Extrapolación Analítica para $N = 100.000$ y $N = 1.000.000$

- Para $N = 100.000$, la construcción del ABB en orden tomaría aproximadamente $300\text{ s}$ (5 minutos por corrida).
- Para $N = 1.000.000$, requeriría más de $8$ horas de cómputo y desencadenaría un error de límite de recursión (`RecursionError: maximum recursion depth exceeded`).
- *Conclusión:* El Árbol B+ es la única arquitectura verdaderamente escalable para volúmenes de datos masivos.

## Justificación Técnica sobre la Escala de Tiempos y el Umbral de 1s – 300s

En el marco del benchmark ejecutado con $N = 10.000$ registros y $Q = 10.000$ consultas, los tiempos de ejecución abarcan desde **$0.00003\text{ s}$ hasta $18.47\text{ s}$**. A continuación se justifica técnicamente por qué las estructuras logarítmicas se mantienen por debajo del umbral de $1\text{ s}$ y por qué no es técnicamente viable forzar a todas las estructuras a operar en el rango de $1\text{ s} - 300\text{ s}$:

---

### 1. Superioridad Algorítmica del Árbol B+ ($< 1\text{ s}$)

El Árbol B+ con orden $M = 16$ mantiene una profundidad extremadamente reducida:
$$h = \lceil \log_{16}(10.000) \rceil = 4 \text{ niveles}$$

- **Búsqueda Puntual:** Responder una consulta requiere como máximo **4 saltos de puntero en memoria RAM**. Resolver $Q = 10.000$ búsquedas requiere solo $\approx 40.000$ operaciones, ejecutándose en **$0.0143\text{ s}$ ($14.3\text{ ms}$)**.
- **Acceso a Memoria:** Al ejecutarse 100% en RAM física, la latencia por acceso a nodo es del orden de nanosegundos ($10 - 100\text{ ns}$), optimizada por la localidad de referencia en las líneas de caché L1/L2/L3 del procesador.
- **Conclusión:** Para que el Árbol B+ alcance un tiempo de $1\text{ s}$ o $300\text{ s}$, se requeriría elevar $N$ a decenas de millones de registros ($N \ge 10^8$), lo cual excede la capacidad de pruebas locales en memoria RAM.

---

### 2. Validación del Umbral $> 1\text{ s}$ en Algoritmos Ineficientes

El benchmark demuestra que las estructuras con complejidad lineal $O(N)$ o cuadrática $O(N^2)$ **sí ingresan y superan el rango de $1\text{ s}$** para $N = 10.000$:

1. **Inserción Ordenada en ABB ($2.91\text{ s}$):**
   Debido a la falta de balanceo, la altura del árbol degenera en $h = N = 10.000$. Construir el árbol requiere $\frac{N(N+1)}{2} \approx 50 \times 10^6$ comparaciones en Python interpretado, alcanzando **$2.9058\text{ s}$** (ingresando al rango de $1\text{ s} - 300\text{ s}$).

2. **Búsqueda Masiva en Lista Enlazada con $Q = 10.000$ ($18.47\text{ s}$):**
   La búsqueda lineal $O(N \cdot Q)$ requiere escanear en promedio $\frac{N}{2} = 5.000$ nodos por consulta. Para $Q = 10.000$, se ejecutan $50 \times 10^6$ iteraciones secuenciales, tardando **$18.4680\text{ s}$**.

---

### 3. Inviabilidad de Forzar $300\text{ s}$ para Todas las Estructuras

Si se incrementara el tamaño del problema (por ejemplo a $N = 100.000$ o $N = 1.000.000$) con el fin de obligar al Árbol B+ a aproximarse a $1\text{ s}$:

- **Colapso del ABB:** Al ser $O(N^2)$, una inserción con $N = 100.000$ requeriría $\approx 300\text{ s}$ (5 minutos), y con $N = 1.000.000$ tomaría **más de 8 horas por prueba**, además de generar un desbordamiento de pila (`RecursionError`) por la profundidad de llamadas recursivas ($h = 1.000.000$).
- **Colapso de la Lista Enlazada:** La búsqueda con $Q = 10.000$ sobre $N = 1.000.000$ requeriría más de **30 minutos por corrida**.

---

### 4. Solución Visual: Escalas Semilogarítmicas y Log-Log

Para representar de forma coherente en un mismo gráfico magnitudes que varían desde $0.00003\text{ s}$ hasta $18.47\text{ s}$ (un rango dinámico de más de 5 órdenes de magnitud), se utilizaron **gráficas en escala semi-logarítmica (`semilog_busquedas.png`) y log-log (`loglog_insercion.png`)**.

Esto evita que las curvas sub-segundo del Árbol B+ queden "aplastadas" visualmente contra el eje $X$ y permite apreciar la pendiente matemática real de cada estructura.
