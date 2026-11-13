# ERPlite · Sistema de Administración Empresarial

ERP ligero para una pyme: **RRHH, inventario, compras, ventas con facturación, dashboard, reportes PDF/Excel y auditoría**, con permisos configurables por rol.

| Capa | Tecnología |
|---|---|
| Base de datos | PostgreSQL 15+ (3FN, vistas, triggers, CHECK, EXCLUDE, índices parciales y trigram) |
| Backend | Python 3.12+ · FastAPI · SQLAlchemy 2 · Pydantic v2 · JWT · ReportLab · openpyxl |
| Frontend | React 18 · Vite · TailwindCSS · Recharts |

## Capturas

![Dashboard](docs/capturas/02-dashboard.png)

| | |
|---|---|
| ![Login](docs/capturas/01-login.png) **Login** con usuarios demo | ![Empleados](docs/capturas/03-empleados.png) **Empleados** con búsqueda, filtros y paginación |
| ![Formulario](docs/capturas/04-formulario-empleado.png) **Formulario** generado por configuración | ![Stock](docs/capturas/05-stock.png) **Stock** con semáforo y reporte PDF |
| ![Compras](docs/capturas/06-ordenes-compra.png) **Órdenes de compra** con flujo de estados | ![Venta](docs/capturas/07-orden-venta-detalle.png) **Orden de venta** lista para facturar |
| ![Facturas](docs/capturas/08-facturas.png) **Facturas** con PDF y anulación | ![Solicitudes](docs/capturas/09-solicitudes.png) **Solicitudes** con aprobación |
| ![Permisos](docs/capturas/10-roles-permisos.png) **Permisos** configurables por rol | ![Auditoría](docs/capturas/11-auditoria.png) **Auditoría** con el antes y el después |
| ![Reportes](docs/capturas/12-reportes.png) **Reportes** PDF y Excel | ![Mi espacio](docs/capturas/13-mi-espacio-empleado.png) **Autoservicio** del empleado |

<p align="center">
  <img src="docs/capturas/14-movil-dashboard.png" width="260" alt="Dashboard en móvil">
  &nbsp;&nbsp;
  <img src="docs/capturas/15-movil-menu.png" width="260" alt="Menú en móvil">
</p>

## Funcionalidades

- **Usuarios y roles**: administrador, gerente, empleado. Matriz de permisos *rol × módulo × acción* (ver, crear, editar, eliminar, aprobar) editable desde la interfaz.
- **RRHH**: empleados, departamentos, puestos (con banda salarial), asistencia (el empleado marca entrada y salida), vacaciones y permisos con **flujo de aprobación**.
- **Inventario**: productos, categorías, almacenes, stock por almacén, kardex inmutable, ajustes manuales y alertas de stock mínimo.
- **Compras**: proveedores y órdenes de compra `borrador → aprobada → recibida | cancelada`. Al recibir la orden se registra la entrada al inventario.
- **Ventas**: clientes, cotizaciones (que se convierten en orden), órdenes de venta y **facturación que descuenta inventario en una sola transacción**. Al anular una factura, el stock vuelve al almacén.
- **Dashboard**: ventas del mes con variación respecto al anterior, productos más vendidos, stock crítico y empleados activos.
- **Reportes** en PDF y Excel: inventario, stock crítico, movimientos, ventas, compras, nómina y auditoría.
- **Auditoría**: quién creó, modificó o eliminó cada registro, cuándo y desde qué IP, con el antes y el después en JSON.
- Todas las tablas tienen **paginación, búsqueda y filtros del lado del servidor**, **borrado lógico** y un diseño **responsive**.

