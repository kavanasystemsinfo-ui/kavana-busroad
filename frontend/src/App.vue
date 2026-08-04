<script setup lang="ts">
import { ref, computed } from 'vue'

const origen = ref('Madrid')
const destino = ref('Barcelona')
const loading = ref(false)
const error = ref<string | null>(null)
const result = ref<any | null>(null)

const dimensiones = ref({
  largo_m: 12.0,
  ancho_m: 2.5,
  alto_m: 3.5,
  peso_kg: 12000
})

// Use environment variable for API URL, fallback to production backend
const API_URL = import.meta.env.VITE_API_URL || 'https://busroad-api.kavanasystems.com'

// URLs para abrir la ruta en apps de navegación (se actualizan tras calcular)
const mapsUrl = ref('')
const wazeUrl = ref('')

// Diferencia en km entre la ruta segura y la convencional (si existe)
const diferenciaKm = computed(() => {
  if (!result.value || !result.value.convencional) return 0
  return Math.round((result.value.convencional.distancia_km - result.value.distancia_km) * 10) / 10
})

const abrirEnMapas = (origen: string, destino: string) => {
  mapsUrl.value = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origen)}&destination=${encodeURIComponent(destino)}&travelmode=driving`
  wazeUrl.value = `https://www.waze.com/ul?q=${encodeURIComponent(destino)}&navigate=yes`
}

