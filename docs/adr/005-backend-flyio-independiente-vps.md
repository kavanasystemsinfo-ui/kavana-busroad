# ADR 005 — Backend en Fly.io (servicio independiente del VPS de laboratorio)

**Estado:** Aceptado
**Fecha:** 2026-08-05

## Contexto

El backend de BusRoad se desplegó inicialmente en un clúster **k3s (Kubernetes)
del VPS personal**, detrás de nginx con certificado Let's Encrypt. El VPS es el
**laboratorio de trabajo** de Kavana Systems: se usa para experimentar con k3s,
nginx, scripts y herramientas. Los demás proyectos del portfolio (RouteAI,
Warehouse) ya viven en servicios independientes (Render, Neon, Vercel).

## Problema

Hacer que un proyecto de portfolio dependa del VPS personal mezcla dos cosas
que deberían estar separadas:

1. **El portfolio debe demostrar que un proyecto puede vivir solo**, con
   infraestructura estándar de la industria, igual que se haría para un
   cliente. Si el VPS se reinicia, se borra o se usa para otro experimento,
   la API de BusRoad cae sin que el proyecto lo controle.
2. **El CV se enriquece con más plataformas**: Fly.io es una plataforma de
   despliegue muy valorada (machines, regiones, auto-scaling a cero) que
   complementa a Render, Vercel y Neon ya usadas en otros proyectos.

Además, el despliegue en k3s exigía mantener el clúster, los secrets de k8s y
el vhost de nginx, añadiendo carga de mantenimiento al laboratorio.

## Alternativas evaluadas

1. **Dejar el backend en k3s (VPS)**: funcionaba, pero acoplaba el proyecto al
   laboratorio y no aportaba nada nuevo al stack. Descartada como producción.
2. **Render (como RouteAI/Warehouse)**: consistente con el resto del
   portfolio, pero no añadía ninguna plataforma nueva al CV.
3. **Fly.io**: plataforma moderna (machines de Firecracker, regiones, auto-stop
   a cero), gratuita para uso hobby, añade una plataforma nueva al stack y al
   CV. Elegida.

## Decisión

El backend de BusRoad se despliega en **Fly.io**:

- App `busroad-api` en la región `cdg` (Madrid deprecada en Fly al momento de
  la migración).
- Dockerfile existente reutilizado (build remoto con `--remote-only`).
- Secrets (`ORS_API_KEY`, `GOOGLE_API_KEY`) movidos de los Secrets de k8s a
  `flyctl secrets set`.
- `auto_stop_machines = "stop"`: la máquina se detiene en reposo y arranca
  bajo demanda, coste cero en hobby.
- El dominio `busroad-api.kavanasystems.com` se mantiene: A + AAAA en Namecheap
  apuntan a las IPs de Fly, y `_acme-challenge` CNAME para la validación ACME
  de Let's Encrypt. El frontend no cambia su URL de API.

## Consecuencias

**Positivas**

- Ningún proyecto del portfolio depende ya del VPS de laboratorio.
- Nuevo punto en el CV: **Fly.io** (machines, regiones, certs custom).
- Coste cero en el plan Hobby (auto-stop a cero).
- El frontend y la landing no cambian (misma URL `busroad-api.kavanasystems.com`).
- El manifiesto k3s queda en `k8s/` como referencia del experimento Kubernetes
  (también con valor en el CV).

**Negativas / límites**

- Fly.io Hobby: la máquina se detiene tras un periodo de inactividad, el
  primer request tras el reposo tarda unos segundos en arrancar (cold start).
- El plan Hobby comparte recursos (CPU/memoria limitados): suficiente para uso
  personal/portfolio; para producción real habría que pasar a plan de pago.
- La región `cdg` (París) está algo más lejos que Madrid para usuarios
  españoles, pero la latencia es despreciable para esta API.
- Los registros DNS requieren mantenimiento manual en Namecheap (A, AAAA y
  `_acme-challenge`): si cambian las IPs de Fly, hay que actualizarlos.
