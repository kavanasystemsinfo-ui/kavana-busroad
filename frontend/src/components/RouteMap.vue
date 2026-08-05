<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps<{
  polylineSegura: string
  polylineConvencional?: string
  origen: string
  destino: string
  colorSegura: string
  colorConvencional?: string
}>()

const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let layerSegura: L.LayerGroup | null = null
let layerConvencional: L.LayerGroup | null = null

// Decodifica un polyline encoded (formato Google/ORS) a coordenadas [lat, lng]
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

const renderMapa = () => {
  if (!mapEl.value) return
  if (!map) {
    map = L.map(mapEl.value, { zoomControl: true, attributionControl: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map)
  }

  // Limpiar capas anteriores
  if (layerSegura) { layerSegura.remove(); layerSegura = null }
  if (layerConvencional) { layerConvencional.remove(); layerConvencional = null }
  layerSegura = L.layerGroup().addTo(map)
  layerConvencional = L.layerGroup().addTo(map)

  const ptsSegura = decodePolyline(props.polylineSegura)
  const ptsConv = props.polylineConvencional ? decodePolyline(props.polylineConvencional) : null

  // Ruta convencional debajo (más fina, color neutro)
  if (ptsConv && ptsConv.length > 1) {
    L.polyline(ptsConv, {
      color: props.colorConvencional || '#64748b',
      weight: 3,
      opacity: 0.6,
      dashArray: '6 6'
    }).addTo(layerConvencional)
  }

  // Ruta segura encima (gruesa, color del tema)
  if (ptsSegura.length > 1) {
    L.polyline(ptsSegura, {
      color: props.colorSegura,
      weight: 6,
      opacity: 0.95
    }).addTo(layerSegura)
  }

  // Marcadores de origen y destino (divIcon con emoji, evita problemas de assets)
  if (ptsSegura.length > 0) {
    const [lat0, lng0] = ptsSegura[0]
    const [lat1, lng1] = ptsSegura[ptsSegura.length - 1]
    L.marker([lat0, lng0], {
      icon: L.divIcon({ html: '<div style="font-size:26px">🟢</div>', className: '', iconSize: [26, 26], iconAnchor: [13, 13] }),
      title: props.origen
    }).addTo(layerSegura).bindPopup(props.origen)
    L.marker([lat1, lng1], {
      icon: L.divIcon({ html: '<div style="font-size:26px">🔴</div>', className: '', iconSize: [26, 26], iconAnchor: [13, 13] }),
      title: props.destino
    }).addTo(layerSegura).bindPopup(props.destino)
  }

  // Ajustar vista a la ruta segura (padding pequeño: la ruta ocupa ~80% del mapa)
  if (ptsSegura.length > 1) {
    map.fitBounds(L.latLngBounds(ptsSegura), { padding: [18, 18], maxZoom: 15 })
  } else if (ptsConv && ptsConv.length > 1) {
    map.fitBounds(L.latLngBounds(ptsConv), { padding: [18, 18], maxZoom: 15 })
  }

  // Si el mapa está en un contenedor oculto, invalidar tamaño al mostrar
  setTimeout(() => map?.invalidateSize(), 100)
}

onMounted(() => {
  renderMapa()
})

watch(() => [props.polylineSegura, props.polylineConvencional, props.colorSegura] as const, () => {
  nextTick(() => renderMapa())
})
</script>

<template>
  <div class="route-map-wrap">
    <div ref="mapEl" class="route-map"></div>
    <div class="map-legend">
      <span class="legend-item"><span class="legend-dot" :style="{ background: props.colorSegura }"></span> Ruta compatible con el vehículo</span>
      <span v-if="props.polylineConvencional" class="legend-item"><span class="legend-dot std"></span> Ruta estándar</span>
    </div>
  </div>
</template>

<style scoped>
.route-map-wrap {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #2a2e3a;
  margin-bottom: 14px;
}

.route-map {
  width: 100%;
  height: 280px;
  background: #1a1d27;
  z-index: 1;
}

.map-legend {
  display: flex;
  gap: 16px;
  align-items: center;
  background: #1a1d27;
  border: 1px solid #2a2e3a;
  border-top: none;
  border-radius: 0 0 14px 14px;
  padding: 8px 14px;
  font-size: 0.72em;
  font-weight: 600;
  color: #d1d5db;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 14px;
  height: 5px;
  border-radius: 3px;
  flex-shrink: 0;
}

.legend-dot.std {
  background: repeating-linear-gradient(90deg, #64748b 0 4px, transparent 4px 7px);
}
</style>
