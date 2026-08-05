# ADR 001 — Separación entre motor de planificación y motor de navegación

**Estado:** Aceptado
**Fecha:** 2026-08-05

## Contexto

BusRoad calcula rutas para vehículos pesados (autobuses, camiones) usando
**OpenRouteService** con perfil `driving-hgv`, que aplica restricciones reales
de altura, anchura, largo y peso extraídas de OpenStreetMap. En Europa, Google
Routes API no aplica estas restricciones (el campo `vehicle` ni siquiera se
acepta fuera de EE.UU.), por lo que Google quedó descartado como motor de
cálculo desde el inicio.

El usuario final (un conductor de autobús) necesita dos cosas distintas:

1. **Ver** la ruta optimizada con sus restricciones (planificación).
2. **Navegar** por ella con instrucciones por voz mientras conduce (GPS).

## Problema

Inicialmente, el frontend exportaba **8 waypoints muestreados uniformemente**
de la geometría de ORS a una URL de Google Maps (`dir/?api=1&waypoints=...`).
Esto provocaba dos efectos indeseados:

1. **Google recalcula el recorrido**: Google Maps no acepta una geometría
   completa; solo acepta origen, destino y waypoints, y vuelve a calcular la
   mejor ruta entre ellos. La ruta dibujada podía diferir de la optimizada por
   ORS (otras salidas de autovía, otros accesos, desvíos).
2. **Waypoints geocodificados inversamente**: los puntos intermedios en mitad
   del campo aparecían con nombres absurdos ("Polígono 10", "UT.2",
   "DEYUNIK", "Placa Número 13"), y puntos cercanos entre sí (p. ej. dos
   waypoints en Sagunto) hacían que Google entrara por un acceso y saliera por
   otro, dibujando trazados que se cruzan visualmente (apariencia de
   "bifurcación" en la captura del usuario).

El resultado: la ruta que el conductor veía y seguía no era la ruta que
BusRoad había optimizado.

## Alternativas evaluadas

1. **Google Maps como navegador con waypoints uniformes** (situación inicial):
   coste cero, pero Google recalculaba y degradaba la ruta optimizada.
   Descartada como solución principal.
2. **Waypoints inteligentes en cambios de dirección**: extraer solo los
   vértices donde la geometría cambia de dirección > 12° (cruces, salidas,
   curvas) y pasarlos como waypoints. Mejora la fidelidad, pero Google sigue
   recalculando entre waypoints; no es exacto, solo "menos malo".
3. **Navegación propia con SDK profesional** (TomTom Navigation SDK, HERE
   Navigation SDK, Sygic Professional): navega exactamente sobre la geometría,
   pero tiene coste de licencia y complejidad alta. Descartada para la fase
   actual (proyecto portfolio, uso personal).
4. **Visualización independiente con Leaflet + OpenStreetMap**: pintar la
   geometría completa de ORS en un mapa propio, sin depender de ningún
   navegador para la vista. Gratis (sin API key), fidelidad total al cálculo
   de ORS.

## Decisión

Adoptar una **arquitectura con separación de responsabilidades**: BusRoad es
la **fuente de verdad** de la planificación; los navegadores comerciales son
**clientes de navegación** opcionales.

1. **Planificación y visualización**: Leaflet + OpenStreetMap pinta la
   geometría completa de ORS (miles de coordenadas, sin muestrear). La ruta
   segura se dibuja en el color del tema y la convencional en gris punteado,
   con marcadores de origen/destino y leyenda. Es la vista principal de la
   app y lo que el conductor debe seguir.
2. **Navegación delegada**: los botones "Iniciar Navegación" (Google Maps) y
   Waze abren el navegador con **waypoints inteligentes** (vértices con cambio
   de dirección > 12°, máximo 8, con fallback uniforme si la ruta es casi
   recta) para que el navegador no ataje por caminos no optimizados. Se acepta
   que el navegador pueda adaptar ligeramente el recorrido por tráfico.
3. **Transparencia**: la UI avisa explícitamente de que el navegador puede
   adaptar la ruta por tráfico u otras condiciones, pero que los waypoints en
   los cruces clave mantienen el itinerario optimizado.
4. **Agnosticismo del navegador**: la capa de navegación es un botón que abre
   URLs estándar; mañana podría añadirse TomTom GO, Sygic Truck o cualquier
   otro cliente sin tocar la planificación.

## Consecuencias

**Positivas**

- La ruta mostrada en la app es **exactamente** la calculada por ORS con las
  restricciones del vehículo. Fidelidad total en planificación.
- Google/Waze dejan de influir en la decisión de ruta: solo ejecutan la
  navegación por voz.
- La arquitectura es defendible en entrevistas: distingue claramente entre
  *motor de optimización* y *motor de navegación*, y documenta un rediseño
  motivado por un problema real detectado en uso.
- Coste cero: Leaflet + OpenStreetMap son gratuitos, sin API key.
- Base lista para evolucionar: SDK de navegación profesional (TomTom/HERE) en
  el futuro sin tocar la capa de planificación.

**Negativas / límites**

- La navegación delegada no es 100 % fiel: Google Maps puede recalcular entre
  waypoints. Para fidelidad total en conducción haría falta un SDK de pago
  (alternativa 3), fuera de alcance actual.
- Leaflet requiere conexión a internet para los tiles de OpenStreetMap (la
  app ya es online por diseño).
- Los tiles de OSM tienen política de uso razonable: suficiente para uso
  personal/portfolio; un producto con alto tráfico debería evaluar un tile
  provider propio (MapLibre + tiles autoalojados o proveedor comercial).
