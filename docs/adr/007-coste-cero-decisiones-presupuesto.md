# ADR 007 — Coste cero y decisiones tomadas por presupuesto

**Estado:** Aceptado
**Fecha:** 2026-09-17

## Contexto

BusRoad es una pieza de portafolio de Kavana Systems con **un solo usuario real:
su autor**. No hay usuarios externos, ni clientes, ni compromiso de servicio, y
el objetivo declarado es coste ~0 €/mes. Eso condiciona todas las decisiones que
tocan dinero: motor de rutas, hosting, persistencia, modelo del asistente, DNS,
CI y entornos.

El riesgo de este escenario no es gastar poco, es **disimular el límite**: si el
README presenta como arquitectura de producción lo que en realidad es una
elección de presupuesto (cold start, cuotas gratuitas, datos solo en el navegador,
sin CI), la documentación miente. Este ADR fija qué se decidió por coste y qué
señales obligan a revisarlo.

## Decisión

Se eligen por coste marginal cero todas las piezas que dependen de presupuesto, y
cada límite aceptado queda escrito:

- **Motor de rutas:** OpenRouteService con perfil `driving-hgv` sobre clave
  gratuita (2.000 rutas/día), con **Nominatim** como respaldo de geocodificación.
  Si no hay claves configuradas, el backend responde una ruta de ejemplo (mock).
- **Backend:** Fly.io en plan hobby: una sola app (`busroad-api`), una región
  (`cdg`), VM de `256mb` / `1` CPU compartida, `auto_stop_machines = "stop"` y
  `min_machines_running = 0` (`fly.toml`, ver ADR 005).
- **Frontend y DNS:** PWA Vue 3 en el plan gratuito de Vercel; registros
  A/AAAA/`_acme-challenge` de `busroad-api.kavanasystems.com` mantenidos a mano
  en Namecheap con certificados Let's Encrypt emitidos por Fly/Vercel.
- **Sin base de datos ni autenticación:** vehículos, favoritos, configuración y
  borrador de ruta viven en `localStorage` del navegador (`frontend/src/App.vue`).
- **API abierta:** `/api/v1/ruta` y el asistente no piden credenciales. La única
  protección es un límite de 15 preguntas/día por IP con contador en memoria del
  proceso (`backend/app/assistant.py`), más una lista fija de orígenes CORS en
  `backend/app/main.py`.
- **Asistente RAG:** TF-IDF en memoria sobre README y ADRs, con modelo `:free` de
  OpenRouter por defecto (`ASSISTANT_MODEL_FREE` / `MODELO_PRO`).
- **Sin CI/CD ni staging:** los tests de `backend/tests/` se ejecutan a mano
  (pytest no está en `backend/requirements.txt`), el backend se despliega con
  `flyctl deploy` y el frontend lo despliega Vercel al hacer push.

## Alternativas evaluadas

| Decisión | Opción elegida | Alternativas evaluadas y por qué se descartaron |
|---|---|---|
| Motor de rutas | ORS `driving-hgv` con clave gratuita (2.000 rutas/día) | **Google Routes** ya está en el repo como respaldo, pero no aplica restricciones de dimensiones fuera de EE. UU. (`backend/.env.example`), así que no sirve como motor principal. **Mock sin claves**: sirve para desarrollar sin gastar cuota, nunca para una ruta real |
| Geocodificación | ORS geocode con `boundary.country=ESP` (varias candidatas por dirección) | **Nominatim como motor principal** (tal como está documentado en `backend/app/motor.py`): gratis y sin clave, pero con límite estricto (~1 req/s) y sin compromiso de servicio; por eso se usa solo como respaldo cuando ORS no encuentra la dirección |
| Hosting del backend | Fly.io hobby con auto-stop a cero | **k3s en el VPS de laboratorio**: fue la primera opción y funcionaba, pero acoplaba el proyecto al laboratorio y no aportaba plataforma nueva (ADR 005). **Render**, usado por otros proyectos del portfolio: consistente, pero no añadía ninguna plataforma al stack (ADR 005) |
| Persistencia | `localStorage` en el navegador | **Base de datos gestionada** (Neon, ya usada en otros proyectos del portfolio según ADR 005): sin cuentas ni usuarios no hay nada que persistir en servidor, y añadiría coste y superficie de fallo a cambio de nada |
| Modelo del asistente | Modelo `:free` de OpenRouter | **Modelo de pago con SLA**: sin usuarios reales del asistente no hay tráfico que justifique el coste; se acepta la falta de garantía de disponibilidad (configurable por entorno con `ASSISTANT_MODEL_FREE` / `MODELO_PRO`) |
| CORS | Lista fija de orígenes en el código | **Configuración por entorno**: no existen dev/staging/prod separados, así que una lista fija (localhost, dominio propio, URLs de Vercel) es suficiente hoy |

## Consecuencias

**Positivas**

- Coste ~0 €/mes: todas las piezas caben en planes gratuitos (ORS, Fly.io
  hobby, Vercel, Nominatim, tiles de OSM).
- Cero datos personales en el servidor: al no haber cuentas ni base de datos, no
  hay nada que proteger ni que borrar a petición de un usuario.
- Los límites son verificables en el propio repo (`fly.toml`,
  `backend/.env.example`, `backend/app/assistant.py`), no promesas.

**Negativas / límites**

- **Cold start**: con `min_machines_running = 0`, el primer request tras el
  reposo tarda en responder (ya reconocido en ADR 005).
- **Una sola región y sin redundancia**: en `cdg` y con `min_machines_running = 0`
  no hay instancia caliente; si Fly no arranca la máquina, la API no responde.
- **Cuota compartida**: las 2.000 rutas/día de ORS son una clave gratuita que se
  comparte con el desarrollo y las pruebas.
- **Rate limit en memoria**: el contador de 15 preguntas/día se pierde al
  reiniciar la máquina y no se comparte entre instancias; no sirve con más de una
  máquina.
- **API sin autenticación**: cualquiera que conozca la URL consume cuota de ORS y
  de OpenRouter.
- **Datos frágiles por diseño**: favoritos y vehículos viven en el navegador; se
  pierden al borrar el almacenamiento del dispositivo y no se sincronizan.
- **Entrega manual**: sin CI, un push no valida nada; los tests hay que
  ejecutarlos a mano y con pytest instalado aparte.

## Señal de revisión

Revisar este ADR cuando ocurra cualquiera de estas cosas:

1. **Aparece un segundo usuario real** (aunque sea una prueba con un conductor
   externo): toca cuentas, base de datos, autenticación y rate limit distribuido.
2. **El consumo se acerca a las 2.000 rutas/día de ORS** o hay quejas de latencia
   en el primer request: toca plan de pago de ORS y `min_machines_running > 0`.
3. **BusRoad pasa a usarse en explotación** (rutas escolares o repartos reales):
   toca mínimo de máquinas, más de una región, monitorización, captura de errores
   y CI/CD antes de que alguien dependa de ello.
4. **El asistente deja de ser demo de portafolio**: toca modelo de pago e
   índice persistente en lugar de TF-IDF en memoria.
5. **Cambian las IPs de Fly** o el plan de Vercel: revisar si el DNS manual en
   Namecheap sigue siendo aceptable o hay que automatizarlo.
