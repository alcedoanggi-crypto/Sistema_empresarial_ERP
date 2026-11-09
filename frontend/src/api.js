// Cliente HTTP mínimo: agrega el token, traduce errores de la API a mensajes legibles.
const BASE = '/api'

function mensajeError(data) {
  const det = data?.detail
  if (!det) return 'Error inesperado'
  if (typeof det === 'string') return det
  if (Array.isArray(det)) return det.map((e) => `${e.loc?.slice(-1)[0]}: ${e.msg}`).join(' · ')
  if (det.faltantes) {
    return `${det.mensaje}: ` + det.faltantes.map((f) => `${f.producto} (disponible ${f.disponible}, pedido ${f.solicitado})`).join(', ')
  }
  return JSON.stringify(det)
}

export async function api(path, { method = 'GET', body } = {}) {
  const token = localStorage.getItem('token')
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401 && path !== '/auth/login') {
    localStorage.removeItem('token')
    window.location.href = '/login'
    return
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(mensajeError(data))
  return data
}

export async function descargar(path, nombre) {
  const res = await fetch(BASE + path, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
  if (!res.ok) throw new Error(mensajeError(await res.json().catch(() => null)))
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: nombre })
  a.click()
  URL.revokeObjectURL(url)
}

// Notificaciones simples (las muestra <Toaster/>)
export function notificar(texto, tipo = 'ok') {
  window.dispatchEvent(new CustomEvent('toast', { detail: { texto, tipo } }))
}

export const dinero = (v) =>
  v == null ? '—' : Number(v).toLocaleString('es-EC', { style: 'currency', currency: 'USD' })
export const fecha = (v) => (v ? new Date(v.length === 10 ? v + 'T00:00' : v).toLocaleDateString('es-EC') : '—')
export const fechaHora = (v) => (v ? new Date(v).toLocaleString('es-EC') : '—')
