import { useEffect, useState } from 'react'
import { api, fecha, notificar } from '../api'
import { useAuth } from '../auth'
import Tabla from '../components/Tabla'
import { Badge, Campo, Encabezado, Modal, useListado, useOpciones } from '../components/ui'

const TIPOS = ['vacaciones', 'permiso', 'licencia_medica', 'otro']
const opts = (v) => v.map((x) => ({ value: x, label: x.replace('_', ' ') }))

export function Asistencia() {
  const listado = useListado('/rrhh/asistencias')
  const empleados = useOpciones('/rrhh/empleados', (e) => e.nombre_completo)
  return (
    <>
      <Encabezado titulo="Asistencia" />
      <Tabla listado={listado}
        filtros={[{ name: 'empleado_id', label: 'Empleado', options: empleados }]}
        columnas={[
          { key: 'fecha', label: 'Fecha', render: (r) => fecha(r.fecha) }, { key: 'empleado_nombre', label: 'Empleado' },
          { key: 'hora_entrada', label: 'Entrada', render: (r) => r.hora_entrada.slice(0, 5) },
          { key: 'hora_salida', label: 'Salida', render: (r) => r.hora_salida?.slice(0, 5) ?? '—' },
          { key: 'atraso', label: 'Puntualidad', render: (r) => r.atraso ? <Badge valor="atraso" color="amarillo" /> : <Badge valor="a tiempo" color="verde" /> },
        ]} />
    </>
  )
}

/** Lista de solicitudes. Si el usuario puede aprobar, ve todas y tiene botones de aprobación. */
function ListaSolicitudes({ listado }) {
  const { puede } = useAuth()
  const aprobador = puede('rrhh', 'aprobar')

  async function revisar(s, accion) {
    const comentario = accion === 'rechazar' ? prompt('Motivo del rechazo:') : ''
    if (accion === 'rechazar' && !comentario) return
    try {
      await api(`/rrhh/solicitudes/${s.id}/${accion}`, { method: 'POST', body: accion === 'cancelar' ? undefined : { comentario: comentario || null } })
      notificar(`Solicitud ${accion === 'aprobar' ? 'aprobada' : accion === 'rechazar' ? 'rechazada' : 'cancelada'}`)
      listado.recargar()
    } catch (e) { notificar(e.message, 'error') }
  }

  return (
    <Tabla listado={listado} busqueda={aprobador}
      filtros={[{ name: 'estado', label: 'Estado', options: opts(['pendiente', 'aprobada', 'rechazada', 'cancelada']) },
                { name: 'tipo', label: 'Tipo', options: opts(TIPOS) }]}
      columnas={[
        { key: 'empleado_nombre', label: 'Empleado' }, { key: 'tipo', label: 'Tipo', render: (r) => r.tipo.replace('_', ' ') },
        { key: 'fechas', label: 'Período', render: (r) => `${fecha(r.fecha_inicio)} → ${fecha(r.fecha_fin)}` },
        { key: 'dias', label: 'Días hábiles' }, { key: 'motivo', label: 'Motivo' },
        { key: 'estado', label: 'Estado', render: (r) => <span title={r.comentario_revision || ''}><Badge valor={r.estado} /></span> },
        { key: 'revisor_nombre', label: 'Revisó' },
      ]}
      acciones={(s) => s.estado === 'pendiente' && (
        <div className="flex justify-end gap-3">
          {aprobador && <button className="btn-link" onClick={() => revisar(s, 'aprobar')}>Aprobar</button>}
          {aprobador && <button className="text-sm text-red-600 hover:underline" onClick={() => revisar(s, 'rechazar')}>Rechazar</button>}
          <button className="text-sm text-slate-500 hover:underline" onClick={() => revisar(s, 'cancelar')}>Cancelar</button>
        </div>
      )} />
  )
}

export function Solicitudes() {
  const listado = useListado('/rrhh/solicitudes')
  return <><Encabezado titulo="Solicitudes de vacaciones y permisos" /><ListaSolicitudes listado={listado} /></>
}

