import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'

// Menú: cada entrada se muestra sólo si el rol tiene permiso "ver" en su módulo
export const MENU = [
  { grupo: 'General', items: [
    { to: '/', label: 'Dashboard', modulo: 'dashboard' },
    { to: '/mi-espacio', label: 'Mi espacio', modulo: 'autoservicio' },
  ] },
  { grupo: 'Recursos Humanos', items: [
    { to: '/rrhh/empleados', label: 'Empleados', modulo: 'rrhh' },
    { to: '/rrhh/departamentos', label: 'Departamentos', modulo: 'rrhh' },
    { to: '/rrhh/puestos', label: 'Puestos', modulo: 'rrhh' },
    { to: '/rrhh/asistencia', label: 'Asistencia', modulo: 'rrhh' },
    { to: '/rrhh/solicitudes', label: 'Solicitudes', modulo: 'rrhh' },
  ] },
  { grupo: 'Inventario', items: [
    { to: '/inventario/stock', label: 'Stock', modulo: 'inventario' },
    { to: '/inventario/productos', label: 'Productos', modulo: 'inventario' },
    { to: '/inventario/categorias', label: 'Categorías', modulo: 'inventario' },
    { to: '/inventario/almacenes', label: 'Almacenes', modulo: 'inventario' },
    { to: '/inventario/movimientos', label: 'Movimientos', modulo: 'inventario' },
  ] },
  { grupo: 'Compras', items: [
    { to: '/compras/proveedores', label: 'Proveedores', modulo: 'compras' },
    { to: '/compras/ordenes', label: 'Órdenes de compra', modulo: 'compras' },
  ] },
  { grupo: 'Ventas', items: [
    { to: '/ventas/clientes', label: 'Clientes', modulo: 'ventas' },
    { to: '/ventas/cotizaciones', label: 'Cotizaciones', modulo: 'ventas' },
    { to: '/ventas/ordenes', label: 'Órdenes de venta', modulo: 'ventas' },
    { to: '/ventas/facturas', label: 'Facturas', modulo: 'ventas' },
  ] },
  { grupo: 'Administración', items: [
    { to: '/reportes', label: 'Reportes', modulo: 'reportes' },
    { to: '/auditoria', label: 'Auditoría', modulo: 'auditoria' },
    { to: '/usuarios', label: 'Usuarios', modulo: 'usuarios' },
    { to: '/roles', label: 'Roles y permisos', modulo: 'usuarios' },
  ] },
]

export default function Layout() {
  const { usuario, puede, logout } = useAuth()
  const [abierto, setAbierto] = useState(false)

  const menu = (
    <nav className="space-y-4 p-3 text-sm">
      {MENU.map((g) => {
        const items = g.items.filter((i) => puede(i.modulo))
        if (!items.length) return null
        return (
          <div key={g.grupo}>
            <p className="mb-1 px-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{g.grupo}</p>
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end onClick={() => setAbierto(false)}
                       className={({ isActive }) => `block rounded px-2 py-1.5 ${isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                {i.label}
              </NavLink>
            ))}
          </div>
        )
      })}
    </nav>
  )

  return (
    <div className="flex min-h-screen">
      {/* Sidebar escritorio */}
      <aside className="hidden w-56 shrink-0 bg-slate-900 lg:block">
        <div className="px-5 py-4 text-lg font-bold text-white">ERP<span className="text-indigo-400">lite</span></div>
        {menu}
      </aside>
      {/* Sidebar móvil */}
      {abierto && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setAbierto(false)}>
          <aside className="h-full w-60 overflow-y-auto bg-slate-900" onClick={(e) => e.stopPropagation()}>{menu}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b bg-white px-4 py-3">
          <button className="text-2xl lg:hidden" onClick={() => setAbierto(true)}>☰</button>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-600">{usuario.nombre} · <span className="capitalize text-slate-400">{usuario.rol_nombre}</span></span>
            <button className="btn-secundario py-1" onClick={logout}>Salir</button>
          </div>
        </header>
        <main className="flex-1 p-4 lg:p-6"><Outlet /></main>
      </div>
      <Toaster />
    </div>
  )
}

function Toaster() {
  const [toasts, setToasts] = useState([])
  useEffect(() => {
    const h = (e) => {
      const id = Math.random()
      setToasts((t) => [...t, { id, ...e.detail }])
      setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500)
    }
    window.addEventListener('toast', h)
    return () => window.removeEventListener('toast', h)
  }, [])
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((t) => (
        <div key={t.id} className={`max-w-sm rounded-md px-4 py-2 text-sm text-white shadow-lg ${t.tipo === 'error' ? 'bg-red-600' : 'bg-emerald-600'}`}>
          {t.texto}
        </div>
      ))}
    </div>
  )
}
