# ADR 006 — Paradas intermedias y optimización de orden (VROOM)

**Estado:** Aceptado
**Fecha:** 2026-08-05

## Contexto

El hermano de Jorge es conductor de autobús escolar. Una de sus tareas
habituales es la **ruta de colegios**: salir de un punto, pasar por varias
paradas para recoger niños y llegar al colegio. Es el mismo patrón que
manejan las apps de transporte profesional (Sygic, TomTom GO).

La primera versión de BusRoad solo calculaba rutas de un punto A a un punto B
(`coordinates: [origen, destino]`). Para las rutas escolares faltaba el
concepto de **paradas intermedias** entre el origen y el destino.

## Problema

Dos necesidades distintas que no existían:

1. **Múltiples puntos intermedios**: el conductor necesita definir N paradas
   (direcciones de recogida) entre el origen y el colegio, y que la ruta pase
   por todas ellas **respetando las restricciones del vehículo** (altura,
   anchura, largo, peso) en todo el recorrido.
2. **Dos modos de recorrido** según el caso de uso:
   - **Orden manual**: el orden de recogida lo fija el conductor (los niños
     esperan en sus paradas, no se puede saltar). Es el caso típico escolar.
   - **Optimización automática**: si el orden da igual (reparto, vuelta al
     depósito), interesa el recorrido más corto posible (problema del viajante
     con restricciones).

## Alternativas evaluadas

1. **Solo orden manual** (pasar las coordenadas a ORS directions en orden):
   ORS ya soporta N coordenadas en `coordinates` y aplica las restricciones a
   todo el recorrido. Cubre el caso escolar, pero no resuelve "¿cuál es el
   orden más eficiente?".
2. **Optimización en el cliente**: implementar un algoritmo de optimización
   (vecino más cercano, 2-opt) en el frontend. Se descartó: duplicaría lógica
   que ORS ya ofrece, añadiría código a mantener y el 2-opt en JS para 20
   paradas es peor que el solver de VROOM.
3. **Endpoint `/optimization` de ORS (VROOM)**: resuelve el problema del
   viajante con perfil `driving-hgv`, respetando restricciones, con
   `start`/`end` fijos y jobs (paradas) libres. Devuelve el **orden óptimo** de
   visita, no la geometría. Elegido para el modo optimización.

## Decisión

### 1. API con paradas opcionales

`RutaRequest` gana dos campos:

- `paradas: list[str]` (hasta 20): direcciones intermedias, geocodificadas
  igual que origen/destino (España forzada, radio 1500 m).
- `optimizar: bool`: si es true, se reordenan las paradas antes de calcular.

Las coordenadas completas `[origen, parada1, ..., paradaN, destino]` se pasan
a ORS directions (`driving-hgv` con restricciones), que calcula el recorrido
total con pasos e instrucciones en español.

### 2. Optimización con VROOM (no con `optimized`)

- El endpoint de directions **no acepta** `optimized` en esta versión de ORS
  (error 2002 "Parameter 'optimized' has incorrect value or format",
  verificado 2026-08-05).
- La optimización se hace con el endpoint `/optimization` (VROOM): un vehicle
  con `start`/`end` fijos y un job por parada. El resultado devuelve los
  **steps en orden óptimo** (start → job 3 → job 1 → ... → end).
- Se reordenan las coordenadas según ese orden y se llama a directions con el
  orden ya optimizado para obtener la geometría y los pasos.
- Si la optimización falla (timeout, red), se usa el orden dado por el
  usuario: la optimización es una mejora, nunca un bloqueo.

### 3. Frontend

- Botón "➕ Añadir parada" (hasta 20) en la pestaña Ruta, cada parada con
  subir/bajar/eliminar.
- Checkbox "Optimizar orden" visible solo con 2+ paradas.
- El mapa Leaflet dibuja la geometría completa pasando por todas las paradas.

## Consecuencias

**Positivas**

- BusRoad cubre el caso de uso escolar real del hermano de Jorge: recogida de
  niños con paradas y restricciones de vehículo.
- La optimización demuestra valor cuantificable: en la prueba real
  (Torres de Serranos → 3 paradas → IES Cheste) el orden manual malo dio
  132,1 km y el optimizado 90,9 km: **41 km y 37 minutos de ahorro**.
- La separación "orden manual vs optimizado" es la misma que usan las apps
  profesionales (Sygic): el conductor controla el orden cuando importa.
- Un endpoint de ORS más en el stack (directions + optimization + geocode),
  con su ADR: más material de entrevista.

**Negativas / límites**

- VROOM no devuelve la geometría: hace falta una segunda llamada a directions
  con el orden reordenado (2 peticiones ORS por ruta optimizada; con la cuota
  gratuita de 2.000/día es irrelevante a este uso).
- La optimización usa perfil `driving-hgv` pero sin restricciones de
  dimensiones en el solver VROOM (no se pasan en esta versión): el orden
  óptimo se calcula sobre distancias hgv, y las restricciones se aplican
  después en directions. Para rutas escolares con pocas paradas es
  despreciable; si hubiera casos con restricciones muy asimétricas, habría
  que revisar.
- Los waypoints de navegación (Google/Waze) se generan sobre el polyline
  final, que ya incluye todas las paradas: no hay impacto adicional.
