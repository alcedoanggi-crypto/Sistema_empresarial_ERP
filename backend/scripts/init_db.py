"""Crea el esquema (sql/*.sql) y carga datos de demostración.

Uso (desde backend/, con el venv activo):
    python -m scripts.init_db            # carga esquema si falta + datos demo
    python -m scripts.init_db --reset    # BORRA todo y vuelve a empezar

Requiere que exista la BD y el rol (ver scripts/crear_bd.sql).
"""
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text

from app.core.seguridad import hash_password
from app.database import SessionLocal, engine
from app.models import (Almacen, Asistencia, Categoria, Cliente, Departamento, Empleado, Modulo, Movimiento,
                        OrdenCompra, OrdenCompraDetalle, OrdenVenta, OrdenVentaDetalle, Permiso, Producto,
                        Proveedor, Puesto, Rol, Solicitud, Usuario)
from app.services.compras import recibir_orden
from app.services.ventas import facturar

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
random.seed(42)

MODULOS = [("dashboard", "Dashboard"), ("usuarios", "Usuarios y roles"), ("rrhh", "Recursos Humanos"),
           ("autoservicio", "Mi espacio"), ("inventario", "Inventario"), ("compras", "Compras"),
           ("ventas", "Ventas"), ("reportes", "Reportes"), ("auditoria", "Auditoría")]

TODO = dict(puede_ver=True, puede_crear=True, puede_editar=True, puede_eliminar=True, puede_aprobar=True)
VER = dict(puede_ver=True)
PERMISOS = {
    "administrador": {m: TODO for m, _ in MODULOS},
    "gerente": {"dashboard": VER, "usuarios": VER, "rrhh": TODO, "autoservicio": TODO, "inventario": TODO,
                "compras": TODO, "ventas": TODO, "reportes": VER, "auditoria": VER},
    "empleado": {"dashboard": VER, "autoservicio": dict(puede_ver=True, puede_crear=True),
                 "inventario": VER, "ventas": dict(puede_ver=True, puede_crear=True)},
}


def cargar_esquema(reset: bool) -> None:
    with engine.begin() as con:
        existe = con.execute(text("SELECT to_regclass('public.roles')")).scalar()
        if existe and not reset:
            print("· Esquema ya existe")
            return
        if reset:
            con.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        cursor = con.connection.cursor()   # cursor crudo: sin parámetros, los '%' del SQL quedan intactos
        for archivo in sorted(SQL_DIR.glob("*.sql")):
            cursor.execute(archivo.read_text(encoding="utf-8"))
            print(f"· {archivo.name}")