/** Autoservicio del empleado: marcar asistencia, saldo de vacaciones y sus solicitudes. */
export function MiEspacio() {
  const { usuario } = useAuth()
  const listado = useListado('/rrhh/solicitudes', usuario.empleado_id ? { empleado_id: usuario.empleado_id } : {})
  const [saldo, setSaldo] = useState(null)
  const [asistencia, setAsistencia] = useState([])
  const [nueva, setNueva] = useState(false)

  const cargar = () => {
    api('/rrhh/mis-vacaciones').then(setSaldo).catch(() => setSaldo(null))
    api('/rrhh/mi-asistencia').then(setAsistencia).catch(() => setAsistencia([]))
  }
  useEffect(cargar, [])

  if (!usuario.empleado_id) {
    return <><Encabezado titulo="Mi espacio" /><p className="card text-sm text-slate-500">Su usuario no está vinculado a un empleado. Ingrese como <b>empleado@empresa.com</b> para probar el autoservicio.</p></>
  }

  const hoy = asistencia.find((a) => a.fecha === new Date().toLocaleDateString('en-CA'))
  async function marcar() {
    try {
      const r = await api('/rrhh/mi-asistencia/marcar', { method: 'POST' })
      notificar(r.hora_salida ? `Salida registrada ${r.hora_salida.slice(0, 5)}` : `Entrada registrada ${r.hora_entrada.slice(0, 5)}`)
      cargar()
    } catch (e) { notificar(e.message, 'error') }
  }

  return (
    <>
      <Encabezado titulo={`Hola, ${usuario.empleado_nombre}`}>
        <button className="btn-primario" onClick={() => setNueva(true)}>+ Nueva solicitud</button>
      </Encabezado>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs font-medium uppercase text-slate-500">Asistencia de hoy</p>
          <p className="mt-1 text-sm">Entrada: <b>{hoy?.hora_entrada?.slice(0, 5) ?? '—'}</b> · Salida: <b>{hoy?.hora_salida?.slice(0, 5) ?? '—'}</b></p>
          <button className="btn-primario mt-2 w-full" disabled={hoy?.hora_salida} onClick={marcar}>
            {!hoy ? 'Marcar entrada' : !hoy.hora_salida ? 'Marcar salida' : 'Jornada completa'}
          </button>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase text-slate-500">Vacaciones disponibles</p>
          <p className="mt-1 text-3xl font-bold text-slate-800">{saldo?.dias_disponibles ?? '—'}</p>
          <p className="text-xs text-slate-400">{saldo && `${saldo.dias_asignados} asignados · ${saldo.dias_tomados} tomados · ${saldo.dias_pendientes} pendientes`}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase text-slate-500">Días trabajados este mes</p>
          <p className="mt-1 text-3xl font-bold text-slate-800">{asistencia.length}</p>
          <p className="text-xs text-slate-400">{asistencia.filter((a) => a.atraso).length} atrasos</p>
        </div>
      </div>
      <h2 className="mb-2 font-semibold text-slate-700">Mis solicitudes</h2>
      <ListaSolicitudes listado={listado} />
      {nueva && <NuevaSolicitud onClose={() => setNueva(false)} onOk={() => { setNueva(false); listado.recargar(); cargar() }} />}
    </>
  )
}

function NuevaSolicitud({ onClose, onOk }) {
  const [f, setF] = useState({ tipo: 'vacaciones', fecha_inicio: '', fecha_fin: '', motivo: '' })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  async function guardar(e) {
    e.preventDefault()
    try {
      await api('/rrhh/solicitudes', { method: 'POST', body: f })
      notificar('Solicitud enviada para aprobación')
      onOk()
    } catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo="Nueva solicitud" onClose={onClose}>
      <form onSubmit={guardar} className="space-y-3">
        <Campo label="Tipo"><select className="input" value={f.tipo} onChange={set('tipo')}>{opts(TIPOS).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Desde"><input className="input" type="date" required value={f.fecha_inicio} onChange={set('fecha_inicio')} /></Campo>
          <Campo label="Hasta"><input className="input" type="date" required value={f.fecha_fin} onChange={set('fecha_fin')} /></Campo>
        </div>
        <Campo label="Motivo"><input className="input" required minLength={5} value={f.motivo} onChange={set('motivo')} /></Campo>
        {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <div className="flex justify-end gap-2"><button type="button" className="btn-secundario" onClick={onClose}>Cancelar</button><button className="btn-primario">Enviar</button></div>
      </form>
    </Modal>
  )
}
