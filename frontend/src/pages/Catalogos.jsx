// Catálogos simples: sólo configuración sobre <CrudPage/>.
import { dinero, fecha } from '../api'
import CrudPage from '../components/CrudPage'
import { Badge, useOpciones } from '../components/ui'

const opts = (...vals) => vals.map((v) => ({ value: v, label: v.replace('_', ' ') }))

export function Departamentos() {
  return (
    <CrudPage titulo="Departamentos" url="/rrhh/departamentos" modulo="rrhh"
      columnas={[{ key: 'codigo', label: 'Código' }, { key: 'nombre', label: 'Nombre' }, { key: 'descripcion', label: 'Descripción' }]}
      campos={[
        { name: 'codigo', label: 'Código', required: true, upper: true, placeholder: 'VEN' },
        { name: 'nombre', label: 'Nombre', required: true },
        { name: 'descripcion', label: 'Descripción', type: 'textarea' },
      ]} />
  )
}

export function Puestos() {
  const deps = useOpciones('/rrhh/departamentos')
  return (
    <CrudPage titulo="Puestos" url="/rrhh/puestos" modulo="rrhh"
      filtros={[{ name: 'departamento_id', label: 'Departamento', options: deps }]}
      columnas={[
        { key: 'nombre', label: 'Puesto' }, { key: 'departamento_nombre', label: 'Departamento' },
        { key: 'salario_min', label: 'Salario mín.', render: (r) => dinero(r.salario_min) },
        { key: 'salario_max', label: 'Salario máx.', render: (r) => dinero(r.salario_max) },
      ]}
      campos={[
        { name: 'departamento_id', label: 'Departamento', type: 'select', options: deps, required: true },
        { name: 'nombre', label: 'Nombre', required: true },
        { name: 'salario_min', label: 'Salario mínimo', type: 'number', required: true },
        { name: 'salario_max', label: 'Salario máximo', type: 'number', required: true },
      ]} />
  )
}

export function Empleados() {
  const deps = useOpciones('/rrhh/departamentos')
  return (
    <CrudPage titulo="Empleados" url="/rrhh/empleados" modulo="rrhh"
      reportes={[{ clave: 'empleados', titulo: 'Nómina' }]}
      filtros={[
        { name: 'departamento_id', label: 'Departamento', options: deps },
        { name: 'estado', label: 'Estado', options: opts('activo', 'licencia', 'inactivo') },
      ]}
      columnas={[
        { key: 'codigo', label: 'Código' }, { key: 'nombre_completo', label: 'Nombre' }, { key: 'cedula', label: 'Cédula' },
        { key: 'departamento_nombre', label: 'Departamento' }, { key: 'puesto_nombre', label: 'Puesto' },
        { key: 'fecha_ingreso', label: 'Ingreso', render: (r) => fecha(r.fecha_ingreso) },
        { key: 'salario', label: 'Salario', render: (r) => dinero(r.salario) },
        { key: 'estado', label: 'Estado', render: (r) => <Badge valor={r.estado} /> },
      ]}
      campos={[
        { name: 'codigo', label: 'Código', required: true, upper: true },
        { name: 'cedula', label: 'Cédula (10 dígitos)', required: true },
        { name: 'nombres', label: 'Nombres', required: true },
        { name: 'apellidos', label: 'Apellidos', required: true },
        { name: 'email', label: 'Correo', type: 'email', required: true },
        { name: 'telefono', label: 'Teléfono' },
        { name: 'fecha_nacimiento', label: 'Fecha de nacimiento', type: 'date', required: true },
        { name: 'fecha_ingreso', label: 'Fecha de ingreso', type: 'date', required: true },
        { name: 'puesto_id', label: 'Puesto', type: 'select', optionsUrl: '/rrhh/puestos',
          optionLabel: (p) => `${p.nombre} (${p.departamento_nombre})`, required: true },
        { name: 'salario', label: 'Salario', type: 'number', required: true },
        { name: 'jefe_id', label: 'Jefe inmediato', type: 'select', optionsUrl: '/rrhh/empleados', optionLabel: (e) => e.nombre_completo },
        { name: 'estado', label: 'Estado', type: 'select', options: opts('activo', 'licencia', 'inactivo'), default: 'activo', required: true },
        { name: 'dias_vacaciones_anuales', label: 'Días de vacaciones/año', type: 'number', default: 15 },
        { name: 'direccion', label: 'Dirección', type: 'textarea' },
      ]} />
  )
}

export function Categorias() {
  return (
    <CrudPage titulo="Categorías" url="/inventario/categorias" modulo="inventario"
      columnas={[{ key: 'nombre', label: 'Nombre' }, { key: 'descripcion', label: 'Descripción' }]}
      campos={[{ name: 'nombre', label: 'Nombre', required: true }, { name: 'descripcion', label: 'Descripción', type: 'textarea' }]} />
  )
}

export function Almacenes() {
  return (
    <CrudPage titulo="Almacenes" url="/inventario/almacenes" modulo="inventario"
      columnas={[
        { key: 'codigo', label: 'Código' }, { key: 'nombre', label: 'Nombre' }, { key: 'direccion', label: 'Dirección' },
        { key: 'activo', label: 'Estado', render: (r) => <Badge valor={r.activo ? 'activo' : 'inactivo'} /> },
      ]}
      campos={[
        { name: 'codigo', label: 'Código', required: true, upper: true }, { name: 'nombre', label: 'Nombre', required: true },
        { name: 'direccion', label: 'Dirección' }, { name: 'activo', label: 'Activo', type: 'checkbox' },
      ]} />
  )
}

