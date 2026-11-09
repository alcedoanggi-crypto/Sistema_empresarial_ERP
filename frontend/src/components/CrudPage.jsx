import { useState } from 'react'
import { api, notificar } from '../api'
import { useAuth } from '../auth'
import BotonesReporte from './BotonesReporte'
import Tabla from './Tabla'
import { Campo, Encabezado, Modal, useListado, useOpciones } from './ui'

/**
 * Página CRUD genérica a partir de una configuración:
 *  { titulo, url, modulo, columnas, campos, filtros }
 * campos: [{ name, label, type: text|number|date|email|password|textarea|checkbox|select,
 *            options?, optionsUrl?, optionLabel?, required?, soloCrear? }]
 * Así cada catálogo (empleados, productos, clientes...) son ~20 líneas de configuración.
 */
export default function CrudPage({ titulo, url, modulo, columnas, campos, filtros = [], acciones, reportes = [] }) {
  const { puede } = useAuth()
  const listado = useListado(url)
  const [editando, setEditando] = useState(null) // null = cerrado, {} = nuevo, {...} = edición

  async function eliminar(fila) {
    if (!confirm('¿Eliminar este registro? (borrado lógico, queda en auditoría)')) return
    try {
      await api(`${url}/${fila.id}`, { method: 'DELETE' })
      notificar('Registro eliminado')
      listado.recargar()
    } catch (e) {
      notificar(e.message, 'error')
    }
  }

  return (
    <>
      <Encabezado titulo={titulo}>
        <BotonesReporte reportes={reportes} />
        {puede(modulo, 'crear') && <button className="btn-primario" onClick={() => setEditando({})}>+ Nuevo</button>}
      </Encabezado>
      <Tabla
        listado={listado}
        columnas={columnas}
        filtros={filtros}
        acciones={(fila) => (
          <div className="flex justify-end gap-3">
            {acciones?.(fila, listado.recargar)}
            {puede(modulo, 'editar') && <button className="btn-link" onClick={() => setEditando(fila)}>Editar</button>}
            {puede(modulo, 'eliminar') && <button className="text-sm text-red-600 hover:underline" onClick={() => eliminar(fila)}>Eliminar</button>}
          </div>
        )}
      />
      {editando && (
        <Formulario url={url} campos={campos} inicial={editando} titulo={titulo}
                    onClose={() => setEditando(null)}
                    onGuardado={() => { setEditando(null); listado.recargar() }} />
      )}
    </>
  )
}

function Formulario({ url, campos, inicial, titulo, onClose, onGuardado }) {
  const esNuevo = !inicial.id
  const visibles = campos.filter((c) => esNuevo || !c.soloCrear)
  const [valores, setValores] = useState(() =>
    Object.fromEntries(visibles.map((c) => [c.name, inicial[c.name] ?? (c.type === 'checkbox' ? (c.default ?? true) : c.default ?? '')]))
  )
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  async function guardar(e) {
    e.preventDefault()
    // Convierte '' en null y los números a Number antes de enviar
    const body = {}
    for (const c of visibles) {
      let v = valores[c.name]
      if (v === '') v = null
      else if ((c.type === 'number' || c.type === 'select') && v != null && !isNaN(v) && c.numeric !== false) v = Number(v)
      if (c.type === 'password' && !esNuevo && !v) continue
      body[c.name] = v
    }
    setGuardando(true)
    setError('')
    try {
      await api(esNuevo ? url : `${url}/${inicial.id}`, { method: esNuevo ? 'POST' : 'PUT', body })
      notificar(esNuevo ? 'Registro creado' : 'Cambios guardados')
      onGuardado()
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Modal titulo={`${esNuevo ? 'Nuevo' : 'Editar'} · ${titulo}`} onClose={onClose} ancho="max-w-2xl">
      <form onSubmit={guardar}>
        <div className="grid gap-3 sm:grid-cols-2">
          {visibles.map((c) => (
            <div key={c.name} className={c.type === 'textarea' ? 'sm:col-span-2' : ''}>
              <Entrada campo={c} valor={valores[c.name]} esNuevo={esNuevo}
                       onChange={(v) => setValores((s) => ({ ...s, [c.name]: v }))} />
            </div>
          ))}
        </div>
        {error && <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-secundario" onClick={onClose}>Cancelar</button>
          <button className="btn-primario" disabled={guardando}>{guardando ? 'Guardando...' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}

function Entrada({ campo: c, valor, onChange, esNuevo }) {
  const remotas = useOpciones(c.optionsUrl, c.optionLabel)
  const requerido = c.required && !(c.type === 'password' && !esNuevo)

  if (c.type === 'checkbox') {
    return (
      <label className="mt-6 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={!!valor} onChange={(e) => onChange(e.target.checked)} /> {c.label}
      </label>
    )
  }
  let control
  if (c.type === 'select') {
    const opciones = c.options || remotas
    control = (
      <select className="input" value={valor ?? ''} required={requerido} onChange={(e) => onChange(e.target.value)}>
        <option value="">— Seleccione —</option>
        {opciones.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    )
  } else if (c.type === 'textarea') {
    control = <textarea className="input" rows={2} value={valor ?? ''} onChange={(e) => onChange(e.target.value)} />
  } else {
    control = (
      <input className="input" type={c.type || 'text'} step={c.type === 'number' ? 'any' : undefined}
             value={valor ?? ''} required={requerido} placeholder={c.placeholder}
             onChange={(e) => onChange(c.upper ? e.target.value.toUpperCase() : e.target.value)} />
    )
  }
  return <Campo label={c.label + (requerido ? ' *' : '')}>{control}</Campo>
}
