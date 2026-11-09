import { useEffect, useState } from 'react'
import { api, descargar, fechaHora, notificar } from '../api'
import { useAuth } from '../auth'
import BotonesReporte from '../components/BotonesReporte'
import Tabla from '../components/Tabla'
import { Badge, Campo, Encabezado, Modal, useListado } from '../components/ui'

export function Reportes() {
  const [reportes, setReportes] = useState([])
  const [rango, setRango] = useState({ desde: '', hasta: '' })
  const [bajando, setBajando] = useState('')
  useEffect(() => { api('/reportes').then(setReportes) }, [])

  async function bajar(clave, formato) {
    const p = new URLSearchParams({ formato })
    if (rango.desde) p.set('desde', rango.desde)
    if (rango.hasta) p.set('hasta', rango.hasta)
    setBajando(clave + formato)
    try {
      await descargar(`/reportes/${clave}?${p}`, `${clave}.${formato === 'pdf' ? 'pdf' : 'xlsx'}`)
    } catch (e) { notificar(e.message, 'error') } finally { setBajando('') }
  }

  return (
    <>
      <Encabezado titulo="Reportes" />
      <div className="card mb-4 flex flex-wrap items-end gap-3">
        <Campo label="Desde"><input className="input" type="date" value={rango.desde} onChange={(e) => setRango({ ...rango, desde: e.target.value })} /></Campo>
        <Campo label="Hasta"><input className="input" type="date" value={rango.hasta} onChange={(e) => setRango({ ...rango, hasta: e.target.value })} /></Campo>
        <p className="pb-2 text-xs text-slate-400">El rango aplica a ventas, compras, movimientos y auditoría.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {reportes.map((r) => (
          <div key={r.clave} className="card flex items-center justify-between gap-2">
            <div><p className="font-medium text-slate-800">{r.titulo}</p><p className="text-xs capitalize text-slate-400">{r.modulo}</p></div>
            <div className="flex gap-2">
              <button className="btn-secundario px-2 py-1 text-red-700" disabled={!!bajando} onClick={() => bajar(r.clave, 'pdf')}>{bajando === r.clave + 'pdf' ? '...' : 'PDF'}</button>
              <button className="btn-secundario px-2 py-1 text-emerald-700" disabled={!!bajando} onClick={() => bajar(r.clave, 'excel')}>{bajando === r.clave + 'excel' ? '...' : 'Excel'}</button>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

const TABLAS = ['empleados', 'usuarios', 'productos', 'ordenes_compra', 'ordenes_venta', 'facturas', 'clientes', 'proveedores', 'solicitudes', 'permisos']

export function Auditoria() {
  const listado = useListado('/auditoria')
  const [detalle, setDetalle] = useState(null)
  return (
    <>
      <Encabezado titulo="Auditoría">
        <BotonesReporte reportes={[{ clave: 'auditoria', titulo: 'Bitácora' }]} />
      </Encabezado>
      <p className="mb-3 text-sm text-slate-500">Registrada automáticamente por un trigger de PostgreSQL en cada INSERT/UPDATE/DELETE. Es de solo lectura.</p>
      <Tabla listado={listado} busqueda={false}
        filtros={[
          { name: 'accion', label: 'Acción', options: ['CREAR', 'MODIFICAR', 'ELIMINAR', 'RESTAURAR'].map((v) => ({ value: v, label: v })) },
          { name: 'tabla', label: 'Tabla', options: TABLAS.map((v) => ({ value: v, label: v })) },
        ]}
        columnas={[
          { key: 'fecha', label: 'Fecha', render: (r) => fechaHora(r.fecha) }, { key: 'usuario', label: 'Usuario' },
          { key: 'accion', label: 'Acción', render: (r) => <Badge valor={r.accion} /> },
          { key: 'tabla', label: 'Tabla' }, { key: 'registro_id', label: 'ID' },
          { key: 'campos', label: 'Campos modificados', render: (r) => <span className="text-xs">{r.campos_modificados?.join(', ') ?? '—'}</span> },
        ]}
        acciones={(r) => <button className="btn-link" onClick={() => setDetalle(r)}>Detalle</button>} />
      {detalle && (
        <Modal titulo={`${detalle.accion} · ${detalle.tabla} #${detalle.registro_id}`} onClose={() => setDetalle(null)} ancho="max-w-3xl">
          <div className="grid gap-3 text-xs sm:grid-cols-2">
            {['datos_anteriores', 'datos_nuevos'].map((k) => (
              <div key={k}><p className="mb-1 font-semibold text-slate-600">{k === 'datos_anteriores' ? 'Antes' : 'Después'}</p>
                <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-2">{detalle[k] ? JSON.stringify(detalle[k], null, 2) : '—'}</pre></div>
            ))}
          </div>
        </Modal>
      )}
    </>
  )
}

const ACCIONES = ['ver', 'crear', 'editar', 'eliminar', 'aprobar']

export function Roles() {
  const { puede } = useAuth()
  const [roles, setRoles] = useState([])
  const [rol, setRol] = useState(null)
  const [matriz, setMatriz] = useState([])
  useEffect(() => { api('/seguridad/roles').then((r) => { setRoles(r); setRol(r[1] || r[0]) }) }, [])
  useEffect(() => { if (rol) api(`/seguridad/roles/${rol.id}/permisos`).then(setMatriz) }, [rol])

  const fijo = rol?.nombre === 'administrador' || !puede('usuarios', 'editar')
  const toggle = (i, a) => setMatriz((m) => m.map((f, j) => {
    if (j !== i) return f
    const n = { ...f, [`puede_${a}`]: !f[`puede_${a}`] }
    if (a !== 'ver' && n[`puede_${a}`]) n.puede_ver = true            // cualquier acción exige "ver"
    if (a === 'ver' && !n.puede_ver) ACCIONES.forEach((x) => (n[`puede_${x}`] = false))
    return n
  }))

  async function guardar() {
    try {
      setMatriz(await api(`/seguridad/roles/${rol.id}/permisos`, { method: 'PUT', body: matriz }))
      notificar('Permisos guardados (aplican en el próximo inicio de sesión)')
    } catch (e) { notificar(e.message, 'error') }
  }

  return (
    <>
      <Encabezado titulo="Roles y permisos">
        {!fijo && <button className="btn-primario" onClick={guardar}>Guardar cambios</button>}
      </Encabezado>
      <div className="mb-3 flex flex-wrap gap-2">
        {roles.map((r) => (
          <button key={r.id} onClick={() => setRol(r)} className={`btn capitalize ${rol?.id === r.id ? 'bg-indigo-600 text-white' : 'btn-secundario'}`}>{r.nombre}</button>
        ))}
      </div>
      {rol?.nombre === 'administrador' && <p className="mb-2 text-sm text-amber-700">Los permisos del administrador son fijos para no quedar sin acceso al sistema.</p>}
      <div className="card overflow-x-auto p-0">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr><th className="px-3 py-2 text-left">Módulo</th>{ACCIONES.map((a) => <th key={a} className="px-3 py-2">{a}</th>)}</tr>
          </thead>
          <tbody>
            {matriz.map((f, i) => (
              <tr key={f.modulo_id} className="border-t">
                <td className="px-3 py-2">{f.modulo_nombre}</td>
                {ACCIONES.map((a) => (
                  <td key={a} className="px-3 py-2 text-center">
                    <input type="checkbox" className="h-4 w-4 accent-indigo-600" disabled={fijo} checked={f[`puede_${a}`]} onChange={() => toggle(i, a)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