def seed() -> None:
    db = SessionLocal()
    if db.scalar(text("SELECT count(*) FROM modulos")):
        print("· Ya hay datos; use --reset para recargar")
        return

    # --- Seguridad ---------------------------------------------------------
    modulos = {}
    for i, (clave, nombre) in enumerate(MODULOS):
        modulos[clave] = Modulo(clave=clave, nombre=nombre, orden=i)
        db.add(modulos[clave])
    roles = {}
    for nombre, matriz in PERMISOS.items():
        rol = Rol(nombre=nombre, descripcion=f"Rol {nombre}", es_sistema=True)
        rol.permisos = [Permiso(modulo=modulos[m], **p) for m, p in matriz.items()]
        roles[nombre] = rol
        db.add(rol)
    admin = Usuario(nombre="Administrador", email="admin@empresa.com",
                    password_hash=hash_password("Admin123!"), rol=roles["administrador"])
    db.add(admin)
    db.commit()
    db.close()

    # A partir de aquí la auditoría registra al administrador como autor
    db = SessionLocal()
    db.info["usuario_id"] = admin.id
    admin = db.get(Usuario, admin.id)

    # --- RRHH --------------------------------------------------------------
    deps = {c: Departamento(codigo=c, nombre=n) for c, n in
            [("GER", "Gerencia"), ("VEN", "Ventas"), ("BOD", "Bodega"), ("ADM", "Administración")]}
    db.add_all(deps.values())
    db.flush()
    puestos = {n: Puesto(departamento_id=deps[d].id, nombre=n, salario_min=Decimal(a), salario_max=Decimal(b))
               for n, d, a, b in [("Gerente General", "GER", 2500, 5000), ("Vendedor", "VEN", 470, 900),
                                  ("Jefe de Ventas", "VEN", 1000, 1800), ("Bodeguero", "BOD", 470, 800),
                                  ("Contador", "ADM", 900, 1500), ("Asistente Administrativo", "ADM", 470, 750)]}
    db.add_all(puestos.values())
    db.flush()
    personas = [("María", "Torres", "Gerente General", 3200), ("Carlos", "Mendoza", "Jefe de Ventas", 1400),
                ("Ana", "Vélez", "Vendedor", 650), ("Luis", "Paredes", "Vendedor", 600),
                ("Sofía", "Andrade", "Contador", 1100), ("Jorge", "Castro", "Bodeguero", 520),
                ("Daniela", "Ruiz", "Asistente Administrativo", 550), ("Pedro", "Salazar", "Bodeguero", 500)]
    empleados = []
    for i, (n, a, p, s) in enumerate(personas, 1):
        e = Empleado(codigo=f"EMP-{i:03d}", cedula=f"17{i:08d}", nombres=n, apellidos=a,
                     email=f"{n.lower().replace('í', 'i')}.{a.lower().replace('é', 'e')}@empresa.com",
                     telefono=f"09{random.randint(10000000, 99999999)}", fecha_nacimiento=date(1985 + i, i, 10),
                     fecha_ingreso=date(2019 + i % 5, i, 1), puesto_id=puestos[p].id, salario=Decimal(s),
                     estado="licencia" if i == 8 else "activo")
        db.add(e)
        empleados.append(e)
    db.flush()
    for e in empleados[1:]:
        e.jefe_id = empleados[0].id

    db.add_all([
        Usuario(nombre="María Torres", email="gerente@empresa.com", password_hash=hash_password("Gerente123!"),
                rol_id=roles["gerente"].id, empleado_id=empleados[0].id),
        Usuario(nombre="Ana Vélez", email="empleado@empresa.com", password_hash=hash_password("Empleado123!"),
                rol_id=roles["empleado"].id, empleado_id=empleados[2].id),
    ])

    hoy = date.today()
    for e in empleados[:7]:
        for d in range(1, hoy.day):
            dia = hoy.replace(day=d)
            if dia.weekday() < 5:
                entrada = time(8, random.choice([0, 5, 10, 20, 30]))
                db.add(Asistencia(empleado_id=e.id, fecha=dia, hora_entrada=entrada, hora_salida=time(17, 0)))
    db.add_all([
        Solicitud(empleado_id=empleados[2].id, tipo="vacaciones", fecha_inicio=hoy + timedelta(days=20),
                  fecha_fin=hoy + timedelta(days=24), dias=5, motivo="Viaje familiar"),
        Solicitud(empleado_id=empleados[5].id, tipo="permiso", fecha_inicio=hoy + timedelta(days=3),
                  fecha_fin=hoy + timedelta(days=3), dias=1, motivo="Cita médica"),
    ])

    # --- Inventario --------------------------------------------------------
    cats = {n: Categoria(nombre=n) for n in ["Computación", "Accesorios", "Oficina", "Redes"]}
    db.add_all(cats.values())
    almacenes = [Almacen(codigo="MATRIZ", nombre="Bodega Matriz", direccion="Av. Principal 123"),
                 Almacen(codigo="SUC-N", nombre="Sucursal Norte", direccion="Calle Norte 45")]
    db.add_all(almacenes)
    db.flush()
    catalogo = [("LAP-001", "Laptop 14\" Core i5", "Computación", 520, 749, 5, 25),
                ("LAP-002", "Laptop 15\" Ryzen 7", "Computación", 680, 949, 3, 12),
                ("MON-024", "Monitor 24\" Full HD", "Computación", 110, 169, 5, 30),
                ("TEC-USB", "Teclado USB", "Accesorios", 6, 14, 20, 120),
                ("MOU-INA", "Mouse inalámbrico", "Accesorios", 5, 12, 20, 15),
                ("AUD-BT", "Audífonos Bluetooth", "Accesorios", 18, 39, 10, 40),
                ("PAP-A4", "Resma papel A4", "Oficina", 3.2, 5.5, 50, 300),
                ("TIN-NEG", "Tóner negro", "Oficina", 25, 48, 10, 8),
                ("SIL-ERG", "Silla ergonómica", "Oficina", 85, 159, 3, 10),
                ("ROU-AC", "Router WiFi AC1200", "Redes", 32, 59, 5, 18),
                ("SWI-08", "Switch 8 puertos", "Redes", 19, 35, 5, 4),
                ("CAB-UTP", "Cable UTP Cat6 (caja)", "Redes", 70, 115, 2, 0)]
    productos = []
    for sku, nombre, cat, costo, venta, minimo, inicial in catalogo:
        p = Producto(sku=sku, nombre=nombre, categoria_id=cats[cat].id, precio_costo=Decimal(str(costo)),
                     precio_venta=Decimal(str(venta)), stock_minimo=minimo)
        db.add(p)
        db.flush()
        productos.append(p)
        if inicial:
            db.add(Movimiento(producto_id=p.id, almacen_id=almacenes[0].id, tipo="entrada", origen="inicial",
                              cantidad=inicial * 3, costo_unitario=p.precio_costo, documento="SALDO-INICIAL",
                              usuario_id=admin.id))
            db.add(Movimiento(producto_id=p.id, almacen_id=almacenes[1].id, tipo="entrada", origen="inicial",
                              cantidad=max(1, inicial // 3), costo_unitario=p.precio_costo,
                              documento="SALDO-INICIAL", usuario_id=admin.id))
    db.commit()

    # --- Compras -----------------------------------------------------------
    provs = [Proveedor(ruc=r, razon_social=n, nombre_contacto=c, email=m, dias_credito=d) for r, n, c, m, d in [
        ("1790012345001", "TecnoMayorista S.A.", "Raúl Pinto", "ventas@tecnomayorista.com", 30),
        ("0991234567001", "Distribuidora Andina Cía. Ltda.", "Lucía Mora", "pedidos@andina.com", 15),
        ("1791122334001", "Papelería Total", "Andrés León", "info@papeleriatotal.com", 0)]]
    db.add_all(provs)
    db.flush()
    for i, estado in enumerate(["recibida", "aprobada", "borrador"]):
        oc = OrdenCompra(proveedor_id=provs[i].id, almacen_id=almacenes[0].id, creado_por=admin.id,
                         fecha_entrega_esperada=hoy + timedelta(days=7))
        oc.detalles = [OrdenCompraDetalle(producto_id=p.id, cantidad=10 * (j + 1), costo_unitario=p.precio_costo)
                       for j, p in enumerate(productos[i * 4:i * 4 + 3])]
        db.add(oc)
        db.flush()
        if estado != "borrador":
            oc.estado, oc.aprobado_por, oc.fecha_aprobacion = "aprobada", admin.id, datetime.now(timezone.utc)
        db.commit()
        if estado == "recibida":
            recibir_orden(db, oc.id, admin)

    # --- Ventas: ~6 meses de facturación (pasa por la transacción real) ----
    clientes = [Cliente(tipo_identificacion=t, identificacion=i, nombre=n, email=m) for t, i, n, m in [
        ("ruc", "1790098765001", "Constructora Horizonte S.A.", "compras@horizonte.com"),
        ("ruc", "0990011223001", "Colegio San Andrés", "admin@sanandres.edu.ec"),
        ("cedula", "1712345678", "Roberto Jaramillo", "rjaramillo@gmail.com"),
        ("cedula", "0912345678", "Paola Benítez", "pbenitez@hotmail.com"),
        ("ruc", "1792233445001", "Clínica Santa Fe", "logistica@clinicasantafe.com")]]
    db.add_all(clientes)
    db.commit()
    vendibles = [p for p in productos if p.sku not in ("CAB-UTP",)]
    for k in range(28):
        dias_atras = int(175 * (1 - k / 27)) + random.randint(0, 3)
        ov = OrdenVenta(cliente_id=random.choice(clientes).id, almacen_id=almacenes[0].id, creado_por=admin.id)
        ov.detalles = [OrdenVentaDetalle(producto_id=p.id, cantidad=random.randint(1, 4), precio_unitario=p.precio_venta,
                                         descuento_pct=Decimal(random.choice([0, 0, 5])))
                       for p in random.sample(vendibles, random.randint(1, 3))]
        db.add(ov)
        db.commit()
        try:
            factura = facturar(db, ov.id, admin)
        except HTTPException:            # sin stock: la transacción se revirtió completa
            ov.estado = "cancelada"
            db.commit()
            continue
        momento = datetime.now(timezone.utc) - timedelta(days=dias_atras)
        db.execute(text("UPDATE facturas SET fecha_emision = :f WHERE id = :id"), {"f": momento, "id": factura.id})
        db.execute(text("UPDATE ordenes_venta SET fecha = :f WHERE id = :id"), {"f": momento.date(), "id": ov.id})
        db.commit()
    # Una orden pendiente para probar la facturación desde la interfaz
    ov = OrdenVenta(cliente_id=clientes[0].id, almacen_id=almacenes[0].id, creado_por=admin.id)
    ov.detalles = [OrdenVentaDetalle(producto_id=productos[0].id, cantidad=2, precio_unitario=productos[0].precio_venta)]
    db.add(ov)
    db.commit()
    db.close()
    print("· Datos demo cargados")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cargar_esquema(reset="--reset" in sys.argv)
    seed()
    print("\nListo. Usuarios: admin@empresa.com / Admin123!  ·  gerente@empresa.com / Gerente123!"
          "  ·  empleado@empresa.com / Empleado123!")
