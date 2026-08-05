# ADR 004 — Comparación simultánea entre ruta estándar y ruta HGV

**Estado:** Aceptado
**Fecha:** 2026-08-05

## Contexto

El backend de BusRoad calcula, para cada origen/destino, **dos rutas con las
mismas coordenadas**:

1. **Ruta segura** (perfil `driving-hgv` de ORS): respeta las restricciones de
   altura, anchura, largo y peso del vehículo.
2. **Ruta convencional** (perfil `driving-car`): la que seguiría un coche
   normal, sin restricciones.

El endpoint `/api/v1/ruta` devuelve ambas con su distancia, duración, polyline
y pasos.

## Problema

El valor de BusRoad es demostrar **por qué** la ruta del vehículo es distinta
(y a veces más larga). Si solo se mostrara la ruta segura, el usuario no
tendría referencia: vería 68 km y 1h10 sin saber si eso es bueno o malo. La
pregunta implícita de todo conductor es: "¿y por qué no voy por la otra?".

## Alternativas evaluadas

1. **Mostrar solo la ruta segura**: sin referencia, el usuario no percibe el
   trade-off ni confía en la planificación. Descartada.
2. **Mostrar la ruta estándar solo si hay diferencias**: técnicamente posible,
   pero el usuario no vería el caso "coinciden" (que también comunica valor:
   "no hay obstáculos para tu vehículo"). Descartada.
3. **Comparación simultánea siempre visible**: las dos rutas se calculan,
   se dibujan en el mapa (segura en color del tema, estándar en gris
   punteado) y se presentan en dos tarjetas con tiempo, distancia y una nota
   que explica la relación entre ambas.

## Decisión

La comparación simultánea es una **decisión de UX además de técnica**: el
resultado muestra siempre ambas rutas, en el mapa y en tarjetas:

- **Mapa**: ruta segura gruesa (6px, color del tema) sobre la estándar fina
  punteada (3px gris), con leyenda integrada.
- **Tarjetas**:
  - Tarjeta segura con sello "🛡 Compatible con tu vehículo", tiempo,
    distancia, nº de pasos y caja "✓ Calculado con las restricciones".
  - Tarjeta estándar con aviso contextual: si es más corta pero no apta
    ("Más corta pero no apta: puede pasar por vías con restricciones"), o si
    coincide ("Coinciden: no hay obstáculos para tu vehículo").
- **Formato**: tiempo en `1h 10m` y distancia destacada a la derecha, para que
  el trade-off se lea en un vistazo sin explicaciones.
- Cada tarjeta tiene su botón de navegación (la segura con waypoints del
  ADR 003; la estándar abre Google Maps sin waypoints).

## Consecuencias

**Positivas**

- El usuario entiende el valor del producto **de un vistazo**: "tardo más
  porque esta ruta está adaptada a mi vehículo". No necesita leer
  documentación.
- La comparación es demostrable: un reclutador o arquitecto ve en 5 segundos
  la propuesta de valor de BusRoad.
- El caso "coinciden" comunica confianza: no hay obstáculos, la ruta segura y
  la de coche son la misma.
- Un coste de backend mínimo: ORS ya calcula ambas rutas en una petición.

**Negativas / límites**

- Más ruido visual para un usuario que solo quiere una ruta. Mitigado con
  jerarquía clara (la tarjeta segura es la protagonista, la estándar tiene
  opacidad visual menor).
- El doble cálculo duplica el tiempo de respuesta de ORS (~2x), aunque se
  hace en paralelo en el backend. Aceptable para uso personal.
- La comparación de kilómetros puede inducir a error si el usuario la lee
  como "la app elige mal": la nota contextual ("más corta pero no apta")
  explica la diferencia.
