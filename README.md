# Kavana BusRoad

Aplicación PWA para cálculo de rutas de vehículos grandes (autobuses, camiones, grúas, etc.) con restricciones de dimensión y paso bajo puentes/túneles. 

## 📋 Descripción

Kavana BusRoad ayuda a transportistas y conductores de vehículos de gran tamaño a planificar rutas evitando obstáculos según las dimensiones del vehículo, ancho, peso y altura libre. 

- **Frontend**: Vue 3 + Vite (PWA, desplegado en Vercel)
- **Backend**: FastAPI (Python) que usa la [Google Routes API](https://developers.google.com/maps/documentation/routes) para calcular rutas con restricciones de vehículos.
- **Motor de rutas**: Cuando la `GOOGLE_API_KEY` de API_KEY` está configurada, consulta Google Routes; si no, devuelve una ruta de ejemplo (mock) para permitir desarrollo sin costo.
- **Despliegue**: Backend listo para desplegar en cualquier proveedor que soporte contenedores (Render, Fly.io, etc.) o VMs. Frontend desplegado en Vercel.

## 🛠️ Stack Tecnológico

| Área | Tecnologías |
|------|-------------|
| Frontend | Vue 3, Vite, TypeScript, Pinia, TailwindCSS, Workbox (PWA) |
| Backend | FastAPI, Uvicorn, Pydantic, python-dotenv |
| Infra | Docker (opcional), GitHub Actions (CI) |
| Despliegue | Vercel (frontend), cualquier host para backend |
| API externa | Google Routes API, Geocoding API |
| Testing | pytest (backend), Vitest/Jest (frontend opcional) |

## 📁 Estructura del proyecto

```
kavana-busroad/
├── backend/          # Código fuente del API (FastAPI)
│   ├── app/
│   │   ├── main.py           # Entrypoint de la API
│   │   ├── motor/            # Lógica de cálculo de rutas (llama a Google Routes o mock)
│   │   └── ...
│   ├── .env.example          # Variables de entorno de ejemplo
│   ├── requirements.txt      # Dependencias Python
│   └── ... 
├── frontend/           # Código fuente de la PWA (Vue 3 + Vite)
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── router/
│   │   └── store/
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── .gitignore
└── README.md
```

## ⚙️ Configuración

### Variables de entorno (backend)

Copia `.env.example` a `.env` y completa los valores:

```dotenv
# Clave de Google Cloud con las siguientes APIs activadas:
# - Routes API
# - Geocoding API
GOOGLE_API_KEY=tu_clave_aqui

# Puerto donde escuchará el servidor (default: 8000)
PORT=8000
```

> **Nota**: Si `GOOGLE_API_KEY` no está definida, el endpoint de ruta devolverá una respuesta mock para permitir desarrollo y pruebas sin costo.

### Dependencias

#### Backend
```bash
cd backend
# Se recomienda usar un entorno virtual
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

#### Frontend
```bash
cd frontend
npm install   # o yarn / pnpm
```

## ▶️ Ejecutar en desarrollo

### Backend
```bash
cd backend
# Asegúrate de tener .env con GOOGLE_API_KEY (o deja vacío para mock)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
La API quedará disponible en `http://localhost: mock)
uvicorn app.main:app --reload
```
El servidor se ejecutará en `http://localhost:8000`.

### Frontend
```bash
cd frontend
npm run dev   # o: vite
```
La aplicación PWA se servirá en `http://localhost:5173` (puede variar según Vite).  
El frontend está configurado para llamar a la API en `http://localhost:8000` (ver `src/services/api.ts` o similar).

## 🐳 Docker (opcional)

Si prefieres correr el backend en un contenedor:

```bash
# Desde la raíz del proyecto
docker build -t kavana-busroad-backend -f backend/Dockerfile .
docker run -p 8000:8000 --env-file backend/.env kavana-busroad-backend
```

*(Actualmente no hay un `Dockerfile` en el repositorio; puedes crear uno basado en la imagen oficial de python:3.12-slim.)*

## 🧪 Health Check

Una vez el backend está corriendo, verifica su estado:

```bash
curl http://localhost:8000/api/v1/health
```

Respuesta esperada:
```json
{
  "status": "ok",
  "motor": "google-routes"   // o "mock" si no hay GOOGLE_API_KEY
}
```

## 📖 Documentación de la API

Cuando el backend está en ejecución, la documentación interactiva Swagger UI está disponible en:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Los endpoints principales son:
- `GET /api/v1/health` – Estado del servicio.
- `POST /api/v1/route` – Calcula una ruta dada una origen, destino y dimensiones del vehículo. (Ver esquema en Swagger para el payload exacto.)

## 🚀 Despliegue

### Frontend (Vercel)
1. Fork/repositorio en tu cuenta de GitHub.
2. En Vercel, importa el proyecto y apunta al directorio `frontend/`.
3. Configura las variables de entorno (si el frontend necesita alguna, por ahora ninguna).
4. Vercel detectará automáticamente que es un proyecto Vite y lo desplegará.

### Backend (ejemplo con Render)
1. Crea un nuevo **Web Service** en Render.
2. Conecta tu repositorio y establece el **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. En la sección de **Environment**, agrega:
   - `GOOGLE_API_KEY` (valor secreto)
   - `PORT` (Render lo provee automáticamente, pero puedes dejarlo vacío para que use el del .env)
5. Despliega.

## 📚 Próximos pasos / Mejoras

- [ ] Añadir pruebas unitarias y de integración (backend.
- [ ]**
- [ ] Docker** oficial para el yun CI/CD para pruebas a y despliegue automático.
- [ ] Ampliar el motor de rutas para soportar otros proveedores (ORS, Mapbox, etc.) como fallback.
- [ ] Internacionalización (i18n) de la interfaz.
- [ ] Sistema de autenticación y guardado de rutas favoritas.

## 📄 Licencia

Este proyecto es privado y pertenece a Kavana Systems. No se redistribuye sin permiso explícito.

## 🙏 Créditos

- Inspirado por los desafíos reales de transporte de carga sobredimensionada.
- Utiliza Google Routes API para cálculo de rutas con restricciones de vehículos.
- Desarrollado con ☕ y 🚍 por el equipo de Kavana.

--- 

*README creado el 2025-08-04 por Hermes Agent siguiendo los estándares de Kavana Engineering.*