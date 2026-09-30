# ADR 008 — La PWA se sirve desde el backend en Fly.io (se retira Vercel)

**Estado:** Aceptado
**Fecha:** 2026-09-30
**Relacionado:** ADR 005 (backend en Fly.io), ADR 007 (decisiones por presupuesto)

## Contexto

El frontend (PWA Vue 3 + Vite) vivía en Vercel bajo `busroad.kavanasystems.com`.
Ese dominio pertenecía a un **proyecto paraguas de la organización**
(`kavana-systems-v3-frontend`) vinculado en git a **otro repositorio**
(`kavana-manufacturing`), no a `kavana-busroad`. La consecuencia era real y
comprobada: un push a este repositorio **no desplegaba nada**, así que el sitio
publicado podía quedar indefinidamente por detrás del código. Fue justo lo que
pasó: la PWA servida no contenía el buscador de direcciones que ya estaba en
`main`.

Con el paquete de robustez cerrado (caché y rate limit persistidos en disco,
geocodificación confirmada antes de enrutar) y el backend ya en Fly (ADR 005),
mantener un segundo proveedor obligaba a tocar CORS, dos planes y dos
despliegues para un producto de un solo usuario real.

## Decisión

El **backend FastAPI sirve la PWA desde la misma app de Fly**:

1. `backend/Dockerfile` pasa a ser multi-stage: un stage `node:22-slim` compila
   el frontend (`npm ci` + `vite build`) y un stage `python:3.12-slim` copia el
   resultado a `./static`.
2. `backend/app/main.py` monta `StaticFiles` en `/` **después** de los routers
   `/api/v1` (que tienen prioridad por orden de matcheo) y de forma
   **condicional**: si no hay `dist` (desarrollo local, tests) imprime un aviso
   y arranca solo como API, de modo que los tests unitarios no dependen del
   build del frontend.
3. `busroad.kavanasystems.com` (PWA) y `busroad-api.kavanasystems.com` (API)
   apuntan a la misma app, así que la PWA llama a la API **en el mismo origen**.

## Alternativas evaluadas

| Opción | Por qué se descartó |
|---|---|
| Arreglar el proyecto paraguas de Vercel (re-vincularlo a `kavana-busroad`) | Sigue siendo un proyecto compartido por varias apps: cambiar su configuración de git puede alterar los despliegues de las otras. No se toca infraestructura compartida a ciegas |
| Proyecto Vercel dedicado solo para BusRoad | Añade un segundo proveedor, un segundo plan y CORS entre orígenes a cambio de nada: el backend ya está en Fly |
| Netlify / Cloudflare Pages | Mismo problema que la opción anterior: otra plataforma, otro despliegue y otra superficie de fallo para una PWA de un usuario |
| Seguir en Vercel y desplegar a mano con la CLI | Arregla el síntoma, no la causa: mantiene la dependencia y el riesgo de que la PWA quede desincronizada del backend |

## Consecuencias

**Positivas**

- Un solo `flyctl deploy` publica PWA y API: **no pueden quedar desincronizadas**.
- Un solo proveedor y un solo plan gratuito, y la PWA se sirve en el mismo
  origen que la API (sin CORS en el caso normal).
- El despliegue deja de depender de una configuración de git ajena a este repo.

**Negativas / límites**

- La imagen Docker crece (incluye el build del frontend) y cada despliegue
  compila Node además de instalar Python: los despliegues tardan algo más.
- Sin CDN delante de la PWA: los estáticos los sirve la máquina de Fly (256 MB,
  con auto-stop). Para un usuario es irrelevante; con tráfico real, CDN delante.
- El DNS sigue siendo manual en Namecheap y hacen falta los registros
  `_acme-challenge` de cada hostname para que Fly emita el certificado.

## Señales de revisión

1. **Aparece tráfico real o más de un usuario**: poner un CDN delante de los
   estáticos y `min_machines_running > 0`.
2. **Otra app del paraguas se migra de Vercel**: replicar este patrón app por
   app, verificando el artefacto servido antes de tocar el DNS de cada
   subdominio.
3. **Cambian las IPs de Fly**: revisar el DNS manual de los dos subdominios.
