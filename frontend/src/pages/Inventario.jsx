import { useState } from 'react'
import { api, dinero, fechaHora, notificar } from '../api'
import { useAuth } from '../auth'
import BotonesReporte from '../components/BotonesReporte'
import Tabla from '../components/Tabla'
import { Badge, Campo, Encabezado, Modal, useListado, useOpciones } from '../components/ui'

// Stock consolidado: viene de la vista v_stock_productos
export function Stock() {
  const listado = useListado('/inventario/stock')
  const cats = useOpciones('/inventario/categorias', (c) => c.nombre).map((o) => ({ value: o.label, label: o.label }))
  return (
    <>
      <Encabezado titulo="Stock por producto">
        <BotonesReporte reportes={[{ clave: 'inventario', titulo: 'Inventario' }, { clave: 'stock-critico', titulo: 'Stock crítico' }]} />
      </Encabezado>
      <Tabla listado={listado}
        filtros={[
          { name: 'estado', label: 'Estado', options: ['normal', 'critico', 'agotado'].map((v) => ({ value: v, label: v })) },
          { name: 'categoria', label: 'Categoría', options: cats },
        ]}
        columnas={[
          { key: 'sku', label: 'SKU' }, { key: 'nombre', label: 'Producto' }, { key: 'categoria', label: 'Categoría' },
          { key: 'stock_total', label: 'Stock', render: (r) => `${r.stock_total} ${r.unidad_medida}` },
          { key: 'stock_minimo', label: 'Mínimo' },
          { key: 'valor_inventario', label: 'Valor', render: (r) => dinero(r.valor_inventario) },
          { key: 'estado_stock', label: 'Estado', render: (r) => <Badge valor={r.estado_stock} /> },
        ]} />
    </>
  )
}

// Kardex: historial inmutable de entradas y salidas
export function Movimientos() {
  const { puede } = useAuth()
  const listado = useListado('/inventario/movimientos')
  const almacenes = useOpciones('/inventario/almacenes')
  const [ajuste, setAjuste] = useState(false)
  return (
    <>
      <Encabezado titulo="Movimientos de inventario">
        <BotonesReporte reportes={[{ clave: 'movimientos', titulo: 'Movimientos' }]} />
        {puede('inventario', 'crear') && <button className="btn-primario" onClick={() => setAjuste(true)}>+ Ajuste manual</button>}
      </Encabezado>
      <Tabla listado={listado}
        filtros={[
          { name: 'tipo', label: 'Tipo', options: [{ value: 'entrada', label: 'entrada' }, { value: 'salida', label: 'salida' }] },
          { name: 'origen', label: 'Origen', options: ['inicial', 'compra', 'venta', 'ajuste', 'anulacion'].map((v) => ({ value: v, label: v })) },
          { name: 'almacen_id', label: 'Almacén', options: almacenes },
        ]}
        columnas={[
          { key: 'created_at', label: 'Fecha', render: (r) => fechaHora(r.created_at) },
          { key: 'producto_nombre', label: 'Producto' }, { key: 'almacen_nombre', label: 'Almacén' },
          { key: 'tipo', label: 'Tipo', render: (r) => <Badge valor={r.tipo} /> }, { key: 'origen', label: 'Origen' },
          { key: 'cantidad', label: 'Cantidad', render: (r) => (r.tipo === 'salida' ? '-' : '+') + r.cantidad },
          { key: 'documento', label: 'Documento' }, { key: 'usuario_nombre', label: 'Usuario' },
        ]} />
      {ajuste && <AjusteModal almacenes={almacenes} onClose={() => setAjuste(false)} onOk={() => { setAjuste(false); listado.recargar() }} />}
    </>
  )
}

function AjusteModal({ almacenes, onClose, onOk }) {
  const productos = useOpciones('/inventario/productos', (p) => `${p.sku} · ${p.nombre}`)
  const [f, setF] = useState({ producto_id: '', almacen_id: '', tipo: 'entrada', cantidad: 1, nota: '' })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function guardar(e) {
    e.preventDefault()
    try {
      await api('/inventario/movimientos', { method: 'POST', body: { ...f, producto_id: +f.producto_id, almacen_id: +f.almacen_id, cantidad: +f.cantidad } })
      notificar('Ajuste registrado')
      onOk()
    } catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo="Ajuste manual de inventario" onClose={onClose}>
      <form onSubmit={guardar} className="space-y-3">
        <Campo label="Producto"><select className="input" required value={f.producto_id} onChange={set('producto_id')}>
          <option value="">— Seleccione —</option>{productos.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></Campo>
        <Campo label="Almacén"><select className="input" required value={f.almacen_id} onChange={set('almacen_id')}>
          <option value="">— Seleccione —</option>{almacenes.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Tipo"><select className="input" value={f.tipo} onChange={set('tipo')}><option>entrada</option><option>salida</option></select></Campo>
          <Campo label="Cantidad"><input className="input" type="number" min="1" required value={f.cantidad} onChange={set('cantidad')} /></Campo>
        </div>
        <Campo label="Motivo"><input className="input" required minLength={3} value={f.nota} onChange={set('nota')} placeholder="Conteo físico, merma..." /></Campo>
        {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
        <div className="flex justify-end gap-2"><button type="button" className="btn-secundario" onClick={onClose}>Cancelar</button><button className="btn-primario">Registrar</button></div>
      </form>
    </Modal>
  )
}
