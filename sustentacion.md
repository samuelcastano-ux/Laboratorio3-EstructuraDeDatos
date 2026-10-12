# Material de Apoyo para Sustentación Técnica — Laboratorio 3

## 1. Muestreo Estadístico e Higiene de Medición

- **Muestreo:** $K = 10$ repeticiones para $N \le 10.000$; $K = 5$ para las mediciones estándar en $N = 20.000$, $N = 30.000$, $N = 50.000$ y $N = 100.000$; en ABB ordenado se usa $K = 3$ para $N \in \{20.000, 30.000, 50.000, 100.000\}$ y en Lista Enlazada para $N = 100.000$; $K = 3$ para todas las estructuras medidas en $N \in \{500.000, 1.000.000\}$.
- **Higiene:** Supresión del recolector de basura (`gc.disable()`) durante los bloques de medición, temporizador de alta resolución (`time.perf_counter()`) y ventanas adaptativas de ejecución ($\ge 1,0\text{ s}$).
- **Tratamiento de Atípicos:** Aplicación del criterio Rango Intercuartílico (IQR) para reportar valores atípicos sin eliminarlos arbitrariamente de los datasets crudos.
- **Unidades:** Estandarización estricta de todos los tiempos en segundos (s).

---

## 2. Comparativa Empírica Principal ($N = 10.000$)

| Estructura | Inserción (s) | Búsqueda $Q=1.000$ (s) | Búsqueda $Q=10.000$ (s) | Memoria (MB) | Altura Promedio |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Lista Enlazada (IDs Aleatorios)** | **0,0065 s** | **1,2508 s** | **12,6555 s** | **0,84 MB** | **1,0** |
| **ABB (IDs Ordenados)** | **2,8664 s** | **0,2342 s** | **2,3373 s** | **0,99 MB** | **10.000,0** |
| **ABB (IDs Aleatorios)** | **0,0198 s** | **0,0015 s** | **0,0156 s** | **0,99 MB** | **31,1** |
| **Árbol B+ ($M=16$, Aleatorio)** | **0,0247 s** | **0,0009 s** | **0,0098 s** | **0,50 MB** | **4,0** |

---

## 3. Puntos Clave de Defensa Técnica

1. **Degeneración Cuadrática del ABB Ordenado ($O(N^2)$):**
   *Al recibir claves secuenciales sin rotaciones de balanceo, la altura crece linealmente ($h = N$). La construcción en $N = 10.000$ toma **2,8664 s**, escala a **71,7215 s** en $N = 50.000$ y alcanza **286,3523 s** (~4,77 minutos) en $N = 100.000$.

2. **Costo de Overhead Constante en Árbol B+ vs. ABB Aleatorio:**
   *Para $N = 10.000$, la inserción en el Árbol B+ (**0,0247 s**) es ligeramente superior al ABB Aleatorio (**0,0198 s**). Este sobrecosto proviene de la administración interna de arreglos en nodos y divisiones (*splits*). Sin embargo, en $N = 100.000$, el Árbol B+ toma la delantera (**0,2826 s** vs **0,3845 s**) y en $N = 1.000.000$ confirma su superioridad (**5,7007 s** vs **6,5557 s**).

3. **Eficiencia de Memoria y Localidad de Caché:**
   *En $N = 1.000.000$, el Árbol B+ ($M=16$) consume únicamente **50,17 MB** frente a los **99,18 MB** del ABB Aleatorio (una reducción del 49,4% en espacio), logrando además resolver $10.000$ consultas en **0,0385 s** frente a **0,0580 s** del ABB.
