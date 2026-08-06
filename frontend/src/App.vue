<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import RouteMap from './components/RouteMap.vue'

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
const paradas = ref<string[]>([])
const optimizar = ref(false)
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

const vehiculoActivo = computed(() =>
  vehiculos.value.find(v => v.id === vehiculoActivoId.value) || null
)

const formatoTiempo = (min: number): string => {
  const m = Math.round(min)
  const h = Math.floor(m / 60)
  const r = m % 60
  return h > 0 ? `${h}h ${r}m` : `${r}m`
}

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
const nombreNuevoVehiculo = ref('')
const guardadoOk = ref(false)

const pesoT = computed({
  get: () => Math.round((dimensiones.value.peso_kg / 1000) * 10) / 10,
  set: (t: number) => { dimensiones.value.peso_kg = Math.round(t * 1000) }
})

// Escalas del visualizador del bus
const busTransform = computed(() => {
  const h = dimensiones.value.alto_m
  const l = dimensiones.value.largo_m
  const heightScale = 0.8 + ((h - 2.0) / 3.0) * 0.4
  const lengthScale = 0.7 + ((l - 5.0) / 20.0) * 0.8
  return `scaleY(${heightScale.toFixed(2)}) scaleX(${lengthScale.toFixed(2)})`
})

function guardarVehiculo() {
  const nombre = nombreNuevoVehiculo.value.trim()
  if (!nombre) {
    error.value = 'Ponle un nombre al vehículo antes de guardarlo (ej: Autobús 55 plazas).'
    return
  }
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
  nombreNuevoVehiculo.value = ''
  guardadoOk.value = true
  setTimeout(() => { guardadoOk.value = false }, 2500)
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

// Extrae SOLO los vértices donde la ruta cambia de dirección (curvas, salidas, cruces)
// Así Google Maps se ve obligado a seguir el recorrido en los puntos críticos,
// y en tramos rectos no desperdiciamos waypoints.
const sampleWaypoints = (points: [number, number][], maxN: number = 8): [number, number][] => {
  if (points.length <= 2) return []
  const THRESHOLD = 12 // grados mínimos de cambio de dirección para contar como vértice
  const vertices: [number, number][] = []

  for (let i = 1; i < points.length - 1; i++) {
    const a = points[i - 1], b = points[i], c = points[i + 1]
    const ang1 = Math.atan2(b[0] - a[0], b[1] - a[1])
    const ang2 = Math.atan2(c[0] - b[0], c[1] - b[1])
    let diff = Math.abs(ang2 - ang1) * 180 / Math.PI
    if (diff > 180) diff = 360 - diff
    if (diff > THRESHOLD) vertices.push(b)
  }

  // Si hay demasiados vértices (ruta muy tortuosa), muestrear uniformemente entre ellos
  let chosen: [number, number][]
  if (vertices.length <= maxN) {
    chosen = vertices
  } else {
    chosen = []
    const step = (vertices.length - 1) / (maxN - 1)
    for (let i = 0; i < maxN; i++) {
      chosen.push(vertices[Math.round(i * step)])
    }
  }

  // Si la ruta es casi recta (pocos vértices), muestrear uniformemente para tener algunos waypoints
  if (chosen.length < 3) {
    chosen = []
    const step = (points.length - 1) / (maxN + 1)
    for (let i = 1; i <= maxN; i++) {
      chosen.push(points[Math.round(i * step)])
    }
  }
  return chosen
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
  const paradasLimpias = paradas.value.map(p => p.trim()).filter(Boolean)
  if (paradasLimpias.length === 0 && paradas.value.length > 0) {
    paradas.value = []
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
        paradas: paradasLimpias,
        optimizar: optimizar.value,
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

// ---------- Gestión de paradas ----------
const anadirParada = () => {
  paradas.value.push('')
}

const eliminarParada = (index: number) => {
  paradas.value.splice(index, 1)
}

const moverParada = (index: number, delta: number) => {
  const nuevo = index + delta
  if (nuevo < 0 || nuevo >= paradas.value.length) return
  const tmp = paradas.value[index]
  paradas.value[index] = paradas.value[nuevo]
  paradas.value[nuevo] = tmp
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

        <!-- Buscador origen/destino -->
        <div class="search-box">
          <div class="search-row">
            <div class="search-icon-col">
              <span class="search-icon origen">🟢</span>
              <div class="search-line"></div>
            </div>
            <div class="search-field">
              <label>Origen</label>
              <input v-model="origen" type="text" placeholder="Ej: Estació del Nord, Valencia" @keyup.enter="calcularRuta" />
            </div>
          </div>
          <div class="search-row">
            <div class="search-icon-col">
              <span class="search-icon destino">📍</span>
            </div>
            <div class="search-field">
              <label>Destino</label>
              <input v-model="destino" type="text" placeholder="Ej: Higueruelas, Valencia" @keyup.enter="calcularRuta" />
            </div>
          </div>

          <!-- Paradas intermedias -->
          <div v-for="(_, index) in paradas" :key="index" class="search-row parada-row">
            <div class="search-icon-col">
              <span class="search-icon parada">{{ index + 1 }}</span>
              <div class="search-line"></div>
            </div>
            <div class="search-field">
              <label>Parada {{ index + 1 }}</label>
              <input v-model="paradas[index]" type="text" placeholder="Ej: CEIP Cervantes, Cheste" @keyup.enter="calcularRuta" />
            </div>
            <div class="parada-actions">
              <button class="parada-btn" title="Subir" :disabled="index === 0" @click="moverParada(index, -1)">↑</button>
              <button class="parada-btn" title="Bajar" :disabled="index === paradas.length - 1" @click="moverParada(index, 1)">↓</button>
              <button class="parada-btn danger" title="Eliminar" @click="eliminarParada(index)">✕</button>
            </div>
          </div>

          <div class="parada-add-row">
            <button class="parada-add-btn" @click="anadirParada">➕ Añadir parada</button>
            <label class="optimizar-toggle" v-if="paradas.length >= 2">
              <input v-model="optimizar" type="checkbox" />
              <span>Optimizar orden</span>
            </label>
          </div>
        </div>

        <!-- Perfil del vehículo activo -->
        <div class="vehicle-profile">
          <div class="vehicle-profile-info">
            <span class="vehicle-profile-icon">🚌</span>
            <div class="vehicle-profile-text">
              <span class="vehicle-profile-label">PERFIL ACTIVO</span>
              <span v-if="vehiculoActivo" class="vehicle-profile-name">{{ vehiculoActivo.nombre }}</span>
              <span v-else class="vehicle-profile-name">Sin vehículo seleccionado</span>
            </div>
          </div>
          <div v-if="vehiculoActivo" class="vehicle-dims">
            <span class="vd-item" title="Altura"><b>{{ vehiculoActivo.alto_m }}</b> m</span>
            <span class="vd-item" title="Peso"><b>{{ (vehiculoActivo.peso_kg / 1000).toFixed(1) }}</b> t</span>
            <span class="vd-item" title="Longitud"><b>{{ vehiculoActivo.largo_m }}</b> m</span>
          </div>
          <button class="edit-btn" @click="activeTab = 'vehiculo'">EDITAR</button>
        </div>

        <!-- Selector de vehículo si hay varios -->
        <div class="form-section" v-if="vehiculos.length > 1">
          <label>Vehículo</label>
          <select :value="vehiculoActivoId || vehiculos[0].id"
            @change="cargarVehiculo(($event.target as HTMLSelectElement).value)">
            <option v-for="v in vehiculos" :key="v.id" :value="v.id">{{ v.nombre }}</option>
          </select>
        </div>
        <div class="form-section" v-else-if="vehiculos.length === 0">
          <div class="no-vehiculo-box">
            <p>Aún no tienes vehículos guardados.</p>
            <button class="btn btn-ghost btn-sm" @click="activeTab = 'vehiculo'">🚌 Crear uno en Vehículo</button>
          </div>
        </div>

        <button class="btn btn-primary btn-lg" :disabled="loading" @click="calcularRuta">
          {{ loading ? 'Calculando...' : '🔍 Calcular Ruta' }}
        </button>

        <div v-if="error" class="error">⚠️ {{ error }}</div>

        <!-- Resultado -->
        <template v-if="result">
          <h2 class="section-title">Rutas sugeridas</h2>

          <!-- Mapa con la geometría exacta de ORS (fuente de verdad) -->
          <RouteMap
            :polyline-segura="result.polyline"
            :polyline-convencional="result.convencional?.polyline"
            :origen="result.origen"
            :destino="result.destino"
            :color-segura="temaActual.primary"
            :color-convencional="'#64748b'"
          />

          <!-- Ruta segura -->
          <div class="route-card safe">
            <div class="route-flood safe">
              <span>🛡️</span><span>COMPATIBLE CON TU VEHÍCULO</span>
            </div>
            <div class="route-body">
              <div class="route-main">
                <div>
                  <span class="route-time">{{ formatoTiempo(result.duracion_min) }}</span>
                  <p class="route-sub">Motor: {{ result.motor }}</p>
                </div>
                <div class="route-dist">
                  <span class="route-dist-value">{{ result.distancia_km }}</span>
                  <span class="route-dist-unit">km</span>
                </div>
              </div>
              <div class="route-chips">
                <span class="chip">🚦 {{ result.pasos?.length || 0 }} pasos</span>
                <span class="chip">🚌 {{ vehiculoActivo?.nombre || 'vehículo configurado' }}</span>
              </div>
              <div class="compat-box">
                <span class="compat-title">✓ Calculado con las restricciones:</span>
                <span class="compat-tags">altura · peso · longitud · anchura</span>
              </div>
              <div class="route-nav">
                <a v-if="mapsSeguraUrl" class="nav-btn-main" :href="mapsSeguraUrl" target="_blank" rel="noopener">
                  Iniciar Navegación <span>🧭</span>
                </a>
                <a v-if="wazeSeguraUrl" class="nav-btn-alt" :href="wazeSeguraUrl" target="_blank" rel="noopener">
                  Waze
                </a>
                <button class="nav-btn-alt fav-inline" @click="guardarFavorito" title="Guardar esta ruta">⭐</button>
              </div>
            </div>
          </div>

          <!-- Ruta convencional -->
          <div v-if="result.convencional" class="route-card std">
            <div class="route-flood std">
              <span>⚠️</span><span>RUTA ESTÁNDAR (COCHE)</span>
            </div>
            <div class="route-body">
              <div class="route-main">
                <div>
                  <span class="route-time">{{ formatoTiempo(result.convencional.duracion_min) }}</span>
                  <p class="route-sub">Sin restricciones de vehículo</p>
                </div>
                <div class="route-dist">
                  <span class="route-dist-value">{{ result.convencional.distancia_km }}</span>
                  <span class="route-dist-unit">km</span>
                </div>
              </div>
              <div v-if="diferenciaKm > 0" class="route-warning">
                <span>⚠️</span>
                <div>
                  <span class="warning-title">Más corta pero no apta</span>
                  <span class="warning-sub">Es {{ diferenciaKm }} km más corta, pero puede pasar por vías con restricciones para tu vehículo</span>
                </div>
              </div>
              <div v-else-if="diferenciaKm <= 0" class="route-warning ok">
                <span>✅</span>
                <div>
                  <span class="warning-title">Coinciden</span>
                  <span class="warning-sub">No hay obstáculos para tu vehículo en esta ruta</span>
                </div>
              </div>
              <div class="route-nav">
                <a v-if="mapsUrl" class="nav-btn-main alt" :href="mapsUrl" target="_blank" rel="noopener">
                  Ver en Google Maps <span>🗺️</span>
                </a>
                <a v-if="wazeUrl" class="nav-btn-alt" :href="wazeUrl" target="_blank" rel="noopener">
                  Waze
                </a>
              </div>
            </div>
          </div>

          <div class="nav-note-badge">
            <span>🧭</span>
            <span>Ruta calculada considerando altura, peso y longitud del vehículo. El navegador puede adaptar el recorrido por tráfico.</span>
          </div>

          <!-- Pasos -->
          <h3 class="section-title">Pasos</h3>
          <ol class="steps-list">
            <li v-for="(paso, index) in result.pasos" :key="index">{{ paso }}</li>
          </ol>

          <!-- Riesgos -->
          <template v-if="result.riesgos && result.riesgos.length > 0">
            <h3 class="section-title">Riesgos</h3>
            <ul class="steps-list">
              <li v-for="(riesgo, index) in result.riesgos" :key="index">
                <strong>{{ riesgo.nombre }}</strong> ({{ riesgo.tipo }}): {{ riesgo.descripcion }}
              </li>
            </ul>
          </template>
          <p v-else class="no-riesgos">✅ Ruta calculada evitando las restricciones de tu vehículo</p>
        </template>
      </section>

      <!-- ══════════ PESTAÑA VEHÍCULO ══════════ -->
      <section v-if="activeTab === 'vehiculo'" class="tab-page">
        <h1 class="app-title">🚌 Vehículo</h1>
        <p class="app-subtitle">Configura las dimensiones exactas para garantizar rutas seguras y evitar restricciones.</p>

        <!-- Visualizador del bus -->
        <div class="bus-visualizer-box">
          <div class="bus-visualizer" :style="{ transform: busTransform }">
            <div class="bus-window"></div>
            <div class="bus-body">
              <span class="bus-label">BUSROAD</span>
            </div>
            <div class="bus-wheels">
              <div class="bus-wheel"></div>
              <div class="bus-wheel"></div>
            </div>
          </div>
          <div class="bus-dims">
            <div class="bus-dim"><span class="bus-dim-icon">⇕</span><span id="label-height">{{ dimensiones.alto_m.toFixed(1) }} m</span></div>
            <div class="bus-dim"><span class="bus-dim-icon">⇔</span><span id="label-width">{{ dimensiones.ancho_m.toFixed(1) }} m</span></div>
            <div class="bus-dim"><span class="bus-dim-icon">⟷</span><span id="label-length">{{ dimensiones.largo_m.toFixed(1) }} m</span></div>
            <div class="bus-dim"><span class="bus-dim-icon">⚖</span><span id="label-weight">{{ pesoT.toFixed(1) }} t</span></div>
          </div>
        </div>

        <!-- Sliders -->
        <div class="slider-card">
          <div class="slider-head">
            <label for="height">Altura (m)</label>
            <div class="slider-value"><span id="val-height">{{ dimensiones.alto_m.toFixed(1) }}</span></div>
          </div>
          <input class="slider" id="height" type="range" min="2.0" max="5.0" step="0.1" v-model.number="dimensiones.alto_m" />
          <div class="slider-bounds"><span>2.0 m</span><span>5.0 m</span></div>
        </div>

        <div class="slider-card">
          <div class="slider-head">
            <label for="width">Ancho (m)</label>
            <div class="slider-value"><span id="val-width">{{ dimensiones.ancho_m.toFixed(1) }}</span></div>
          </div>
          <input class="slider" id="width" type="range" min="2.0" max="3.5" step="0.1" v-model.number="dimensiones.ancho_m" />
          <div class="slider-bounds"><span>2.0 m</span><span>3.5 m</span></div>
        </div>

        <div class="slider-card">
          <div class="slider-head">
            <label for="length">Largo (m)</label>
            <div class="slider-value"><span id="val-length">{{ dimensiones.largo_m.toFixed(1) }}</span></div>
          </div>
          <input class="slider" id="length" type="range" min="5.0" max="25.0" step="0.5" v-model.number="dimensiones.largo_m" />
          <div class="slider-bounds"><span>5.0 m</span><span>25.0 m</span></div>
        </div>

        <div class="slider-card">
          <div class="slider-head">
            <label for="weight">Peso total (t)</label>
            <div class="slider-value"><span id="val-weight">{{ pesoT.toFixed(1) }}</span></div>
          </div>
          <input class="slider" id="weight" type="range" min="3.0" max="44.0" step="0.5" v-model.number="pesoT" />
          <div class="slider-bounds"><span>3.0 t</span><span>44.0 t</span></div>
        </div>

        <!-- Nombre + guardar -->
        <div class="form-section" style="margin-top: 20px">
          <label>Nombre del vehículo</label>
          <input v-model="nombreNuevoVehiculo" type="text" placeholder="Ej: Autobús 55 plazas, Furgoneta 3,5t..." />
        </div>
        <button class="btn btn-primary btn-lg" @click="guardarVehiculo">
          {{ guardadoOk ? '✓ ¡Guardado!' : '💾 Guardar configuración' }}
        </button>

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
.font-pequeno { font-size: 12px; }
.font-normal { font-size: 15px; }
.font-grande { font-size: 18px; }
.font-muy-grande { font-size: 22px; }

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

/* Buscador origen/destino */
.search-box {
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 12px;
}

.search-row {
  display: flex;
  align-items: stretch;
  gap: 12px;
}

.search-icon-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 4px;
}

.search-icon {
  font-size: 1.3em;
  line-height: 1;
}

.search-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: #2d3449;
  margin: 4px 0;
}

.search-field { flex: 1; padding-bottom: 12px; }

.search-row:last-child .search-field { padding-bottom: 0; }

.search-field label {
  display: block;
  font-size: 0.68em;
  font-weight: 700;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.search-field input {
  background: transparent;
  border: none;
  padding: 6px 0;
  font-size: 1em;
  color: #e5e7eb;
  width: 100%;
}

.search-field input:focus { outline: none; }

.search-field input::placeholder { color: #4b5563; }

/* Paradas intermedias */
.search-icon.parada {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--tema-primary);
  color: #0f1117;
  font-size: 0.7em;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', monospace;
}

.parada-row .search-field { padding-bottom: 8px; }

.parada-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 18px;
  flex-shrink: 0;
}

.parada-btn {
  width: 28px;
  height: 24px;
  background: #222a3d;
  border: 1px solid #2a2e3a;
  border-radius: 6px;
  color: #9ca3af;
  font-size: 0.75em;
  cursor: pointer;
  line-height: 1;
}

.parada-btn:hover:not(:disabled) { border-color: var(--tema-primary); color: var(--tema-primary); }

.parada-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.parada-btn.danger:hover { border-color: #f87171; color: #f87171; }

.parada-add-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 6px;
  border-top: 1px dashed #2a2e3a;
  margin-top: 4px;
}

.parada-add-btn {
  background: transparent;
  border: 1px dashed #3a3f52;
  border-radius: 8px;
  color: var(--tema-primary);
  font-size: 0.8em;
  font-weight: 600;
  padding: 8px 12px;
  cursor: pointer;
  font-family: inherit;
}

.parada-add-btn:hover { border-color: var(--tema-primary); background: var(--tema-glow); }

.optimizar-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78em;
  color: #9ca3af;
  cursor: pointer;
  user-select: none;
}

.optimizar-toggle input { width: auto; accent-color: var(--tema-primary); }

/* Perfil de vehículo */
.vehicle-profile {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #222a3d;
  border: 1px solid #2a2e3a;
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 16px;
}

.vehicle-profile-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.vehicle-profile-icon { font-size: 1.5em; }

.vehicle-profile-text { display: flex; flex-direction: column; }

.vehicle-profile-label {
  font-size: 0.62em;
  font-weight: 700;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.vehicle-profile-name { font-size: 0.9em; font-weight: 600; color: #e5e7eb; }

.vehicle-dims {
  display: flex;
  gap: 4px;
  margin-right: 4px;
}

.vd-item {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 0.72em;
  color: #9ca3af;
  font-family: 'JetBrains Mono', monospace;
}

.vd-item b { color: var(--tema-primary); font-size: 1.05em; }

.edit-btn {
  background: rgba(167, 139, 250, 0.12);
  color: var(--tema-primary);
  border: none;
  border-radius: 100px;
  padding: 6px 14px;
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.05em;
  cursor: pointer;
}

.edit-btn:hover { background: rgba(167, 139, 250, 0.25); }

/* Resultado: tarjetas de ruta */
.result-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 20px 0 12px;
}

.result-header-row h2 { font-size: 1.1em; font-weight: 700; }

.fav-btn {
  background: transparent;
  border: 1px solid #2a2e3a;
  color: #9ca3af;
  border-radius: 100px;
  padding: 6px 12px;
  font-size: 0.75em;
  font-weight: 600;
  cursor: pointer;
}

.fav-btn:hover { border-color: var(--tema-primary); color: var(--tema-primary); }

.route-card {
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 14px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.route-flood {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.route-flood.safe {
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  color: #0f1117;
}

.route-flood.std { background: #222a3d; color: #fbbf24; }

.route-body { padding: 14px; }

.route-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.route-time {
  font-size: 1.8em;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #e5e7eb;
  line-height: 1;
}

.route-card.safe .route-time { color: var(--tema-primary); }

.route-sub { font-size: 0.78em; color: #6b7280; margin-top: 4px; }

.route-dist { text-align: right; }

.route-dist-value { font-size: 1.4em; font-weight: 800; color: #e5e7eb; }

.route-dist-unit { font-size: 0.75em; color: #6b7280; margin-left: 2px; }

.route-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }

.chip {
  background: #222a3d;
  color: #9ca3af;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 0.72em;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}

.route-nav { display: flex; gap: 8px; }

.fav-inline {
  padding: 12px;
  font-size: 1.1em;
  line-height: 1;
  cursor: pointer;
}

.compat-box {
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: rgba(74, 222, 128, 0.08);
  border: 1px solid rgba(74, 222, 128, 0.2);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.compat-title {
  font-size: 0.8em;
  font-weight: 700;
  color: #4ade80;
}

.compat-tags {
  font-size: 0.72em;
  color: #9ca3af;
  font-family: 'JetBrains Mono', monospace;
}

.nav-btn-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  color: #0f1117;
  border: none;
  border-radius: 10px;
  padding: 12px;
  font-size: 0.9em;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  transition: filter 0.2s;
}

.nav-btn-main:hover { filter: brightness(1.1); }

.nav-btn-main.alt { background: #222a3d; color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); }

.nav-btn-alt {
  background: transparent;
  border: 1px solid #2a2e3a;
  color: #9ca3af;
  border-radius: 10px;
  padding: 12px 16px;
  font-size: 0.85em;
  font-weight: 600;
  text-decoration: none;
}

.nav-btn-alt:hover { border-color: var(--tema-primary); color: var(--tema-primary); }

.route-warning {
  display: flex;
  gap: 10px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.route-warning.ok { background: rgba(74, 222, 128, 0.08); border-color: rgba(74, 222, 128, 0.25); }

.route-warning > span { font-size: 1.1em; }

.warning-title {
  display: block;
  font-size: 0.8em;
  font-weight: 700;
  color: #fbbf24;
}

.route-warning.ok .warning-title { color: #4ade80; }

.warning-sub {
  display: block;
  font-size: 0.72em;
  color: #9ca3af;
  margin-top: 2px;
}

.steps-list { margin: 8px 0 8px 20px; }

.steps-list li {
  margin-bottom: 6px;
  font-size: 0.88em;
  color: #d1d5db;
}

.error {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 12px 14px;
  border-radius: 10px;
  margin-top: 12px;
  font-size: 0.9em;
}

.maps-note { font-size: 0.78em; color: #6b7280; margin: 4px 0 16px; font-style: italic; }

.nav-note-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.8em;
  color: #9ca3af;
  margin-bottom: 16px;
}

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

/* Visualizador del bus */
.bus-visualizer-box {
  position: relative;
  height: 200px;
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.bus-visualizer-box::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, var(--tema-glow) 0%, transparent 60%);
  pointer-events: none;
}

.bus-visualizer {
  position: relative;
  width: 140px;
  height: 90px;
  transition: transform 0.3s ease;
}

.bus-window {
  height: 33%;
  width: 100%;
  background: rgba(20, 25, 40, 0.6);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.bus-body {
  flex: 1;
  width: 100%;
  height: 67%;
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  box-shadow: 0 4px 16px var(--tema-glow);
}

.bus-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.15em;
  color: #0f1117;
  opacity: 0.85;
}

.bus-wheels {
  position: absolute;
  bottom: -8px;
  width: 100%;
  display: flex;
  justify-content: space-between;
  padding: 0 6px;
}

.bus-wheel {
  width: 22px;
  height: 14px;
  background: #9ca3af;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
}

.bus-dims {
  position: absolute;
  bottom: 12px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-around;
  padding: 0 8px;
}

.bus-dim {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 0.7em;
  font-weight: 700;
  color: #9ca3af;
  font-family: 'JetBrains Mono', monospace;
}

.bus-dim-icon { font-size: 1.1em; color: var(--tema-primary); }

/* Sliders */
.slider-card {
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.slider-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.slider-head label {
  font-size: 0.8em;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0;
}

.slider-value {
  background: #222a3d;
  padding: 6px 14px;
  border-radius: 8px;
  min-width: 70px;
  text-align: center;
}

.slider-value span {
  font-size: 1.2em;
  font-weight: 800;
  color: var(--tema-primary);
}

.slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 6px;
  background: #2d3449;
  outline: none;
  cursor: pointer;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  border: 2px solid #0f1117;
  box-shadow: 0 2px 8px var(--tema-glow);
  cursor: grab;
}

.slider::-moz-range-thumb {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--tema-primary), var(--tema-primary2));
  border: 2px solid #0f1117;
  box-shadow: 0 2px 8px var(--tema-glow);
  cursor: grab;
}

.slider-bounds {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 0.68em;
  color: #6b7280;
  opacity: 0.8;
  font-family: 'JetBrains Mono', monospace;
}

.empty-state { text-align: center; padding: 32px 16px; color: #9ca3af; }

.no-vehiculo-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  background: #1a1d27;
  border: 1px dashed #2a2e3a;
  border-radius: 10px;
  font-size: 0.85em;
  color: #9ca3af;
}

.no-vehiculo-box p { margin: 0; }

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
