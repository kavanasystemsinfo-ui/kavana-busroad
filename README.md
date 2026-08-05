# Kavana BusRoad

Aplicación PWA para cálculo de rutas de vehículos grandes (autobuses, camiones, grúas) con restricciones de dimensión: altura, anchura, largo y peso. Evita puentes bajos, túneles con límite y calles estrechas usando datos reales de OpenStreetMap.

## 📋 Descripción

Kavana BusRoad ayuda a transportistas y conductores de vehículos de gran tamaño a planificar rutas seguras según las dimensiones reales de su vehículo. A diferencia de Google Maps (que calcula rutas de coche), BusRoad aplica las restricciones del vehículo en cada tramo y muestra la comparación con la ruta convencional.

- **Frontend**: Vue 3 + Vite (PWA) desplegado en Vercel
- **Backend**: FastAPI (Python) desplegado en Kubernetes (k3s) en el VPS
- **Motor de rutas**: [OpenRouteService](https://openrouteservice.org/) con perfil `driving-hgv` (vehículos pesados): aplica restricciones reales de altura, anchura, largo y peso en Europa usando datos de OpenStreetMap. Google Routes queda como respaldo de ruta estándar (NO aplica dimensiones fuera de EE.UU.).
- **Navegación**: los botones de Google Maps/Waze usan waypoints extraídos del polyline de la ruta segura, forzando al navegador a seguir el itinerario calculado.

## 🛠️ Stack Tecnológico

| Área | Tecnologías |
|------|-------------|
| Frontend | Vue 3, Vite, TypeScript |
| Backend | FastAPI, Uvicorn, Pydantic, httpx |
| Infra | Docker, Kubernetes (k3s), nginx, Let's Encrypt |
| Despliegue | Vercel (frontend), k3s VPS + nginx (backend) |
| API externa | OpenRouteService (`driving-hgv`, geocoding) · Google Routes (fallback) |
| DNS | Namecheap (subdominio `busroad-api.kavanasystems.com`) |

## 📁 Estructura del proyecto

```
kavana-busroad/
├── backend/            # API FastAPI
│   ├── app/
│   │   ├── main.py     # Entrypoint + health check
│   │   └── motor.py    # Motores de rutas (ORS → Google → mock)
│   ├── Dockerfile      # Imagen python:3.12-slim
│   ├── .env.example
│   └── requirements.txt
├── frontend/           # PWA Vue 3 + Vite
│   ├── src/App.vue     # Formulario + comparativa de rutas + botones de navegación
│   ├── .env.example    # VITE_API_URL
│   └── package.json
├── k8s/
│   ├── backend.yaml    # Deployment + Service NodePort :30080
│   └── README.md       # Arquitectura de despliegue k3s
├── .gitignore
└── README.md
```

## ⚙️ Configuración

### Variables de entorno (backend)

Copia `backend/.env.example` a `backend/.env` y completa:

```dotenv
# MOTOR PRINCIPAL: OpenRouteService (restricciones de dimensiones reales en Europa)
# Clave gratuita: https://openrouteservice.org/dev-portal/ (2.000 rutas/día)
ORS_API_KEY=tu_clave_ors

# MOTOR DE RESPALDO: Google Routes (ruta estándar, sin dimensiones fuera de EE.UU.)
# Opcional. Si no está, el motor principal es ORS; si tampoco hay ORS, devuelve mock.
GOOGLE_API_KEY=tu_clave_google

# Puerto (default: 8000)
PORT=8000
```

> **Nota**: El orden de motores es `ORS → Google → mock`. Solo si no hay ninguna clave configurada se devuelve una ruta de ejemplo (mock) para desarrollo sin costo.

### Variables de entorno (frontend)

Copia `frontend/.env.example` a `frontend/.env`:

```dotenv
# URL del backend en producción
VITE_API_URL=https://busroad-api.kavanasystems.com
# Para desarrollo local: VITE_API_URL=http://localhost:8000
```

## ▶️ Ejecutar en desarrollo

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La API queda en `http://localhost:8000` (Swagger en `/docs`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

La PWA se sirve en `http://localhost:5173`.

## 🐳 Docker

```bash
cd backend
docker build -t kavana-busroad-backend:0.1.0 .
docker run -p 8000:8000 --env-file .env kavana-busroad-backend
```

## ☸️ Despliegue en Kubernetes (k3s)

El backend corre en un clúster k3s en el VPS. Documentación completa en `k8s/README.md`.

Resumen:

```bash
# 1. Construir imagen y cargarla en k3s (sin registro externo)
docker build -t kavana-busroad-backend:0.1.0 backend/
docker save kavana-busroad-backend:0.1.0 | k3s ctr images import -

# 2. Secret con las claves de API
kubectl create secret generic busroad-secrets \
  --from-literal=ors_api_key=TU_CLAVE_ORS \
  --from-literal=google_api_key=TU_CLAVE_GOOGLE

# 3. Deployment + Service (NodePort 30080)
kubectl apply -f k8s/backend.yaml

# 4. nginx del VPS proxea busroad-api.kavanasystems.com → 127.0.0.1:30080
#    con certificado Let's Encrypt (renovación automática vía certbot.timer)
```

> **Pitfall conocido**: el LoadBalancer de Traefik (viene con k3s) captura los puertos 80/443 del host con reglas nftables antes que nginx. Si el tráfico no llega a nginx, convertir el Service de Traefik a ClusterIP (ver `k8s/README.md`).

## 🧪 Health Check

```bash
curl https://busroad-api.kavanasystems.com/api/v1/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "motor": "openrouteservice"   // o "google-routes" / "mock"
}
```

## 📖 Documentación de la API

Swagger UI en `http://localhost:8000/docs` (o `https://busroad-api.kavanasystems.com/docs`).

Endpoints principales:

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/health` | Estado y motor activo |
| POST | `/api/v1/ruta` | Calcula ruta segura + convencional dado origen, destino y dimensiones del vehículo |

Payload de ejemplo:

```json
{
  "origen": "Estació del Nord, Valencia",
  "destino": "C. de Ing. Tamarit, 9, 46170 Villar del Arzobispo, Valencia",
  "vehiculo": { "alto_m": 3.5, "ancho_m": 2.5, "largo_m": 12.0, "peso_kg": 12000 }
}
```

Respuesta: distancia, duración, polyline, pasos en español, y la ruta convencional (coche) para comparar.

## 🚀 Despliegue del frontend (Vercel)

1. Repositorio en GitHub (kavanasystemsinfo-ui/kavana-busroad).
2. En Vercel, importa el proyecto y apunta al directorio `frontend/`.
3. Variable de entorno: `VITE_API_URL=https://busroad-api.kavanasystems.com`.
4. Vercel detecta Vite y despliega automáticamente.

## 🧭 Cómo navegar con la ruta segura

1. Calcula la ruta con las dimensiones de tu vehículo.
2. La app muestra **la geometría exacta de ORS** en un mapa Leaflet (ruta segura en color del tema, convencional en gris punteado) y las dos tarjetas comparativas con tiempo/distancia.
3. Pulsa **"Iniciar Navegación"**: la app extrae los **vértices con cambio de dirección > 12°** (cruces, salidas, curvas) de la geometría y los inyecta como waypoints en Google Maps (o navega en Waze), obligando al navegador a mantener el itinerario optimizado.

> **Arquitectura**: BusRoad es la fuente de verdad. OpenRouteService calcula la geometría completa, Leaflet la representa íntegramente, y Google/Waze se usan únicamente como clientes de navegación. Google Maps no conoce las restricciones de tu vehículo y puede adaptar ligeramente el recorrido por tráfico; los waypoints en los cruces clave minimizan esa deriva. Ver [ADR 001](docs/adr/001-motor-planificacion-vs-navegacion.md).

## 📐 Decisiones de arquitectura (ADRs)

Las decisiones importantes se documentan como ADRs en [`docs/adr/`](docs/adr/):

| ADR | Decisión |
|---|---|
| [001](docs/adr/001-motor-planificacion-vs-navegacion.md) | Separación entre motor de planificación (ORS + Leaflet) y motor de navegación (Google/Waze como clientes) |
| [002](docs/adr/002-preservacion-geometria-ors-cliente.md) | Preservación de la geometría completa de ORS en el cliente (Leaflet la representa íntegramente) |
| [003](docs/adr/003-seleccion-waypoints-cambios-direccion.md) | Selección de waypoints basada en cambios de dirección > 12° (no muestreo uniforme) |
| [004](docs/adr/004-comparacion-ruta-estandar-vs-hgv.md) | Comparación simultánea de ruta estándar y ruta HGV como decisión de UX + técnica |

## 📚 Próximos pasos

- [ ] **Migrar backend de k3s (VPS) a Fly.io** (decisión 2026-08-05): el VPS es el laboratorio de trabajo, no producción. Backend en servicio independiente como el resto del portfolio. Incluye: desplegar Dockerfile en Fly.io, mover claves a secrets de Fly, actualizar `VITE_API_URL` del frontend, actualizar ADR 001 y landing.
- [ ] APK para el hermano (Capacitor + Android Studio) con ajustes: vehículo precargado, tema, quitar comparación
- [ ] Dominio propio para el frontend (`busroad.kavanasystems.com`, CNAME pendiente en Namecheap)
- [ ] Pruebas unitarias e integración (pytest) del backend
- [ ] CI/CD con GitHub Actions
- [ ] Internacionalización (i18n)
- [ ] Autenticación y guardado de rutas favoritas

## 📄 Licencia

Proyecto privado de Kavana Systems. No se redistribuye sin permiso explícito.

## 🙏 Créditos

- Inspirado por un problema real: un conductor de autobús recién titulado planificaba rutas con Google Maps sin saber si su vehículo pasaba por puentes y calles.
- Motor: OpenRouteService (perfil `driving-hgv`) con restricciones de OpenStreetMap.
- Desarrollado con ☕ y 🚍 por el equipo de Kavana.

---

*README actualizado el 2026-08-04 por Hermes Agent siguiendo los estándares de Kavana Engineering.*
