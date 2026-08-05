<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'

// ---------- Estado de pestañas ----------
const activeTab = ref<'ruta' | 'vehiculo' | 'favoritos' | 'config'>('ruta')
const tabs = [
  { id: 'ruta' as const, label: 'Ruta', icon: '🧭' },
  { id: 'vehiculo' as const, label: 'Vehículo', icon: '🚌' },
  { id: 'favoritos' as const, label: 'Favoritos', icon: '⭐' },
  { id: 'config' as const, label: 'Config.', icon: '⚙️' }
]

// ---------- Estado de ruta ----------
const origen = ref('')
const destino = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const result = ref<any | null>(null)

const dimensiones = ref({
  largo_m: 12.0,
  ancho_m: 2.5,
  alto_m: 3.5,
  peso_kg: 12000
})

// ---------- Vehículos guardados (localStorage) ----------
interface Vehiculo {
  id: string
  nombre: string
  largo_m: number
  ancho_m: number
  alto_m: number
  peso_kg: number
}

const vehiculos = ref<Vehiculo[]>([])
const vehiculoActivoId = ref<string | null>(null)

// ---------- Favoritos (localStorage) ----------
interface Favorito {
  id: string
  origen: string
  destino: string
  fecha: string
  distancia_km?: number
  duracion_min?: number
}

const favoritos = ref<Favorito[]>([])

// ---------- Configuración (localStorage) ----------
interface Config {
  tema: 'violeta' | 'azul' | 'verde' | 'naranja' | 'oscuro'
  tamanoFuente: 'pequeño' | 'normal' | 'grande' | 'muy grande'
}

const config = ref<Config>({
  tema: 'violeta',
  tamanoFuente: 'normal'
})

const TEMAS: Record<Config['tema'], { nombre: string; primary: string; primary2: string; glow: string }> = {
  violeta: { nombre: 'Violeta', primary: '#a78bfa', primary2: '#8b5cf6', glow: 'rgba(167,139,250,0.15)' },
  azul: { nombre: 'Azul', primary: '#60a5fa', primary2: '#3b82f6', glow: 'rgba(96,165,250,0.15)' },
  verde: { nombre: 'Verde', primary: '#4ade80', primary2: '#22c55e', glow: 'rgba(74,222,128,0.15)' },
  naranja: { nombre: 'Naranja', primary: '#fb923c', primary2: '#f97316', glow: 'rgba(251,146,60,0.15)' },
  oscuro: { nombre: 'Oscuro', primary: '#94a3b8', primary2: '#64748b', glow: 'rgba(148,163,184,0.12)' }
}

// ---------- API ----------
const API_URL = import.meta.env.VITE_API_URL || 'https://busroad-api.kavanasystems.com'

// URLs para abrir la ruta en apps de navegación (se actualizan tras calcular)
const mapsUrl = ref('')
const wazeUrl = ref('')
const mapsSeguraUrl = ref('')
const wazeSeguraUrl = ref('')

// ---------- Computed ----------
const diferenciaKm = computed(() => {
  if (!result.value || !result.value.convencional) return 0
  return Math.round((result.value.convencional.distancia_km - result.value.distancia_km) * 10) / 10
})

// ---------- localStorage ----------
const LS_KEYS = {
  vehiculos: 'busroad_vehiculos',
  vehiculoActivo: 'busroad_vehiculo_activo',
  favoritos: 'busroad_favoritos',
  config: 'busroad_config'
}

function cargarPersistencia() {
  try {
    const v = localStorage.getItem(LS_KEYS.vehiculos)
    if (v) vehiculos.value = JSON.parse(v)
    const va = localStorage.getItem(LS_KEYS.vehiculoActivo)
    if (va) vehiculoActivoId.value = JSON.parse(va)
    const f = localStorage.getItem(LS_KEYS.favoritos)
    if (f) favoritos.value = JSON.parse(f)
    const c = localStorage.getItem(LS_KEYS.config)
    if (c) config.value = { ...config.value, ...JSON.parse(c) }
  } catch (e) {
    console.error('Error cargando localStorage', e)
  }
}

watch(vehiculos, v => localStorage.setItem(LS_KEYS.vehiculos, JSON.stringify(v)), { deep: true })
watch(vehiculoActivoId, v => localStorage.setItem(LS_KEYS.vehiculoActivo, JSON.stringify(v)))
watch(favoritos, f => localStorage.setItem(LS_KEYS.favoritos, JSON.stringify(f)), { deep: true })
watch(config, c => localStorage.setItem(LS_KEYS.config, JSON.stringify(c)), { deep: true })