const calcularRuta = async () => {
  loading.value = true
  error.value = null
  result.value = null
  try {
    const response = await fetch(`${API_URL}/api/v1/ruta`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
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
    abrirEnMapas(origen.value, destino.value)
  } catch (e: any) {
    error.value = e.message || 'Error desconocido'
    console.error(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="container">
    <h1>Kavana BusRoad - Planificador de Rutas</h1>
    <div class="form-section">
      <label>Origen:</label>
      <input v-model="origen" type="text" placeholder="Ej: Madrid" />
    </div>
    <div class="form-section">
      <label>Destino:</label>
      <input v-model="destino" type="text" placeholder="Ej: Barcelona" />
    </div>
    <div class="form-section">
      <h2>Dimensiones del vehículo</h2>
      <div class="dimensions-grid">
        <div>
          <label>Longitud (m):</label>
          <input v-model.number="dimensiones.largo_m" type="number" step="0.1" min="1" />
        </div>
        <div>
          <label>Anchura (m):</label>
          <input v-model.number="dimensiones.ancho_m" type="number" step="0.1" min="1" />
        </div>
        <div>
          <label>Altura (m):</label>
          <input v-model.number="dimensiones.alto_m" type="number" step="0.1" min="1" />
        </div>
        <div>
          <label>Peso (kg):</label>
          <input v-model.number="dimensiones.peso_kg" type="number" step="100" min="1000" />
        </div>
      </div>
    </div>
    <div class="form-section">
      <button :disabled="loading" @click="calcularRuta">
        {{ loading ? 'Calculando...' : 'Calcular Ruta' }}
      </button>
    </div>

    <div v-if="error" class="error">
      Error: {{ error }}
    </div>

    <div v-if="result" class="result">
      <h2>Resultado de la ruta</h2>
      <p><strong>Origen:</strong> {{ result.origen }}</p>
      <p><strong>Destino:</strong> {{ result.destino }}</p>

      <div class="ruta-segura">
        <h3>🚌 Ruta para tu vehículo</h3>
        <p><strong>Distancia:</strong> {{ result.distancia_km }} km</p>
        <p><strong>Duración:</strong> {{ result.duracion_min }} min</p>
        <p class="motor-note">Calculada con las restricciones de tu vehículo ({{ result.motor }})</p>
      </div>

      <div v-if="result.convencional" class="ruta-convencional">
        <h3>🚗 Ruta convencional (coche)</h3>
        <p><strong>Distancia:</strong> {{ result.convencional.distancia_km }} km</p>
        <p><strong>Duración:</strong> {{ result.convencional.duracion_min }} min</p>
        <p class="motor-note">Sin restricciones, la ruta que seguiría un coche normal</p>
        <p v-if="diferenciaKm > 0" class="diff-note">
          ⚠️ Tu ruta es {{ diferenciaKm }} km más larga pero evita vías no aptas para tu vehículo
        </p>
        <p v-else-if="diferenciaKm < 0" class="diff-note">
          ✅ Tu ruta es incluso {{ Math.abs(diferenciaKm) }} km más corta
        </p>
      </div>

      <div class="maps-actions">
        <a class="maps-btn alt" :href="mapsUrl" target="_blank" rel="noopener">
          🚗 Ver ruta convencional en Google Maps
        </a>
        <a class="maps-btn" :href="wazeUrl" target="_blank" rel="noopener">
          📍 Navegar a destino (Waze)
        </a>
      </div>
      <p class="maps-note">Google Maps no conoce las restricciones de tu vehículo, por eso mostramos la ruta convencional aparte. Para navegar con la ruta segura, usa las instrucciones de arriba.</p>

      <h3>Pasos:</h3>
      <ol>
        <li v-for="(paso, index) in result.pasos" :key="index">{{ paso }}</li>
      </ol>

      <h3 v-if="result.riesgos && result.riesgos.length > 0">Riesgos:</h3>
      <ul v-if="result.riesgos && result.riesgos.length > 0">
        <li v-for="(riesgo, index) in result.riesgos" :key="index">
          <strong>{{ riesgo.nombre }}</strong> ({{ riesgo.tipo }}): {{ riesgo.descripcion }}
        </li>
      </ul>
      <p v-else class="no-riesgos">
        ✅ Ruta calculada evitando las restricciones de tu vehículo
      </p>
    </div>
  </div>
</template>

<style>
.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}
.form-section {
  margin-bottom: 20px;
}
.form-section label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}
.form-section input {
  width: 100%;
  padding: 8px;
  box-sizing: border-box;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}
.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-top: 10px;
}
.dimensions-grid div {
  display: flex;
  flex-direction: column;
}
button {
  background-color: #007bff;
  color: white;
  border: none;
  padding: 10px 20px;
  cursor: pointer;
  font-size: 16px;
  border-radius: 4px;
  transition: background-color 0.3s;
}
button:hover:not(:disabled) {
  background-color: #0056b3;
}
button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}
.error {
  color: red;
  background-color: #ffeef0;
  padding: 10px;
  border-radius: 4px;
  margin-top: 10px;
  border: 1px solid #fcc;
}
.maps-actions {
  display: flex;
  gap: 10px;
  margin: 15px 0;
  flex-wrap: wrap;
}
.maps-btn {
  display: inline-block;
  background-color: #007bff;
  color: white;
  padding: 10px 16px;
  border-radius: 4px;
  text-decoration: none;
  font-size: 15px;
  transition: background-color 0.3s;
}
.maps-btn:hover {
  background-color: #0056b3;
}
.maps-btn.alt {
  background-color: #4caf50;
}
.maps-btn.alt:hover {
  background-color: #388e3c;
}
.maps-note {
  font-size: 13px;
  color: #666;
  margin-top: 8px;
  font-style: italic;
}
.ruta-segura {
  margin-top: 12px;
  padding: 10px;
  background-color: #e8f5e9;
  border-radius: 4px;
  border-left: 4px solid #4caf50;
}
.ruta-convencional {
  margin-top: 12px;
  padding: 10px;
  background-color: #e3f2fd;
  border-radius: 4px;
  border-left: 4px solid #1976d2;
}
.ruta-segura h3, .ruta-convencional h3 {
  margin: 0 0 6px 0;
  font-size: 16px;
  color: #333;
}
.ruta-segura p, .ruta-convencional p {
  margin: 3px 0;
}
.motor-note {
  font-size: 12px;
  color: #777;
  font-style: italic;
}
.diff-note {
  font-size: 14px;
  font-weight: 600;
  margin-top: 6px !important;
  color: #333;
}
.no-riesgos {
  color: #28a745;
  font-size: 14px;
  margin-top: 8px;
}
.result {
  margin-top: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
  border: 1px solid #e9ecef;
}
.result h2, .result h3 {
  margin-top: 0;
  color: #333;
}
.result ol, .result ul {
  margin: 10px 0;
  padding-left: 20px;
}
.result li {
  margin-bottom: 5px;
}
</style>