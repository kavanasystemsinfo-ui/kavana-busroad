# Despliegue Kubernetes (k3s)

## Arquitectura
```
Internet (busroad-api.kavanasystems.com)
    → nginx (VPS, TLS Let's Encrypt, puerto 443)
    → Service NodePort :30080
    → Pod backend (FastAPI, imagen kavana-busroad-backend:0.1.0)
```

## Nota importante (pitfall resuelto)
El LoadBalancer de Traefik que trae k3s capturaba el tráfico de los puertos 80/443
antes que nginx (reglas KUBE-EXT). Se convirtió a ClusterIP para que nginx sea
el único gateway del VPS. Si se reinstala k3s, repetir:
`kubectl patch svc traefik -n kube-system -p '{"spec":{"type":"ClusterIP"}}'`

## Comandos útiles
- `kubectl apply -f k8s/backend.yaml` → despliega Deployment + Service
- `kubectl rollout restart deployment/busroad-backend` → reinicia tras nueva imagen
- `kubectl logs deploy/busroad-backend -f` → logs
- Cargar imagen nueva: `docker build` + `docker save | k3s ctr images import -` + restart

## Secret
La GOOGLE_API_KEY se lee del Secret `busroad-secrets` (key google_api_key).
Crear con: `kubectl create secret generic busroad-secrets --from-literal=google_api_key=...`
Sin el Secret, el backend responde en modo mock.