onMounted(cargarPersistencia)

// ---------- Gestión de vehículos ----------
function guardarVehiculo() {
  const nombre = prompt('Nombre del vehículo (ej: Autobús 55 plazas, Furgoneta 3,5t...):')?.trim()
  if (!nombre) return
  const nuevo: Vehiculo = {
    id: crypto.randomUUID(),
    nombre,
    largo_m: dimensiones.value.largo_m,
    ancho_m: dimensiones.value.ancho_m,
    alto_m: dimensiones.value.alto_m,
    peso_kg: dimensiones.value.peso_kg
  }
  vehiculos.value.push(nuevo)
  vehiculoActivoId.value = nuevo.id
}

function cargarVehiculo(id: string) {
  const v = vehiculos.value.find(x => x.id === id)
  if (v) {
    dimensiones.value = {
      largo_m: v.largo_m,
      ancho_m: v.ancho_m,
      alto_m: v.alto_m,
      peso_kg: v.peso_kg
    }
    vehiculoActivoId.value = id
  }
}

function eliminarVehiculo(id: string) {
  vehiculos.value = vehiculos.value.filter(x => x.id !== id)
  if (vehiculoActivoId.value === id) vehiculoActivoId.value = null
}

// ---------- Gestión de favoritos ----------
function guardarFavorito() {
  if (!result.value) return
  const nuevo: Favorito = {
    id: crypto.randomUUID(),
    origen: result.value.origen || origen.value,
    destino: result.value.destino || destino.value,
    fecha: new Date().toLocaleDateString('es-ES'),
    distancia_km: result.value.distancia_km,
    duracion_min: result.value.duracion_min
  }
  favoritos.value.push(nuevo)
}

function usarFavorito(f: Favorito) {
  origen.value = f.origen
  destino.value = f.destino
  activeTab.value = 'ruta'
}

function eliminarFavorito(id: string) {
  favoritos.value = favoritos.value.filter(x => x.id !== id)
}

// ---------- Temas y fuentes ----------
const fuenteClasses: Record<Config['tamanoFuente'], string> = {
  'pequeño': 'font-pequeno',
  'normal': 'font-normal',
  'grande': 'font-grande',
  'muy grande': 'font-muy-grande'
}

const temaActual = computed(() => TEMAS[config.value.tema])

// ---------- Decodificación de polyline ----------
const decodePolyline = (encoded: string): [number, number][] => {
  const points: [number, number][] = []
  let index = 0, lat = 0, lng = 0
  while (index < encoded.length) {
    let b: number, shift = 0, result = 0
    do {
      b = encoded.charCodeAt(index++) - 63
      result |= (b & 0x1f) << shift
      shift += 5
    } while (b >= 0x20)
    const dlat = result & 1 ? ~(result >> 1) : result >> 1
    lat += dlat
    shift = 0; result = 0
    do {
      b = encoded.charCodeAt(index++) - 63
      result |= (b & 0x1f) << shift
      shift += 5
    } while (b >= 0x20)
    const dlng = result & 1 ? ~(result >> 1) : result >> 1
    lng += dlng
    points.push([lat / 1e5, lng / 1e5])
  }
  return points
}

const sampleWaypoints = (points: [number, number][], n: number): [number, number][] => {
  if (points.length <= n) return points.slice(1, -1)
  const step = (points.length - 1) / (n - 1)
  const out: [number, number][] = []
  for (let i = 0; i < n; i++) {
    out.push(points[Math.round(i * step)])
  }
  return out.slice(1, -1)
}

const abrirEnMapas = (origen: string, destino: string, polyline?: string) => {
  const o = encodeURIComponent(origen)
  const d = encodeURIComponent(destino)
  mapsUrl.value = `https://www.google.com/maps/dir/?api=1&origin=${o}&destination=${d}&travelmode=driving`
  wazeUrl.value = `https://www.waze.com/ul?q=${d}&navigate=yes`
  if (polyline) {
    const pts = sampleWaypoints(decodePolyline(polyline), 8)
    if (pts.length > 0) {
      const wps = pts.map(p => `${p[0]},${p[1]}`).join('|')
      mapsSeguraUrl.value = `https://www.google.com/maps/dir/?api=1&origin=${o}&destination=${d}&waypoints=${wps}&travelmode=driving`
      wazeSeguraUrl.value = `https://www.waze.com/ul?q=${d}&navigate=yes`
    }
  }
}

