# ADR 003 — Selección de waypoints basada en cambios de dirección

**Estado:** Aceptado
**Fecha:** 2026-08-05

## Contexto

Cuando el usuario pulsa "Iniciar Navegación", BusRoad abre Google Maps (o
Waze) con una URL `dir/?api=1&origin=...&destination=...&waypoints=...`.
Estos navegadores **no aceptan una geometría completa**: solo origen, destino
y un número limitado de waypoints (límite práctico de ~8-9), y **recalculan la
ruta entre cada par de puntos**.

La primera implementación muestreaba 8 puntos **uniformemente** a lo largo de
la geometría (puntos equidistantes en distancia recorrida).

## Problema

El muestreo uniforme producía waypoints inútiles o contraproducentes:

1. En tramos rectos largos (autovía de 15 km) se desperdiciaban waypoints en
   puntos intermedios que no aportan nada: Google sigue la autovía igualmente.
2. En puntos donde la ruta cambia de dirección (salidas, cruces, curvas), el
   muestreo uniforme podía no capturar el vértice exacto, dejando a Google
   libertad para elegir otra salida o acceso.
3. Los waypoints intermedios en mitad del campo aparecían geocodificados
   inversamente con nombres absurdos ("Polígono 10", "UT.2", "DEYUNIK"), y
   puntos muy cercanos entre sí podían hacer que Google entrara por un acceso
   y saliera por otro, dibujando trazados que se cruzan (apariencia de
   "bifurcación" reportada por el usuario en Torres de Serranos → Cheste).

## Alternativas evaluadas

1. **Muestreo uniforme** (situación inicial): desperdicia waypoints y no
   ancla los cruces. Descartada.
2. **Todos los vértices sin límite**: excede el límite de waypoints de Google
   en rutas tortuosas. Descartada.
3. **Vértices con umbral de ángulo + límite superior**: detectar solo los
   puntos donde la dirección cambia más de X grados, y si superan el máximo,
   muestrear entre ellos; si hay muy pocos (ruta recta), volver al muestreo
   uniforme como fallback.

## Decisión

Los waypoints de navegación se seleccionan **por cambio de dirección**, no por
distancia:

- Se recorre la geometría decodificada y se calcula el ángulo entre segmentos
  consecutivos (`atan2` sobre vectores, normalizado a [0, 180]).
- Se conserva un punto como waypoint si el cambio de dirección supera
  **12 grados** (umbral empírico: captura salidas y curvas sin generar ruido).
- Si hay más de 8 vértices (ruta tortuosa), se muestrea uniformemente entre
  ellos para respetar el límite de Google.
- Si hay menos de 3 (ruta casi recta), se usa el muestreo uniforme como
  fallback para no abrir la navegación sin ningún waypoint.
- Los waypoints son coordenadas `lat,lng` crudas en la URL; el navegador las
  geocodificará inversamente (eso es inevitable y solo afecta a la etiqueta
  que muestra Google, no al recorrido).

## Consecuencias

**Positivas**

- Los cruces, salidas y curvas quedan anclados: Google no puede elegir otra
  salida en los puntos críticos del recorrido.
- No se desperdician waypoints en tramos rectos, dejando capacidad para las
  zonas que sí importan.
- La navegación delegada se acerca al itinerario planificado, que es el
  objetivo real (fidelidad total solo la daría un SDK de pago, ver ADR 001).

**Negativas / límites**

- Sigue siendo una aproximación: Google recalcula entre waypoints y puede
  variar el recorrido por tráfico. El aviso en la UI lo comunica.
- El umbral de 12° es empírico; rutas con curvas muy suaves (< 12°) pueden
  quedar sin anclar. Ajustable si aparecen casos límite.
- El fallback uniforme reintroduce el problema de etiquetas raras en rutas
  casi rectas, pero sin bifurcaciones (no hay vértices que cruzar).