export function Productos() {
  const cats = useOpciones('/inventario/categorias')
  return (
    <CrudPage titulo="Productos" url="/inventario/productos" modulo="inventario"
      reportes={[{ clave: 'inventario', titulo: 'Inventario' }]}
      filtros={[{ name: 'categoria_id', label: 'Categoría', options: cats }]}
      columnas={[
        { key: 'sku', label: 'SKU' }, { key: 'nombre', label: 'Producto' }, { key: 'categoria_nombre', label: 'Categoría' },
        { key: 'precio_costo', label: 'Costo', render: (r) => dinero(r.precio_costo) },
        { key: 'precio_venta', label: 'Precio', render: (r) => dinero(r.precio_venta) },
        { key: 'stock_total', label: 'Stock', render: (r) => (
          <span className={r.stock_total <= r.stock_minimo ? 'font-semibold text-red-600' : ''}>{r.stock_total}</span>) },
        { key: 'stock_minimo', label: 'Mínimo' },
      ]}
      campos={[
        { name: 'sku', label: 'SKU', required: true, upper: true, placeholder: 'LAP-001' },
        { name: 'nombre', label: 'Nombre', required: true },
        { name: 'categoria_id', label: 'Categoría', type: 'select', options: cats, required: true },
        { name: 'unidad_medida', label: 'Unidad', type: 'select', options: opts('UND', 'KG', 'LT', 'MT', 'CAJA', 'PAQ'), default: 'UND' },
        { name: 'precio_costo', label: 'Precio de costo', type: 'number', required: true },
        { name: 'precio_venta', label: 'Precio de venta', type: 'number', required: true },
        { name: 'stock_minimo', label: 'Stock mínimo', type: 'number', default: 0 },
        { name: 'aplica_iva', label: 'Grava IVA', type: 'checkbox' },
        { name: 'descripcion', label: 'Descripción', type: 'textarea' },
      ]} />
  )
}

export function Proveedores() {
  return (
    <CrudPage titulo="Proveedores" url="/compras/proveedores" modulo="compras"
      columnas={[
        { key: 'ruc', label: 'RUC' }, { key: 'razon_social', label: 'Razón social' }, { key: 'nombre_contacto', label: 'Contacto' },
        { key: 'email', label: 'Correo' }, { key: 'dias_credito', label: 'Crédito (días)' },
      ]}
      campos={[
        { name: 'ruc', label: 'RUC (13 dígitos)', required: true }, { name: 'razon_social', label: 'Razón social', required: true },
        { name: 'nombre_contacto', label: 'Contacto' }, { name: 'email', label: 'Correo', type: 'email' },
        { name: 'telefono', label: 'Teléfono' }, { name: 'dias_credito', label: 'Días de crédito', type: 'number', default: 0 },
        { name: 'direccion', label: 'Dirección', type: 'textarea' },
      ]} />
  )
}

export function Clientes() {
  const tipos = opts('cedula', 'ruc', 'pasaporte')
  return (
    <CrudPage titulo="Clientes" url="/ventas/clientes" modulo="ventas"
      filtros={[{ name: 'tipo_identificacion', label: 'Tipo', options: tipos }]}
      columnas={[
        { key: 'identificacion', label: 'Identificación' }, { key: 'tipo_identificacion', label: 'Tipo' },
        { key: 'nombre', label: 'Nombre' }, { key: 'email', label: 'Correo' }, { key: 'telefono', label: 'Teléfono' },
      ]}
      campos={[
        { name: 'tipo_identificacion', label: 'Tipo de identificación', type: 'select', options: tipos, required: true },
        { name: 'identificacion', label: 'Identificación', required: true, upper: true },
        { name: 'nombre', label: 'Nombre / Razón social', required: true }, { name: 'email', label: 'Correo', type: 'email' },
        { name: 'telefono', label: 'Teléfono' }, { name: 'direccion', label: 'Dirección', type: 'textarea' },
      ]} />
  )
}

export function Usuarios() {
  const roles = useOpciones('/seguridad/roles')
  return (
    <CrudPage titulo="Usuarios" url="/seguridad/usuarios" modulo="usuarios"
      filtros={[{ name: 'rol_id', label: 'Rol', options: roles }]}
      columnas={[
        { key: 'nombre', label: 'Nombre' }, { key: 'email', label: 'Correo' },
        { key: 'rol_nombre', label: 'Rol', render: (r) => <span className="capitalize">{r.rol_nombre}</span> },
        { key: 'empleado_nombre', label: 'Empleado' },
        { key: 'activo', label: 'Estado', render: (r) => <Badge valor={r.activo ? 'activo' : 'inactivo'} /> },
      ]}
      campos={[
        { name: 'nombre', label: 'Nombre', required: true }, { name: 'email', label: 'Correo', type: 'email', required: true },
        { name: 'password', label: 'Contraseña (mín. 8)', type: 'password', required: true },
        { name: 'rol_id', label: 'Rol', type: 'select', options: roles, required: true },
        { name: 'empleado_id', label: 'Empleado vinculado', type: 'select', optionsUrl: '/rrhh/empleados', optionLabel: (e) => e.nombre_completo },
        { name: 'activo', label: 'Activo', type: 'checkbox' },
      ]} />
  )
}