const calcularRuta = async () => {
  if (!origen.value.trim() || !destino.value.trim()) {
    error.value = 'Escribe un origen y un destino para calcular la ruta.'
    return
  }
  loading.value = true
  error.value = null
  result.value = null
  try {
    const response = await fetch(`${API_URL}/api/v1/ruta`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origen: origen.value,
        destino: destino.value,
        vehiculo: dimensiones.value
      })
    })
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${await response.text()}`)
    }
    const data = await response.json()
    result.value = data
    abrirEnMapas(origen.value, destino.value, data.polyline)
  } catch (e: any) {
    error.value = e.message || 'Error desconocido'
    console.error(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="app" :class="[fuenteClasses[config.tamanoFuente]]" :data-tema="config.tema"
    :style="{
      '--tema-primary': temaActual.primary,
      '--tema-primary2': temaActual.primary2,
      '--tema-glow': temaActual.glow
    }">
    <main class="content">
      <!-- ══════════ PESTAÑA RUTA ══════════ -->
      <section v-if="activeTab === 'ruta'" class="tab-page">
        <h1 class="app-title">Kavana BusRoad</h1>
        <p class="app-subtitle">Planificador de rutas para vehículos pesados</p>

        <div class="form-section">
          <label>Origen</label>
          <input v-model="origen" type="text" placeholder="Ej: Estació del Nord, Valencia" @keyup.enter="calcularRuta" />
        </div>
        <div class="form-section">
          <label>Destino</label>
          <input v-model="destino" type="text" placeholder="Ej: Higueruelas, Valencia" @keyup.enter="calcularRuta" />
        </div>

        <div class="form-section">
          <label>Vehículo (dimensiones)</label>
          <select v-if="vehiculos.length > 0" :value="vehiculoActivoId || ''" @change="cargarVehiculo(($event.target as HTMLSelectElement).value)">
            <option value="">— Dimensiones manuales —</option>
            <option v-for="v in vehiculos" :key="v.id" :value="v.id">{{ v.nombre }}</option>
          </select>
          <div class="dimensions-grid">
            <div><label>Longitud (m)</label><input v-model.number="dimensiones.largo_m" type="number" step="0.1" min="1" /></div>
            <div><label>Anchura (m)</label><input v-model.number="dimensiones.ancho_m" type="number" step="0.1" min="1" /></div>
            <div><label>Altura (m)</label><input v-model.number="dimensiones.alto_m" type="number" step="0.1" min="1" /></div>
            <div><label>Peso (kg)</label><input v-model.number="dimensiones.peso_kg" type="number" step="100" min="1000" /></div>
          </div>
          <button class="btn btn-ghost btn-sm" @click="guardarVehiculo">💾 Guardar este vehículo</button>
        </div>

        <div class="form-section">
          <button class="btn btn-primary btn-lg" :disabled="loading" @click="calcularRuta">
            {{ loading ? 'Calculando...' : 'Calcular Ruta' }}
          </button>
        </div>

        <div v-if="error" class="error">⚠️ {{ error }}</div>

        <div v-if="result" class="result">
          <div class="result-header">
            <h2>Resultado de la ruta</h2>
            <button class="btn btn-ghost btn-sm" @click="guardarFavorito">⭐ Añadir a favoritos</button>
          </div>
          <p class="result-origen-destino"><strong>{{ result.origen }}</strong> → <strong>{{ result.destino }}</strong></p>

          <div class="ruta-segura">
            <h3>🚌 Ruta para tu vehículo</h3>
            <p><strong>{{ result.distancia_km }}</strong> km · <strong>{{ result.duracion_min }}</strong> min</p>
            <p class="motor-note">Motor: {{ result.motor }}</p>
          </div>

          <div v-if="result.convencional" class="ruta-convencional">
            <h3>🚗 Ruta convencional (coche)</h3>
            <p><strong>{{ result.convencional.distancia_km }}</strong> km · <strong>{{ result.convencional.duracion_min }}</strong> min</p>
            <p v-if="diferenciaKm > 0" class="diff-note">⚠️ Tu ruta es {{ diferenciaKm }} km más larga pero evita vías no aptas para tu vehículo</p>
            <p v-else-if="diferenciaKm < 0" class="diff-note">✅ Tu ruta es incluso {{ Math.abs(diferenciaKm) }} km más corta</p>
            <p v-else class="diff-note">✅ Coinciden: no hay obstáculos para tu vehículo en esta ruta</p>
          </div>

          <div class="maps-actions">
            <a v-if="mapsSeguraUrl" class="maps-btn" :href="mapsSeguraUrl" target="_blank" rel="noopener">🚌 Navegar por TU ruta (Google Maps)</a>
            <a v-if="wazeSeguraUrl" class="maps-btn" :href="wazeSeguraUrl" target="_blank" rel="noopener">🚌 Navegar por TU ruta (Waze)</a>
          </div>
          <p class="maps-note">Estos botones fuerzan tu ruta segura con puntos de paso.</p>

          <div class="maps-actions">
            <a class="maps-btn alt" :href="mapsUrl" target="_blank" rel="noopener">🚗 Ver ruta convencional en Google Maps</a>
            <a class="maps-btn alt" :href="wazeUrl" target="_blank" rel="noopener">🚗 Ruta convencional (Waze)</a>
          </div>
          <p class="maps-note">Google Maps no conoce las restricciones de tu vehículo.</p>

          <h3>Pasos</h3>
          <ol>
            <li v-for="(paso, index) in result.pasos" :key="index">{{ paso }}</li>
          </ol>

          <h3 v-if="result.riesgos && result.riesgos.length > 0">Riesgos</h3>
          <ul v-if="result.riesgos && result.riesgos.length > 0">
            <li v-for="(riesgo, index) in result.riesgos" :key="index">
              <strong>{{ riesgo.nombre }}</strong> ({{ riesgo.tipo }}): {{ riesgo.descripcion }}
            </li>
          </ul>
          <p v-else class="no-riesgos">✅ Ruta calculada evitando las restricciones de tu vehículo</p>
        </div>
      </section>

      <!-- ══════════ PESTAÑA VEHÍCULO ══════════ -->
      <section v-if="activeTab === 'vehiculo'" class="tab-page">
        <h1 class="app-title">🚌 Mi flota</h1>
        <p class="app-subtitle">Guarda los vehículos que usas habitualmente</p>

        <div class="form-section">
          <label>Longitud (m)</label>
          <input v-model.number="dimensiones.largo_m" type="number" step="0.1" min="1" />
        </div>
        <div class="form-section">
          <label>Anchura (m)</label>
          <input v-model.number="dimensiones.ancho_m" type="number" step="0.1" min="1" />
        </div>
        <div class="form-section">
          <label>Altura (m)</label>
          <input v-model.number="dimensiones.alto_m" type="number" step="0.1" min="1" />
        </div>
        <div class="form-section">
          <label>Peso (kg)</label>
          <input v-model.number="dimensiones.peso_kg" type="number" step="100" min="1000" />
        </div>
        <button class="btn btn-primary" @click="guardarVehiculo">💾 Guardar vehículo</button>

        <h2 class="section-title">Vehículos guardados</h2>
        <div v-if="vehiculos.length === 0" class="empty-state">
          <p>Aún no has guardado ningún vehículo.</p>
        </div>
        <div v-for="v in vehiculos" :key="v.id" class="vehiculo-card" :class="{ activo: v.id === vehiculoActivoId }">
          <div class="vehiculo-info">
            <strong>{{ v.nombre }}</strong>
            <span>{{ v.alto_m }} m alto · {{ v.ancho_m }} m ancho · {{ v.largo_m }} m largo · {{ v.peso_kg }} kg</span>
          </div>
          <div class="vehiculo-actions">
            <button class="btn btn-ghost btn-sm" @click="cargarVehiculo(v.id)">Usar</button>
            <button class="btn btn-danger btn-sm" @click="eliminarVehiculo(v.id)">🗑️</button>
          </div>
        </div>
      </section>

      <!-- ══════════ PESTAÑA FAVORITOS ══════════ -->
      <section v-if="activeTab === 'favoritos'" class="tab-page">
        <h1 class="app-title">⭐ Favoritos</h1>
        <p class="app-subtitle">Tus rutas guardadas</p>

        <div v-if="favoritos.length === 0" class="empty-state">
          <p>No tienes rutas favoritas todavía.</p>
          <p class="empty-hint">Calcula una ruta en la pestaña Ruta y pulsa "⭐ Añadir a favoritos".</p>
        </div>

        <div v-for="f in favoritos" :key="f.id" class="favorito-card">
          <div class="favorito-info">
            <strong>{{ f.origen }}</strong>
            <span>→ {{ f.destino }}</span>
            <span v-if="f.distancia_km" class="favorito-meta">{{ f.distancia_km }} km · {{ f.duracion_min }} min · {{ f.fecha }}</span>
            <span v-else class="favorito-meta">{{ f.fecha }}</span>
          </div>
          <div class="vehiculo-actions">
            <button class="btn btn-ghost btn-sm" @click="usarFavorito(f)">Usar</button>
            <button class="btn btn-danger btn-sm" @click="eliminarFavorito(f.id)">🗑️</button>
          </div>
        </div>
      </section>

      <!-- ══════════ PESTAÑA CONFIGURACIÓN ══════════ -->
      <section v-if="activeTab === 'config'" class="tab-page">
        <h1 class="app-title">⚙️ Configuración</h1>

        <h2 class="section-title">Tema (paleta de colores)</h2>
        <div class="tema-grid">
          <button v-for="t in TEMAS" :key="t.nombre" class="tema-btn" :class="{ activo: config.tema === t.nombre.toLowerCase() }"
            :style="{ '--t': t.primary, '--t2': t.primary2 }" @click="config.tema = t.nombre.toLowerCase() as Config['tema']">
            <span class="tema-dot"></span>{{ t.nombre }}
          </button>
        </div>

        <h2 class="section-title">Tamaño de fuente</h2>
        <div class="tema-grid">
          <button v-for="f in ['pequeño', 'normal', 'grande', 'muy grande']" :key="f"
            class="btn btn-ghost" :class="{ activo: config.tamanoFuente === f }"
            @click="config.tamanoFuente = f as Config['tamanoFuente']">
            {{ f }}
          </button>
        </div>

        <div class="info-box">
          <p>💡 Los cambios se guardan automáticamente en este dispositivo.</p>
        </div>
      </section>
    </main>

    <!-- ══════════ BARRA INFERIOR DE NAVEGACIÓN ══════════ -->
    <nav class="bottom-nav">
      <button v-for="t in tabs" :key="t.id" class="nav-btn" :class="{ activo: activeTab === t.id }" @click="activeTab = t.id">
        <span class="nav-icon">{{ t.icon }}</span>
        <span class="nav-label">{{ t.label }}</span>
      </button>
    </nav>
  </div>
</template>

<style>
:root {
  --tema-primary: #a78bfa;
  --tema-primary2: #8b5cf6;
  --tema-glow: rgba(167, 139, 250, 0.15);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0f1117;
  color: #e5e7eb;
  -webkit-font-smoothing: antialiased;
}

.app {
  max-width: 560px;
  margin: 0 auto;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #12141c 0%, #0f1117 100%);
}

.content {
  flex: 1;
  padding: 24px 20px 100px;
  overflow-y: auto;
}

/* Fuentes */
.font-pequeno { font-size: 13px; }
.font-normal { font-size: 15px; }
.font-grande { font-size: 17px; }
.font-muy-grande { font-size: 19px; }

.app-title {
  font-size: 1.6em;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-bottom: 4px;
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.app-subtitle {
  color: #9ca3af;
  font-size: 0.95em;
  margin-bottom: 24px;
}

.section-title {
  font-size: 1.1em;
  font-weight: 700;
  margin: 24px 0 12px;
  color: #e5e7eb;
}

.form-section { margin-bottom: 16px; }

.form-section label {
  display: block;
  font-size: 0.85em;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 6px;
}

input, select {
  width: 100%;
  padding: 12px 14px;
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 10px;
  color: #e5e7eb;
  font-size: 1em;
  outline: none;
  transition: border-color 0.2s;
}

input:focus, select:focus { border-color: var(--tema-primary); }

.dimensions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}

.dimensions-grid label { font-size: 0.75em; }

/* Botones */
.btn {
  border: none;
  border-radius: 10px;
  padding: 12px 18px;
  font-size: 0.95em;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary {
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  color: #0f1117;
  width: 100%;
}

.btn-primary:hover:not(:disabled) { filter: brightness(1.1); transform: translateY(-1px); }

.btn-lg { padding: 15px 20px; font-size: 1.05em; }

.btn-ghost {
  background: transparent;
  border: 1px solid #2a2e3a;
  color: #e5e7eb;
}

.btn-ghost:hover { border-color: var(--tema-primary); color: var(--tema-primary); }

.btn-danger { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }

.btn-danger:hover { background: rgba(239, 68, 68, 0.3); }

.btn-sm { padding: 8px 12px; font-size: 0.85em; border-radius: 8px; }

/* Resultados */
.error {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 12px 14px;
  border-radius: 10px;
  margin-top: 12px;
  font-size: 0.9em;
}

.result {
  margin-top: 20px;
  padding: 18px;
  background: #161922;
  border: 1px solid #262a38;
  border-radius: 14px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.result-header h2 { font-size: 1.15em; }

.result-origen-destino { color: #9ca3af; font-size: 0.9em; margin-bottom: 14px; }

.ruta-segura {
  padding: 14px;
  background: rgba(74, 222, 128, 0.08);
  border-left: 4px solid #4ade80;
  border-radius: 8px;
  margin-bottom: 10px;
}

.ruta-segura h3, .ruta-convencional h3 { font-size: 0.95em; margin-bottom: 4px; }

.ruta-convencional {
  padding: 14px;
  background: rgba(96, 165, 250, 0.08);
  border-left: 4px solid #60a5fa;
  border-radius: 8px;
  margin-bottom: 10px;
}

.motor-note { font-size: 0.8em; color: #6b7280; font-style: italic; }

.diff-note { font-size: 0.85em; font-weight: 600; margin-top: 6px; }

.maps-actions { display: flex; gap: 8px; margin: 12px 0; flex-wrap: wrap; }

.maps-btn {
  display: inline-block;
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  color: #0f1117;
  padding: 10px 14px;
  border-radius: 10px;
  text-decoration: none;
  font-size: 0.85em;
  font-weight: 600;
  transition: filter 0.2s;
}

.maps-btn:hover { filter: brightness(1.1); }

.maps-btn.alt { background: #1a1d27; color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.3); }

.maps-note { font-size: 0.78em; color: #6b7280; margin-top: 4px; font-style: italic; }

.result h3 { font-size: 1em; margin: 16px 0 8px; }

.result ol, .result ul { margin: 8px 0 8px 20px; }

.result li { margin-bottom: 6px; font-size: 0.92em; color: #d1d5db; }

.no-riesgos { color: #4ade80; font-size: 0.9em; margin-top: 8px; }

/* Vehículos */
.vehiculo-card, .favorito-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 14px;
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 12px;
  margin-bottom: 10px;
}

.vehiculo-card.activo { border-color: var(--tema-primary); }

.vehiculo-info, .favorito-info { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }

.vehiculo-info span, .favorito-info span { font-size: 0.82em; color: #9ca3af; }

.favorito-meta { font-size: 0.78em !important; color: #6b7280 !important; }

.vehiculo-actions { display: flex; gap: 6px; flex-shrink: 0; }

.empty-state { text-align: center; padding: 32px 16px; color: #9ca3af; }

.empty-hint { font-size: 0.85em; margin-top: 6px; color: #6b7280; }

/* Temas */
.tema-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; }

.tema-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  padding: 10px;
  border-radius: 10px;
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  color: #e5e7eb;
  font-size: 0.85em;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.tema-btn.activo { border-color: var(--tema-primary); }

.tema-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--t), var(--t2));
}

.info-box {
  margin-top: 24px;
  padding: 12px 14px;
  background: rgba(96, 165, 250, 0.08);
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 10px;
  font-size: 0.85em;
  color: #9ca3af;
}

/* Barra inferior */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 560px;
  display: flex;
  background: rgba(18, 20, 28, 0.95);
  backdrop-filter: blur(12px);
  border-top: 1px solid #262a38;
  padding: 6px 4px calc(6px + env(safe-area-inset-bottom));
  z-index: 100;
}

.nav-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  background: transparent;
  border: none;
  border-radius: 10px;
  color: #6b7280;
  cursor: pointer;
  transition: color 0.2s;
  font-family: inherit;
}

.nav-btn.activo { color: var(--tema-primary); }

.nav-icon { font-size: 1.3em; line-height: 1; }

.nav-label { font-size: 0.68em; font-weight: 600; }
</style>
