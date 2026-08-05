# ADR 002 — Preservación de la geometría de ORS en el cliente

**Estado:** Aceptado
**Fecha:** 2026-08-05

## Contexto

OpenRouteService devuelve, para cada ruta, una **geometría completa** (polyline
encoded con miles de coordenadas) que representa exactamente el recorrido
calculado con las restricciones del vehículo. El frontend recibe ese polyline
junto con los datos resumidos (distancia, duración, pasos).

En la primera versión de la app, esa geometría solo se usaba para extraer
waypoints y abrir Google Maps: el usuario nunca veía el recorrido real que ORS
había calculado. La vista principal del resultado era un texto con distancia y
duración.

## Problema

La geometría de ORS es el activo más valioso de la planificación: es **la**
prueba de que la ruta respeta las restricciones del vehículo. Al no mostrarla,
el usuario dependía de lo que Google Maps decidiera dibujar, y Google
recalcula el recorrido a su manera (ver ADR 001). Resultado: el conductor veía
una ruta distinta de la planificada, sin forma de comprobar la decisión del
motor.

## Alternativas evaluadas

1. **Solo texto (distancia/duración/pasos)**: sin mapa, el usuario no ve el
   recorrido. Descartada: pierde el valor visual de la planificación.
2. **Extraer waypoints y abrir Google Maps**: el navegador redibuja y degrada
   la ruta (problema documentado en ADR 001). Descartada como vista principal.
3. **Pintar la geometría completa en el cliente con Leaflet**: muestra
   exactamente lo que calculó ORS, sin intermediarios. Gratis (tiles de
   OpenStreetMap, sin API key), fidelidad total.

## Decisión

El cliente **preserva y representa la geometría completa de ORS** con
Leaflet + OpenStreetMap:

- El polyline encoded se decodifica en el cliente (función estándar de
  decodificación, factor 1e5) y se dibuja como polyline sobre el mapa.
- La ruta segura se dibuja en el color del tema (gruesa, 6px); la convencional
  en gris punteado (3px) debajo, para comparar.
- Marcadores de origen/destino (divIcon con emoji, evitando el problema de
  assets de los iconos por defecto de Leaflet).
- `fitBounds` con padding reducido para que la ruta ocupe ~80% del mapa.
- Leyenda integrada debajo del mapa, fuera de la superposición.

## Consecuencias

**Positivas**

- La vista principal muestra **exactamente** la ruta optimizada: fidelidad
  total entre lo que se planifica y lo que se ve.
- El mapa es el diferenciador visual del producto: la comparación de dos
  trazados comunica la propuesta de valor sin leer una palabra.
- Coste cero: Leaflet es open source y los tiles de OSM son gratuitos para
  uso razonable.

**Negativas / límites**

- Dependencia de internet para cargar los tiles de OSM (la app ya es online
  por diseño).
- El bundle crece (~150 KB extra con Leaflet). Aceptable para una app móvil
  PWA; evaluar code-splitting si crece más.
- OSM impone una política de uso razonable de tiles: suficiente para
  portfolio/uso personal; un producto con alto tráfico debería autoalojar
  tiles o usar un proveedor comercial.
