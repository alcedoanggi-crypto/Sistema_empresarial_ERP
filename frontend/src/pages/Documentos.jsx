// Documentos con líneas (órdenes de compra, cotizaciones, órdenes de venta) y facturas.
import { useEffect, useState } from 'react'
import { api, descargar, dinero, fecha, fechaHora, notificar } from '../api'
import { useAuth } from '../auth'
import BotonesReporte from '../components/BotonesReporte'
import Tabla from '../components/Tabla'
import { Badge, Campo, Encabezado, Modal, useListado, useOpciones } from '../components/ui'

const estados = (...v) => v.map((x) => ({ value: x, label: x }))

/**
 * cfg: { titulo, url, modulo, tercero: {campo, label, url, etiqueta, columna},
 *        conAlmacen, conValidez, conEntrega, precio: 'costo_unitario'|'precio_unitario', precioDe, conDescuento,
 *        estados, acciones: (fila, ejecutar, puede) => JSX, editable: estado }
 */
function DocumentoPage({ cfg }) {
  const { puede } = useAuth()
  const listado = useListado(cfg.url)
  const [nuevo, setNuevo] = useState(false)
  const [viendo, setViendo] = useState(null)

  async function ejecutar(fila, accion, body, mensaje) {
    try {
      const r = await api(`${cfg.url}/${fila.id}/${accion}`, { method: 'POST', body })
      notificar(mensaje || 'Operación realizada')
      listado.recargar()
      return r
    } catch (e) { notificar(e.message, 'error') }
  }

  return (
    <>
      <Encabezado titulo={cfg.titulo}>
        {cfg.reportes && <BotonesReporte reportes={cfg.reportes} />}
        {puede(cfg.modulo, 'crear') && <button className="btn-primario" onClick={() => setNuevo(true)}>+ Nuevo</button>}
      </Encabezado>
      <Tabla listado={listado}
        filtros={[{ name: 'estado', label: 'Estado', options: estados(...cfg.estados) }]}
        columnas={[
          { key: 'numero', label: 'Número', render: (r) => <span className="font-medium">{r.numero}</span> },
          { key: 'tercero', label: cfg.tercero.label, render: (r) => r[cfg.tercero.columna] },
          { key: 'fecha', label: 'Fecha', render: (r) => fecha(r.fecha_emision || r.fecha) },
          ...(cfg.conAlmacen ? [{ key: 'almacen_nombre', label: 'Almacén' }] : []),
          { key: 'total', label: 'Total', render: (r) => dinero(r.total) },
          { key: 'estado', label: 'Estado', render: (r) => <Badge valor={r.estado} /> },
        ]}
        acciones={(r) => (
          <div className="flex justify-end gap-3">
            <button className="btn-link" onClick={() => setViendo(r.id)}>Ver</button>
            {cfg.acciones(r, ejecutar, puede)}
          </div>
        )} />
      {nuevo && <NuevoDocumento cfg={cfg} onClose={() => setNuevo(false)} onOk={() => { setNuevo(false); listado.recargar() }} />}
      {viendo && <VerDocumento url={`${cfg.url}/${viendo}`} cfg={cfg} onClose={() => setViendo(null)} />}
    </>
  )
}

