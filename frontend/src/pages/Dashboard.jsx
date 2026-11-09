import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, dinero } from '../api'
import { Badge, Encabezado } from '../components/ui'

const COLOR = '#4f46e5'
const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

export default function Dashboard() {
  const [d, setD] = useState(null)
  useEffect(() => { api('/dashboard').then(setD) }, [])
  if (!d) return <p className="text-slate-400">Cargando...</p>

  const meses = d.ventas_mensuales.map((m) => ({ ...m, etiqueta: MESES[Number(m.mes.slice(5)) - 1] }))

  return (
    <>
      <Encabezado titulo="Dashboard" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi titulo="Ventas del mes" valor={dinero(d.ventas_mes)}
             nota={d.variacion_ventas == null ? `${d.facturas_mes} facturas` : `${d.variacion_ventas > 0 ? '▲' : '▼'} ${Math.abs(d.variacion_ventas)}% vs. mes anterior`}
             notaColor={d.variacion_ventas == null ? '' : d.variacion_ventas >= 0 ? 'text-emerald-600' : 'text-red-600'} />
        <Kpi titulo="Stock crítico" valor={d.stock_critico} nota="productos bajo el mínimo" notaColor={d.stock_critico ? 'text-red-600' : ''} />
        <Kpi titulo="Empleados activos" valor={d.empleados_activos} nota={`${d.solicitudes_pendientes} solicitudes pendientes`} />
        <Kpi titulo="Valor del inventario" valor={dinero(d.valor_inventario)} nota={`${d.ordenes_compra_abiertas} OC abiertas`} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Grafica titulo="Ventas de los últimos 12 meses" className="lg:col-span-2">
          <BarChart data={meses}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="etiqueta" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v) => dinero(v)} labelFormatter={(_, p) => p?.[0]?.payload.mes} />
            <Bar dataKey="total" name="Ventas" fill={COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </Grafica>

        <Grafica titulo={`Productos más vendidos (${d.dias_ranking} días)`}>
          <BarChart data={d.top_productos} layout="vertical" margin={{ left: 10 }}>
            <XAxis type="number" tick={{ fontSize: 12 }} allowDecimals={false} />
            <YAxis type="category" dataKey="sku" width={70} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [`${v} und.`, 'Unidades']} labelFormatter={(_, p) => p?.[0]?.payload.producto} />
            <Bar dataKey="unidades" fill={COLOR} radius={[0, 4, 4, 0]} />
          </BarChart>
        </Grafica>

        <div className="card lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">Alertas de stock</h3>
            <Link to="/inventario/stock" className="btn-link">Ver inventario</Link>
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr><th className="py-1">Producto</th><th>Stock</th><th>Mínimo</th><th>Estado</th></tr>
            </thead>
            <tbody>
              {d.productos_criticos.map((p) => (
                <tr key={p.producto_id} className="border-t">
                  <td className="py-1.5">{p.nombre} <span className="text-xs text-slate-400">{p.sku}</span></td>
                  <td className="font-semibold">{p.stock_total}</td><td>{p.stock_minimo}</td>
                  <td><Badge valor={p.estado_stock} /></td>
                </tr>
              ))}
              {!d.productos_criticos.length && <tr><td colSpan={4} className="py-4 text-center text-slate-400">Sin alertas 🎉</td></tr>}
            </tbody>
          </table>
        </div>

        <Grafica titulo="Empleados activos por departamento">
          <BarChart data={d.empleados_por_departamento}>
            <XAxis dataKey="departamento" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="empleados" name="Empleados" fill={COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </Grafica>
      </div>
    </>
  )
}

function Kpi({ titulo, valor, nota, notaColor = '' }) {
  return (
    <div className="card">
      <p className="text-xs font-medium uppercase text-slate-500">{titulo}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{valor}</p>
      <p className={`mt-1 text-xs ${notaColor || 'text-slate-400'}`}>{nota}</p>
    </div>
  )
}

function Grafica({ titulo, children, className = '' }) {
  return (
    <div className={`card ${className}`}>
      <h3 className="mb-2 text-sm font-semibold text-slate-700">{titulo}</h3>
      <div className="h-64"><ResponsiveContainer>{children}</ResponsiveContainer></div>
    </div>
  )
}
