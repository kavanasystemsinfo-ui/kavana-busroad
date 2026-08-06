# Kavana BusRoad

Aplicación PWA para cálculo de rutas de vehículos grandes (autobuses, camiones, grúas) con restricciones de dimensión: altura, anchura, largo y peso. Evita puentes bajos, túneles con límite y calles estrechas usando datos reales de OpenStreetMap.

## 📋 Descripción

Kavana BusRoad ayuda a transportistas y conductores de vehículos de gran tamaño a planificar rutas seguras según las dimensiones reales de su vehículo. A diferencia de Google Maps (que calcula rutas de coche), BusRoad aplica las restricciones del vehículo en cada tramo y muestra la comparación con la ruta convencional.

- **Frontend**: Vue 3 + Vite (**PWA instalable**, offline) desplegado en Vercel (`busroad.kavanasystems.com`)
- **Backend**: FastAPI (Python) desplegado en Fly.io (`busroad-api.kavanasystems.com`)
- **Motor de rutas**: [OpenRouteService](https://openrouteservice.org/) con perfil `driving-hgv` (vehículos pesados): aplica restricciones reales de altura, anchura, largo y peso en Europa usando datos de OpenStreetMap. Google Routes queda como respaldo de ruta estándar (NO aplica dimensiones fuera de EE.UU.).
- **Navegación**: los botones de Google Maps/Waze usan waypoints extraídos del polyline de la ruta segura, forzando al navegador a seguir el itinerario calculado.
- **Paradas intermedias**: hasta 20 paradas entre origen y destino (rutas escolares), con optimización opcional del orden (VROOM).

## 🛠️ Stack Tecnológico

| Área | Tecnologías |
|------|-------------|
| Frontend | Vue 3, Vite, TypeScript |
| Backend | FastAPI, Uvicorn, Pydantic, httpx |
| Infra | Docker, Fly.io (machines), Let's Encrypt |
| Despliegue | Vercel (frontend), Fly.io (backend) |
| API externa | OpenRouteService (`driving-hgv`, geocoding) · Google Routes (fallback) |
| DNS | Namecheap (A + AAAA `busroad-api` → Fly.io, `_acme-challenge` CNAME) |

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
├── frontend/           # PWA Vue 3 + Vite (instalable, offline)
│   ├── src/App.vue     # Pestañas: Ruta (origen, destino, paradas), Vehículo, Favoritos, Configuración
│   ├── src/components/RouteMap.vue  # Mapa Leaflet con la geometría de ORS
│   ├── public/
│   │   ├── manifest.webmanifest     # Manifest PWA (iconos 192/512, theme #a78bfa)
│   │   ├── sw.js                    # Service worker (app shell offline)
│   │   └── icon-*.png / favicon.png / apple-touch-icon.png
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

## 🚀 Despliegue en Fly.io

El backend corre en **Fly.io** (machines). Configuración en `backend/fly.toml` (región `cdg`, auto-stop cuando está en reposo para coste cero).

```bash
cd backend

# 1. Login (token de organización si hay SSO)
flyctl auth login

# 2. Crear la app (una vez)
flyctl apps create busroad-api

# 3. Secrets con las claves de API
flyctl secrets set --app busroad-api \
  ORS_API_KEY=TU_CLAVE_ORS \
  GOOGLE_API_KEY=TU_CLAVE_GOOGLE

# 4. Desplegar (build remoto)
flyctl deploy --app busroad-api --remote-only

# 5. Certificado para el dominio custom (una vez, tras crear A/AAAA en Namecheap)
flyctl certs add busroad-api.kavanasystems.com
```

DNS en Namecheap para `busroad-api.kavanasystems.com`:

| Tipo | Host | Valor |
|---|---|---|
| A | busroad-api | IP de la app (`flyctl ips list`) |
| AAAA | busroad-api | IPv6 de la app (`flyctl ips list`) |
| CNAME | _acme-challenge.busroad-api | `busroad-api.kavanasystems.com.<app>.<hash>.flydns.net` (lo indica `flyctl certs setup`) |

> **Histórico**: el backend estuvo inicialmente en Kubernetes (k3s) en el VPS de laboratorio. Se migró a Fly.io para que ningún proyecto dependa del VPS (laboratorio de trabajo, no producción). El manifiesto k8s quedó en `k8s/` como referencia del experimento.

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
| POST | `/api/v1/ruta` | Calcula ruta segura + convencional dado origen, destino, paradas opcionales (`paradas[]`, hasta 20), optimización de orden (`optimizar`) y dimensiones del vehículo |

Payload de ejemplo:

```json
{
  "origen": "Estació del Nord, Valencia",
  "destino": "IES Cheste, Valencia",
  "paradas": ["CEIP Cervantes, Cheste, Valencia", "CEIP La Paz, Cheste, Valencia"],
  "optimizar": false,
  "vehiculo": { "alto_m": 3.5, "ancho_m": 2.5, "largo_m": 12.0, "peso_kg": 12000 }
}
```

`optimizar: true` reordena las paradas al recorrido más corto (VROOM, ver ADR 006).

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

## 🛑 Paradas intermedias (rutas escolares y repartos)

Pensado para el caso real de rutas de colegios (recogida de niños en N paradas hasta el colegio) y repartos multi-punto:

1. Pulsa **"➕ Añadir parada"** debajo del destino (hasta 20 paradas).
2. Cada parada acepta una dirección completa (igual que origen/destino) y se puede reordenar con **↑ ↓** o eliminar con **✕**.
3. Con 2+ paradas aparece el checkbox **"Optimizar orden"**: si está activo, el backend reordena las paradas al recorrido más corto (problema del viajante resuelto con el endpoint `/optimization` de ORS, VROOM). Verificado en producción: orden malo 132,1 km → optimizado 90,9 km (**41 km y 37 min de ahorro**).
4. El mapa Leaflet dibuja la ruta completa pasando por todas las paradas, y la navegación (Google/Waze) se genera sobre ese polyline final.

Detalle en [ADR 006](docs/adr/006-paradas-intermedias-optimizacion-vroom.md).

## 📱 Instalación como PWA

La app es una PWA instalable: funciona offline (app shell cacheado por service worker), con icono propio y a pantalla completa.

- **Android/Chrome**: abre `https://busroad.kavanasystems.com` → menú ⋮ → "Instalar aplicación".
- **iPhone/Safari**: abre la app → Compartir → "Añadir a pantalla de inicio".
- **PC/Chrome**: icono de instalación en la barra de direcciones.

La API y los tiles del mapa se mantienen en vivo (no se cachean): el offline cubre abrir la app y la interfaz, el cálculo de rutas requiere conexión.

## 📐 Decisiones de arquitectura (ADRs)

Las decisiones importantes se documentan como ADRs en [`docs/adr/`](docs/adr/):

| ADR | Decisión |
|---|---|
| [001](docs/adr/001-motor-planificacion-vs-navegacion.md) | Separación entre motor de planificación (ORS + Leaflet) y motor de navegación (Google/Waze como clientes) |
| [002](docs/adr/002-preservacion-geometria-ors-cliente.md) | Preservación de la geometría completa de ORS en el cliente (Leaflet la representa íntegramente) |
| [003](docs/adr/003-seleccion-waypoints-cambios-direccion.md) | Selección de waypoints basada en cambios de dirección > 12° (no muestreo uniforme) |
| [004](docs/adr/004-comparacion-ruta-estandar-vs-hgv.md) | Comparación simultánea de ruta estándar y ruta HGV como decisión de UX + técnica |
| [005](docs/adr/005-backend-flyio-independiente-vps.md) | Backend en Fly.io: servicio independiente del VPS de laboratorio |
| [006](docs/adr/006-paradas-intermedias-optimizacion-vroom.md) | Paradas intermedias + optimización de orden con VROOM (rutas escolares) |

## 📚 Próximos pasos

- [x] **Migrar backend de k3s (VPS) a Fly.io** (hecho 2026-08-05): ADR 005, DNS actualizado, certificado emitido. Pendiente: limpiar pod k3s + vhost nginx del VPS.
- [x] **Dominio propio para el frontend** (hecho 2026-08-05): `busroad.kavanasystems.com` con HTTPS en Vercel.
- [x] **PWA instalable** (hecho 2026-08-06): manifest + service worker + iconos propios.
- [x] **Paradas intermedias + optimización VROOM** (hecho 2026-08-06): ADR 006.
- [ ] APK para el hermano (Capacitor + Android Studio) con ajustes: vehículo precargado, tema, quitar comparación
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
