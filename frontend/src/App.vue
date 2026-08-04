<script setup lang="ts">
import { ref } from 'vue'

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
      <p><strong>Distancia:</strong> {{ result.distancia_km }} km</p>
      <p><strong>Duración:</strong> {{ result.duracion_min }} min</p>
      <p><strong>Motor:</strong> {{ result.motor }}</p>

      <h3>Pasos:</h3>
      <ol>
        <li v-for="(paso, index) in result.pasos" :key="index">{{ paso }}</li>
      </ol>

      <h3>Riesgos:</h3>
      <ul>
        <li v-for="(riesgo, index) in result.riesgos" :key="index">
          <strong>{{ riesgo.nombre }}</strong> ({{ riesgo.tipo }}): {{ riesgo.descripcion }}
        </li>
      </ul>
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