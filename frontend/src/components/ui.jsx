import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

export function Modal({ titulo, onClose, children, ancho = 'max-w-lg' }) {
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <div className={`mt-10 w-full ${ancho} rounded-lg bg-white shadow-xl`} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h3 className="font-semibold text-slate-800">{titulo}</h3>
          <button onClick={onClose} className="text-xl leading-none text-slate-400 hover:text-slate-600">×</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

const COLORES = {
  verde: 'bg-emerald-100 text-emerald-700',
  rojo: 'bg-red-100 text-red-700',
  amarillo: 'bg-amber-100 text-amber-700',
  azul: 'bg-sky-100 text-sky-700',
  gris: 'bg-slate-100 text-slate-600',
}
const COLOR_ESTADO = {
  activo: 'verde', aprobada: 'verde', recibida: 'verde', facturada: 'verde', emitida: 'verde', aceptada: 'verde', normal: 'verde', entrada: 'verde', CREAR: 'verde',
  pendiente: 'amarillo', borrador: 'amarillo', licencia: 'amarillo', critico: 'amarillo', enviada: 'azul', MODIFICAR: 'azul', RESTAURAR: 'azul',
  cancelada: 'rojo', rechazada: 'rojo', anulada: 'rojo', inactivo: 'rojo', agotado: 'rojo', salida: 'rojo', vencida: 'rojo', ELIMINAR: 'rojo',
}

export function Badge({ valor, color }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${COLORES[color || COLOR_ESTADO[valor] || 'gris']}`}>
      {String(valor).replace('_', ' ')}
    </span>
  )
}

export function Campo({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  )
}

export function Encabezado({ titulo, children }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-xl font-semibold text-slate-800">{titulo}</h1>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}

/** Opciones para <select> a partir de un endpoint paginado o lista. */
export function useOpciones(url, etiqueta = (x) => x.nombre) {
  const [opciones, setOpciones] = useState([])
  useEffect(() => {
    if (!url) return
    api(url + (url.includes('?') ? '&' : '?') + 'page_size=500')
      .then((d) => setOpciones((d.items || d).map((x) => ({ value: x.id, label: etiqueta(x), raw: x }))))
      .catch(() => setOpciones([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])
  return opciones
}

/** Estado de un listado paginado con búsqueda y filtros (todo se resuelve en el servidor). */
export function useListado(url, filtrosIniciales = {}) {
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [filtros, setFiltros] = useState(filtrosIniciales)
  const [data, setData] = useState({ items: [], total: 0, pages: 1 })
  const [cargando, setCargando] = useState(false)

  const recargar = useCallback(() => {
    const params = new URLSearchParams({ page, page_size: 10 })
    if (q) params.set('q', q)
    Object.entries(filtros).forEach(([k, v]) => v !== '' && v != null && params.set(k, v))
    setCargando(true)
    api(`${url}?${params}`).then(setData).catch(() => setData({ items: [], total: 0, pages: 1 })).finally(() => setCargando(false))
  }, [url, page, q, filtros])

  useEffect(() => {
    const t = setTimeout(recargar, 250) // debounce de la búsqueda
    return () => clearTimeout(t)
  }, [recargar])

  return {
    data, cargando, recargar, page, setPage, q,
    setQ: (v) => { setQ(v); setPage(1) },
    filtros,
    setFiltro: (k, v) => { setFiltros((f) => ({ ...f, [k]: v })); setPage(1) },
  }
}