function NuevoDocumento({ cfg, onClose, onOk }) {
  const terceros = useOpciones(cfg.tercero.url, cfg.tercero.etiqueta)
  const almacenes = useOpciones(cfg.conAlmacen ? '/inventario/almacenes' : null)
  const productos = useOpciones('/inventario/productos', (p) => `${p.sku} · ${p.nombre}`)
  const [cab, setCab] = useState({ [cfg.tercero.campo]: '', almacen_id: '', fecha_validez: '', fecha_entrega_esperada: '', notas: '' })
  const [lineas, setLineas] = useState([{ producto_id: '', cantidad: 1, precio: '', descuento_pct: 0 }])
  const [error, setError] = useState('')

  const setLinea = (i, k, v) => setLineas((ls) => ls.map((l, j) => {
    if (j !== i) return l
    const nueva = { ...l, [k]: v }
    if (k === 'producto_id') nueva.precio = productos.find((p) => p.value === +v)?.raw[cfg.precioDe] ?? ''
    return nueva
  }))
  const total = lineas.reduce((s, l) => s + (+l.cantidad || 0) * (+l.precio || 0) * (1 - (+l.descuento_pct || 0) / 100), 0)

  async function guardar(e) {
    e.preventDefault()
    const body = {
      [cfg.tercero.campo]: +cab[cfg.tercero.campo],
      notas: cab.notas || null,
      ...(cfg.conAlmacen && { almacen_id: +cab.almacen_id }),
      ...(cfg.conValidez && { fecha_validez: cab.fecha_validez }),
      ...(cfg.conEntrega && { fecha_entrega_esperada: cab.fecha_entrega_esperada || null }),
      detalles: lineas.map((l) => ({
        producto_id: +l.producto_id, cantidad: +l.cantidad, [cfg.precio]: +l.precio,
        ...(cfg.conDescuento && { descuento_pct: +l.descuento_pct || 0 }),
      })),
    }
    try {
      await api(cfg.url, { method: 'POST', body })
      notificar('Documento creado')
      onOk()
    } catch (err) { setError(err.message) }
  }

  return (
    <Modal titulo={`Nuevo · ${cfg.titulo}`} onClose={onClose} ancho="max-w-3xl">
      <form onSubmit={guardar} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Campo label={cfg.tercero.label + ' *'}>
            <select className="input" required value={cab[cfg.tercero.campo]} onChange={(e) => setCab({ ...cab, [cfg.tercero.campo]: e.target.value })}>
              <option value="">— Seleccione —</option>{terceros.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </Campo>
          {cfg.conAlmacen && (
            <Campo label="Almacén *">
              <select className="input" required value={cab.almacen_id} onChange={(e) => setCab({ ...cab, almacen_id: e.target.value })}>
                <option value="">— Seleccione —</option>{almacenes.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Campo>
          )}
          {cfg.conValidez && <Campo label="Válida hasta *"><input className="input" type="date" required value={cab.fecha_validez} onChange={(e) => setCab({ ...cab, fecha_validez: e.target.value })} /></Campo>}
          {cfg.conEntrega && <Campo label="Entrega esperada"><input className="input" type="date" value={cab.fecha_entrega_esperada} onChange={(e) => setCab({ ...cab, fecha_entrega_esperada: e.target.value })} /></Campo>}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr><th className="pb-1">Producto</th><th className="w-20">Cant.</th><th className="w-28">Precio</th>{cfg.conDescuento && <th className="w-20">Desc. %</th>}<th className="w-24 text-right">Subtotal</th><th className="w-6" /></tr>
            </thead>
            <tbody>
              {lineas.map((l, i) => (
                <tr key={i}>
                  <td className="pr-2 pb-2"><select className="input min-w-48" required value={l.producto_id} onChange={(e) => setLinea(i, 'producto_id', e.target.value)}>
                    <option value="">— Producto —</option>{productos.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></td>
                  <td className="pr-2 pb-2"><input className="input" type="number" min="1" required value={l.cantidad} onChange={(e) => setLinea(i, 'cantidad', e.target.value)} /></td>
                  <td className="pr-2 pb-2"><input className="input" type="number" step="0.01" min="0" required value={l.precio} onChange={(e) => setLinea(i, 'precio', e.target.value)} /></td>
                  {cfg.conDescuento && <td className="pr-2 pb-2"><input className="input" type="number" min="0" max="100" value={l.descuento_pct} onChange={(e) => setLinea(i, 'descuento_pct', e.target.value)} /></td>}
                  <td className="pb-2 text-right">{dinero((+l.cantidad || 0) * (+l.precio || 0) * (1 - (+l.descuento_pct || 0) / 100))}</td>
                  <td className="pb-2 pl-2">{lineas.length > 1 && <button type="button" className="text-red-500" onClick={() => setLineas(lineas.filter((_, j) => j !== i))}>×</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="btn-link" onClick={() => setLineas([...lineas, { producto_id: '', cantidad: 1, precio: '', descuento_pct: 0 }])}>+ Agregar línea</button>
        </div>
        <Campo label="Notas"><input className="input" value={cab.notas} onChange={(e) => setCab({ ...cab, notas: e.target.value })} /></Campo>
        <p className="text-right text-sm text-slate-600">Total antes de impuestos: <b>{dinero(total)}</b></p>
        {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <div className="flex justify-end gap-2"><button type="button" className="btn-secundario" onClick={onClose}>Cancelar</button><button className="btn-primario">Guardar</button></div>
      </form>
    </Modal>
  )
}

function VerDocumento({ url, cfg, onClose }) {
  const [doc, setDoc] = useState(null)
  useEffect(() => { api(url).then(setDoc) }, [url])
  return (
    <Modal titulo={doc ? `${doc.numero}` : 'Cargando...'} onClose={onClose} ancho="max-w-2xl">
      {doc && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 text-sm">
            <p><span className="text-slate-500">{cfg.tercero.label}:</span> {doc[cfg.tercero.columna]}</p>
            <p><span className="text-slate-500">Estado:</span> <Badge valor={doc.estado} /></p>
            <p><span className="text-slate-500">Fecha:</span> {fecha(doc.fecha_emision || doc.fecha)}</p>
            {doc.almacen_nombre && <p><span className="text-slate-500">Almacén:</span> {doc.almacen_nombre}</p>}
            {doc.factura_numero && <p><span className="text-slate-500">Factura:</span> {doc.factura_numero}</p>}
            {doc.notas && <p className="col-span-2"><span className="text-slate-500">Notas:</span> {doc.notas}</p>}
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-2">Producto</th><th>Cant.</th><th>Precio</th><th className="p-2 text-right">Subtotal</th></tr></thead>
            <tbody>
              {doc.detalles.map((d) => (
                <tr key={d.id} className="border-t">
                  <td className="p-2">{d.producto_nombre}</td><td>{d.cantidad}</td>
                  <td>{dinero(d.precio_unitario ?? d.costo_unitario)}{d.descuento_pct > 0 && <span className="text-xs text-slate-400"> −{d.descuento_pct}%</span>}</td>
                  <td className="p-2 text-right">{dinero(d.subtotal)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-right font-semibold">Total: {dinero(doc.total)}</p>
        </>
      )}
    </Modal>
  )
}

// ---------------------------------------------------------------------------
export function OrdenesCompra() {
  return <DocumentoPage cfg={{
    titulo: 'Órdenes de compra', url: '/compras/ordenes', modulo: 'compras',
    reportes: [{ clave: 'compras', titulo: 'Compras' }],
    tercero: { campo: 'proveedor_id', label: 'Proveedor', url: '/compras/proveedores', etiqueta: (p) => p.razon_social, columna: 'proveedor_nombre' },
    conAlmacen: true, conEntrega: true, precio: 'costo_unitario', precioDe: 'precio_costo',
    estados: ['borrador', 'aprobada', 'recibida', 'cancelada'],
    acciones: (r, ejecutar, puede) => <>
      {r.estado === 'borrador' && puede('compras', 'aprobar') && <button className="btn-link" onClick={() => ejecutar(r, 'aprobar', undefined, 'Orden aprobada')}>Aprobar</button>}
      {r.estado === 'aprobada' && puede('compras', 'editar') && <button className="btn-link" onClick={() => ejecutar(r, 'recibir', undefined, 'Mercadería recibida: stock actualizado')}>Recibir</button>}
      {['borrador', 'aprobada'].includes(r.estado) && puede('compras', 'editar') &&
        <button className="text-sm text-red-600 hover:underline" onClick={() => confirm('¿Cancelar la orden?') && ejecutar(r, 'cancelar', undefined, 'Orden cancelada')}>Cancelar</button>}
    </>,
  }} />
}

export function Cotizaciones() {
  const almacenes = useOpciones('/inventario/almacenes')
  const [convirtiendo, setConvirtiendo] = useState(null)
  return <>
    <DocumentoPage cfg={{
      titulo: 'Cotizaciones', url: '/ventas/cotizaciones', modulo: 'ventas',
      tercero: { campo: 'cliente_id', label: 'Cliente', url: '/ventas/clientes', etiqueta: (c) => c.nombre, columna: 'cliente_nombre' },
      conValidez: true, conDescuento: true, precio: 'precio_unitario', precioDe: 'precio_venta',
      estados: ['borrador', 'enviada', 'aceptada', 'rechazada', 'vencida'],
      acciones: (r, ejecutar, puede) => <>
        {r.estado === 'borrador' && puede('ventas', 'editar') && <button className="btn-link" onClick={() => ejecutar(r, 'enviar', undefined, 'Cotización enviada')}>Enviar</button>}
        {['borrador', 'enviada'].includes(r.estado) && puede('ventas', 'crear') && <button className="btn-link" onClick={() => setConvirtiendo({ r, ejecutar })}>Convertir en venta</button>}
        {['borrador', 'enviada'].includes(r.estado) && puede('ventas', 'editar') && <button className="text-sm text-red-600 hover:underline" onClick={() => ejecutar(r, 'rechazar', undefined, 'Cotización rechazada')}>Rechazar</button>}
      </>,
    }} />
    {convirtiendo && (
      <Modal titulo={`Convertir ${convirtiendo.r.numero} en orden de venta`} onClose={() => setConvirtiendo(null)}>
        <p className="mb-2 text-sm text-slate-600">¿Desde qué almacén se despachará?</p>
        <div className="flex flex-wrap gap-2">
          {almacenes.map((a) => (
            <button key={a.value} className="btn-secundario" onClick={async () => {
              await convirtiendo.ejecutar(convirtiendo.r, 'convertir', { almacen_id: a.value }, 'Orden de venta generada')
              setConvirtiendo(null)
            }}>{a.label}</button>
          ))}
        </div>
      </Modal>
    )}
  </>
}

export function OrdenesVenta() {
  return <DocumentoPage cfg={{
    titulo: 'Órdenes de venta', url: '/ventas/ordenes', modulo: 'ventas',
    reportes: [{ clave: 'ventas', titulo: 'Ventas' }],
    tercero: { campo: 'cliente_id', label: 'Cliente', url: '/ventas/clientes', etiqueta: (c) => c.nombre, columna: 'cliente_nombre' },
    conAlmacen: true, conDescuento: true, precio: 'precio_unitario', precioDe: 'precio_venta',
    estados: ['pendiente', 'facturada', 'cancelada'],
    acciones: (r, ejecutar, puede) => <>
      {r.estado === 'pendiente' && puede('ventas', 'crear') &&
        <button className="btn-link" onClick={() => ejecutar(r, 'facturar', undefined, 'Factura emitida: inventario descontado')}>Facturar</button>}
      {r.estado === 'pendiente' && puede('ventas', 'editar') &&
        <button className="text-sm text-red-600 hover:underline" onClick={() => confirm('¿Cancelar la orden?') && ejecutar(r, 'cancelar', undefined, 'Orden cancelada')}>Cancelar</button>}
    </>,
  }} />
}

export function Facturas() {
  const { puede } = useAuth()
  const listado = useListado('/ventas/facturas')

  async function anular(f) {
    const motivo = prompt(`Motivo de anulación de ${f.numero} (la mercadería vuelve al almacén):`)
    if (!motivo) return
    try {
      await api(`/ventas/facturas/${f.id}/anular`, { method: 'POST', body: { motivo } })
      notificar('Factura anulada y stock devuelto')
      listado.recargar()
    } catch (e) { notificar(e.message, 'error') }
  }

  return (
    <>
      <Encabezado titulo="Facturas">
        <BotonesReporte reportes={[{ clave: 'ventas', titulo: 'Ventas' }]} />
      </Encabezado>
      <Tabla listado={listado}
        filtros={[{ name: 'estado', label: 'Estado', options: estados('emitida', 'anulada') }]}
        columnas={[
          { key: 'numero', label: 'Número', render: (r) => <span className="font-medium">{r.numero}</span> },
          { key: 'cliente_nombre', label: 'Cliente' }, { key: 'orden_venta_numero', label: 'Orden' },
          { key: 'fecha_emision', label: 'Emisión', render: (r) => fechaHora(r.fecha_emision) },
          { key: 'subtotal', label: 'Subtotal', render: (r) => dinero(r.subtotal - r.descuento) },
          { key: 'iva', label: 'IVA', render: (r) => dinero(r.iva) },
          { key: 'total', label: 'Total', render: (r) => <b>{dinero(r.total)}</b> },
          { key: 'estado', label: 'Estado', render: (r) => <Badge valor={r.estado} /> },
        ]}
        acciones={(r) => (
          <div className="flex justify-end gap-3">
            <button className="btn-link" onClick={() => descargar(`/ventas/facturas/${r.id}/pdf`, `factura-${r.numero}.pdf`).catch((e) => notificar(e.message, 'error'))}>PDF</button>
            {r.estado === 'emitida' && puede('ventas', 'aprobar') && <button className="text-sm text-red-600 hover:underline" onClick={() => anular(r)}>Anular</button>}
          </div>
        )} />
    </>
  )
}
