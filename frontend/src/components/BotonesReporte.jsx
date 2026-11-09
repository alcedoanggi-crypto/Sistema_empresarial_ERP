import { useState } from 'react'
import { descargar, notificar } from '../api'

/**
 * Botones PDF / Excel para exportar un reporte desde la propia pantalla del módulo.
 * reportes: [{ clave: 'inventario', titulo: 'Inventario' }]
 * En los módulos sólo se ofrece PDF; Excel queda en la página general de Reportes.
 */
export default function BotonesReporte({ reportes, excel = false }) {
  const [bajando, setBajando] = useState('')

  async function bajar(clave, formato) {
    setBajando(clave + formato)
    try {
      await descargar(`/reportes/${clave}?formato=${formato}`, `${clave}.${formato === 'pdf' ? 'pdf' : 'xlsx'}`)
    } catch (e) {
      notificar(e.message, 'error')
    } finally {
      setBajando('')
    }
  }

  return reportes.map((r) => (
    <div key={r.clave} className="flex items-center overflow-hidden rounded-md border border-slate-300 bg-white text-sm">
      <span className="px-2 text-slate-500">{r.titulo}</span>
      <button className="border-l border-slate-300 px-2 py-2 font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
              disabled={!!bajando} onClick={() => bajar(r.clave, 'pdf')}>
        {bajando === r.clave + 'pdf' ? '...' : '⬇ PDF'}
      </button>
      {excel && <button className="border-l border-slate-300 px-2 py-2 font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
              disabled={!!bajando} onClick={() => bajar(r.clave, 'excel')}>
        {bajando === r.clave + 'excel' ? '...' : 'Excel'}
      </button>}
    </div>
  ))
}
