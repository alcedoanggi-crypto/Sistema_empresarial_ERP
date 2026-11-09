import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import Layout, { MENU } from './components/Layout'
import './index.css'
import { Auditoria, Reportes, Roles } from './pages/Admin'
import { Almacenes, Categorias, Clientes, Departamentos, Empleados, Productos, Proveedores, Puestos, Usuarios } from './pages/Catalogos'
import Dashboard from './pages/Dashboard'
import { Cotizaciones, Facturas, OrdenesCompra, OrdenesVenta } from './pages/Documentos'
import { Movimientos, Stock } from './pages/Inventario'
import Login from './pages/Login'
import { Asistencia, MiEspacio, Solicitudes } from './pages/RRHH'

const PAGINAS = {
  '/': Dashboard, '/mi-espacio': MiEspacio,
  '/rrhh/empleados': Empleados, '/rrhh/departamentos': Departamentos, '/rrhh/puestos': Puestos,
  '/rrhh/asistencia': Asistencia, '/rrhh/solicitudes': Solicitudes,
  '/inventario/stock': Stock, '/inventario/productos': Productos, '/inventario/categorias': Categorias,
  '/inventario/almacenes': Almacenes, '/inventario/movimientos': Movimientos,
  '/compras/proveedores': Proveedores, '/compras/ordenes': OrdenesCompra,
  '/ventas/clientes': Clientes, '/ventas/cotizaciones': Cotizaciones, '/ventas/ordenes': OrdenesVenta, '/ventas/facturas': Facturas,
  '/reportes': Reportes, '/auditoria': Auditoria, '/usuarios': Usuarios, '/roles': Roles,
}
const RUTAS = MENU.flatMap((g) => g.items)

function Protegido() {
  const { usuario, cargando, puede } = useAuth()
  if (cargando) return <p className="p-8 text-slate-400">Cargando...</p>
  if (!usuario) return <Navigate to="/login" replace />
  const inicio = RUTAS.find((r) => puede(r.modulo))?.to || '/'
  return (
    <Routes>
      <Route element={<Layout />}>
        {RUTAS.filter((r) => puede(r.modulo)).map((r) => {
          const Pagina = PAGINAS[r.to]
          return <Route key={r.to} path={r.to} element={<Pagina />} />
        })}
        <Route path="*" element={<Navigate to={inicio} replace />} />
      </Route>
    </Routes>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<Protegido />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
)
