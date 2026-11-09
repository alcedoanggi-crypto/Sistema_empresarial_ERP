"""Reportes exportables. Cada reporte se define UNA vez (columnas + filas) y se
renderiza a PDF (ReportLab) o Excel (openpyxl) con el mismo contenido."""
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

COLOR_PRIMARIO = "1E3A8A"
COLOR_ZEBRA = "F1F5F9"


@dataclass
class Columna:
    titulo: str
    clave: str
    tipo: str = "texto"     # texto | entero | dinero | fecha | fechahora
    ancho: float = 1.0      # peso relativo


@dataclass
class Reporte:
    titulo: str
    columnas: list[Columna]
    filas: list[dict]
    subtitulo: str = ""
    totales: dict = field(default_factory=dict)


def _periodo(desde: date | None, hasta: date | None) -> str:
    if desde and hasta:
        return f"Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
    if desde:
        return f"Desde {desde:%d/%m/%Y}"
    if hasta:
        return f"Hasta {hasta:%d/%m/%Y}"
    return "Todo el período"


def _filas(db: Session, sql: str, **params) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), params).mappings()]


def _sumar(filas: list[dict], *claves: str) -> dict:
    return {c: sum((f[c] or 0 for f in filas), Decimal("0")) for c in claves}


# --------------------------------------------------------------------------
# Definición de reportes
# --------------------------------------------------------------------------
def rep_inventario(db: Session, desde=None, hasta=None) -> Reporte:
    filas = _filas(db, "SELECT * FROM v_stock_productos ORDER BY categoria, nombre")
    return Reporte(
        "Inventario valorizado",
        [Columna("SKU", "sku"), Columna("Producto", "nombre", ancho=2.5), Columna("Categoría", "categoria", ancho=1.4),
         Columna("Unidad", "unidad_medida", ancho=0.6), Columna("Stock", "stock_total", "entero", 0.7),
         Columna("Mínimo", "stock_minimo", "entero", 0.7), Columna("Costo", "precio_costo", "dinero"),
         Columna("Valor", "valor_inventario", "dinero"), Columna("Estado", "estado_stock", ancho=0.8)],
        filas, f"Corte al {date.today():%d/%m/%Y}", _sumar(filas, "valor_inventario"),
    )


def rep_stock_critico(db: Session, desde=None, hasta=None) -> Reporte:
    filas = _filas(db, "SELECT *, stock_minimo - stock_total AS faltante FROM v_stock_critico ORDER BY estado_stock, nombre")
    return Reporte(
        "Alertas de stock mínimo",
        [Columna("SKU", "sku"), Columna("Producto", "nombre", ancho=2.5), Columna("Categoría", "categoria", ancho=1.4),
         Columna("Stock", "stock_total", "entero", 0.7), Columna("Mínimo", "stock_minimo", "entero", 0.7),
         Columna("Faltante", "faltante", "entero", 0.7), Columna("Estado", "estado_stock", ancho=0.8)],
        filas, f"Corte al {date.today():%d/%m/%Y}",
    )


def rep_movimientos(db: Session, desde=None, hasta=None) -> Reporte:
    filas = _filas(db, """
        SELECT m.created_at, p.sku, p.nombre AS producto, a.nombre AS almacen, m.tipo, m.origen,
               m.cantidad, m.documento, u.nombre AS usuario
          FROM movimientos_inventario m
          JOIN productos p ON p.id = m.producto_id
          JOIN almacenes a ON a.id = m.almacen_id
          LEFT JOIN usuarios u ON u.id = m.usuario_id
         WHERE (CAST(:desde AS date) IS NULL OR m.created_at >= :desde)
           AND (CAST(:hasta AS date) IS NULL OR m.created_at < CAST(:hasta AS date) + 1)
         ORDER BY m.created_at DESC""", desde=desde, hasta=hasta)
    return Reporte(
        "Historial de movimientos de inventario",
        [Columna("Fecha", "created_at", "fechahora", 1.2), Columna("SKU", "sku"), Columna("Producto", "producto", ancho=2.2),
         Columna("Almacén", "almacen", ancho=1.2), Columna("Tipo", "tipo", ancho=0.7), Columna("Origen", "origen", ancho=0.8),
         Columna("Cantidad", "cantidad", "entero", 0.7), Columna("Documento", "documento", ancho=1.3),
         Columna("Usuario", "usuario", ancho=1.2)],
        filas, _periodo(desde, hasta),
    )


def rep_ventas(db: Session, desde=None, hasta=None) -> Reporte:
    filas = _filas(db, """
        SELECT f.numero, f.fecha_emision, c.identificacion, c.nombre AS cliente, ov.numero AS orden,
               f.subtotal - f.descuento AS neto, f.iva, f.total, f.estado
          FROM facturas f
          JOIN ordenes_venta ov ON ov.id = f.orden_venta_id
          JOIN clientes c ON c.id = ov.cliente_id
         WHERE (CAST(:desde AS date) IS NULL OR f.fecha_emision >= :desde)
           AND (CAST(:hasta AS date) IS NULL OR f.fecha_emision < CAST(:hasta AS date) + 1)
         ORDER BY f.fecha_emision DESC""", desde=desde, hasta=hasta)
    emitidas = [f for f in filas if f["estado"] == "emitida"]
    return Reporte(
        "Reporte de ventas (facturación)",
        [Columna("Factura", "numero", ancho=1.5), Columna("Fecha", "fecha_emision", "fechahora", 1.2),
         Columna("Identificación", "identificacion", ancho=1.1), Columna("Cliente", "cliente", ancho=2.2),
         Columna("Orden", "orden"), Columna("Neto", "neto", "dinero"), Columna("IVA", "iva", "dinero", 0.8),
         Columna("Total", "total", "dinero"), Columna("Estado", "estado", ancho=0.8)],
        filas, _periodo(desde, hasta) + " · los totales excluyen facturas anuladas",
        _sumar(emitidas, "neto", "iva", "total"),
    )


def rep_compras(db: Session, desde=None, hasta=None) -> Reporte:
    filas = _filas(db, """
        SELECT numero, fecha_emision, proveedor, almacen, num_lineas, total, estado
          FROM v_ordenes_compra_resumen
         WHERE (CAST(:desde AS date) IS NULL OR fecha_emision >= :desde)
           AND (CAST(:hasta AS date) IS NULL OR fecha_emision <= :hasta)
         ORDER BY fecha_emision DESC, numero DESC""", desde=desde, hasta=hasta)
    vigentes = [f for f in filas if f["estado"] != "cancelada"]
    return Reporte(
        "Reporte de órdenes de compra",
        [Columna("Número", "numero"), Columna("Fecha", "fecha_emision", "fecha"), Columna("Proveedor", "proveedor", ancho=2.5),
         Columna("Almacén", "almacen", ancho=1.3), Columna("Líneas", "num_lineas", "entero", 0.6),
         Columna("Total", "total", "dinero"), Columna("Estado", "estado", ancho=0.9)],
        filas, _periodo(desde, hasta) + " · el total excluye órdenes canceladas", _sumar(vigentes, "total"),
    )


def rep_empleados(db: Session, desde=None, hasta=None) -> Reporte:
    filas = _filas(db, """
        SELECT e.codigo, e.cedula, e.apellidos || ' ' || e.nombres AS empleado, d.nombre AS departamento,
               p.nombre AS puesto, e.fecha_ingreso, e.salario, e.estado
          FROM empleados e
          JOIN puestos p ON p.id = e.puesto_id
          JOIN departamentos d ON d.id = p.departamento_id
         WHERE e.deleted_at IS NULL
         ORDER BY d.nombre, e.apellidos""")
    activos = [f for f in filas if f["estado"] == "activo"]
    return Reporte(
        "Nómina de empleados",
        [Columna("Código", "codigo", ancho=0.8), Columna("Cédula", "cedula"), Columna("Empleado", "empleado", ancho=2.2),
         Columna("Departamento", "departamento", ancho=1.4), Columna("Puesto", "puesto", ancho=1.6),
         Columna("Ingreso", "fecha_ingreso", "fecha"), Columna("Salario", "salario", "dinero"),
         Columna("Estado", "estado", ancho=0.8)],
        filas, f"{len(activos)} empleados activos · masa salarial de activos", _sumar(activos, "salario"),
    )


def rep_auditoria(db: Session, desde=None, hasta=None) -> Reporte:
    filas = _filas(db, """
        SELECT a.fecha, COALESCE(u.nombre, '(sistema)') AS usuario, a.accion, a.tabla, a.registro_id,
               array_to_string(a.campos_modificados, ', ') AS campos, host(a.ip) AS ip
          FROM auditoria a LEFT JOIN usuarios u ON u.id = a.usuario_id
         WHERE (CAST(:desde AS date) IS NULL OR a.fecha >= :desde)
           AND (CAST(:hasta AS date) IS NULL OR a.fecha < CAST(:hasta AS date) + 1)
         ORDER BY a.fecha DESC LIMIT 5000""", desde=desde, hasta=hasta)
    return Reporte(
        "Bitácora de auditoría",
        [Columna("Fecha", "fecha", "fechahora", 1.2), Columna("Usuario", "usuario", ancho=1.4),
         Columna("Acción", "accion", ancho=0.9), Columna("Tabla", "tabla", ancho=1.4),
         Columna("Registro", "registro_id", "entero", 0.7), Columna("Campos modificados", "campos", ancho=2.8),
         Columna("IP", "ip", ancho=0.9)],
        filas, _periodo(desde, hasta) + " · máximo 5.000 registros",
    )


REPORTES: dict[str, tuple[str, str, Callable[..., Reporte]]] = {
    # clave: (módulo requerido, descripción, generador)
    "inventario": ("inventario", "Inventario valorizado", rep_inventario),
    "stock-critico": ("inventario", "Alertas de stock mínimo", rep_stock_critico),
    "movimientos": ("inventario", "Historial de movimientos", rep_movimientos),
    "ventas": ("ventas", "Ventas facturadas", rep_ventas),
    "compras": ("compras", "Órdenes de compra", rep_compras),
    "empleados": ("rrhh", "Nómina de empleados", rep_empleados),
    "auditoria": ("auditoria", "Bitácora de auditoría", rep_auditoria),
}


# --------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------
def _texto(valor, tipo: str) -> str:
    if valor is None:
        return ""
    if tipo == "dinero":
        return f"$ {valor:,.2f}"
    if tipo == "entero":
        return f"{valor:,}"
    if tipo == "fecha" and isinstance(valor, date):
        return f"{valor:%d/%m/%Y}"
    if tipo == "fechahora" and isinstance(valor, datetime):
        return f"{valor.astimezone():%d/%m/%Y %H:%M}"
    return str(valor)


def a_pdf(rep: Reporte) -> bytes:
    buffer = io.BytesIO()
    pagina = landscape(A4)
    doc = SimpleDocTemplate(buffer, pagesize=pagina, leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.4 * cm, title=rep.titulo)
    estilos = getSampleStyleSheet()
    celda = ParagraphStyle("celda", parent=estilos["BodyText"], fontSize=7.5, leading=9)
    cabecera = ParagraphStyle("cab", parent=celda, textColor=colors.white, fontName="Helvetica-Bold")

    elementos = [
        Paragraph(settings.nombre_empresa, ParagraphStyle("emp", parent=estilos["Normal"], textColor=colors.grey)),
        Paragraph(rep.titulo, estilos["Title"]),
        Paragraph(f"{rep.subtitulo} · Generado {datetime.now():%d/%m/%Y %H:%M} · {len(rep.filas)} registros",
                  estilos["Normal"]),
        Spacer(1, 0.4 * cm),
    ]

    ancho_util = pagina[0] - doc.leftMargin - doc.rightMargin
    peso_total = sum(c.ancho for c in rep.columnas)
    anchos = [ancho_util * c.ancho / peso_total for c in rep.columnas]
    celda_num = ParagraphStyle("num", parent=celda, alignment=2)
    estilo_col = [celda_num if c.tipo in ("dinero", "entero") else celda for c in rep.columnas]

    datos = [[Paragraph(c.titulo, cabecera) for c in rep.columnas]]
    datos += [[Paragraph(_texto(f.get(c.clave), c.tipo), estilo_col[j]) for j, c in enumerate(rep.columnas)]
              for f in rep.filas]
    if rep.totales:
        datos.append([Paragraph(f"<b>{_texto(rep.totales[c.clave], c.tipo)}</b>", estilo_col[j])
                      if c.clave in rep.totales else Paragraph("<b>TOTAL</b>" if j == 0 else "", celda)
                      for j, c in enumerate(rep.columnas)])

    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_PRIMARIO}")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(f"#{COLOR_ZEBRA}")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if rep.totales:
        estilo.append(("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor(f"#{COLOR_PRIMARIO}")))
    tabla.setStyle(TableStyle(estilo))
    elementos.append(tabla)

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(pagina[0] - doc.rightMargin, 0.8 * cm, f"Página {doc_.page}")
        canvas.drawString(doc.leftMargin, 0.8 * cm, rep.titulo)
        canvas.restoreState()

    doc.build(elementos, onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()


def a_excel(rep: Reporte) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = rep.titulo[:31]
    n = len(rep.columnas)

    ws["A1"] = rep.titulo
    ws["A1"].font = Font(size=14, bold=True, color=COLOR_PRIMARIO)
    ws["A2"] = f"{settings.nombre_empresa} · {rep.subtitulo} · Generado {datetime.now():%d/%m/%Y %H:%M}"
    ws["A2"].font = Font(size=9, italic=True, color="64748B")

    fila_cab = 4
    borde = Border(bottom=Side(style="thin", color="CBD5E1"))
    for j, c in enumerate(rep.columnas, start=1):
        celda = ws.cell(row=fila_cab, column=j, value=c.titulo)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor=COLOR_PRIMARIO)
        celda.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = max(10, int(14 * c.ancho))

    formatos = {"dinero": '"$" #,##0.00', "entero": "#,##0", "fecha": "DD/MM/YYYY", "fechahora": "DD/MM/YYYY HH:MM"}
    for i, f in enumerate(rep.filas, start=fila_cab + 1):
        for j, c in enumerate(rep.columnas, start=1):
            valor = f.get(c.clave)
            if isinstance(valor, Decimal):
                valor = float(valor)
            elif isinstance(valor, datetime):
                valor = valor.astimezone().replace(tzinfo=None)   # Excel no admite zona horaria
            celda = ws.cell(row=i, column=j, value=valor)
            celda.border = borde
            if c.tipo in formatos:
                celda.number_format = formatos[c.tipo]
            if (i - fila_cab) % 2 == 0:
                celda.fill = PatternFill("solid", fgColor=COLOR_ZEBRA)

    ultima = fila_cab + len(rep.filas)
    if rep.totales:
        fila_tot = ultima + 1
        ws.cell(row=fila_tot, column=1, value="TOTAL").font = Font(bold=True)
        for j, c in enumerate(rep.columnas, start=1):
            if c.clave in rep.totales:
                celda = ws.cell(row=fila_tot, column=j, value=float(rep.totales[c.clave]))
                celda.font = Font(bold=True)
                celda.number_format = formatos.get(c.tipo, "General")
                celda.border = Border(top=Side(style="medium", color=COLOR_PRIMARIO))

    ws.auto_filter.ref = f"A{fila_cab}:{get_column_letter(n)}{max(ultima, fila_cab)}"
    ws.freeze_panes = ws.cell(row=fila_cab + 1, column=1)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Factura individual
# --------------------------------------------------------------------------
def factura_pdf(factura) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=f"Factura {factura.numero}")
    est = getSampleStyleSheet()
    orden = factura.orden_venta
    cliente = orden.cliente
    primario = colors.HexColor(f"#{COLOR_PRIMARIO}")

    encabezado = Table([[
        Paragraph(f"<font size=16><b>{settings.nombre_empresa}</b></font><br/>RUC 1790000000001<br/>"
                  "Av. Principal 123, Quito", est["Normal"]),
        Paragraph(f"<font size=14 color='#{COLOR_PRIMARIO}'><b>FACTURA</b></font><br/>N.º {factura.numero}<br/>"
                  f"Fecha: {factura.fecha_emision.astimezone():%d/%m/%Y %H:%M}<br/>Orden: {orden.numero}",
                  ParagraphStyle("d", parent=est["Normal"], alignment=2)),
    ]], colWidths=[9.5 * cm, 8 * cm])

    datos_cliente = Paragraph(
        f"<b>Cliente:</b> {cliente.nombre}<br/><b>{cliente.tipo_identificacion.upper()}:</b> {cliente.identificacion}"
        f"<br/><b>Dirección:</b> {cliente.direccion or '-'} &nbsp; <b>Teléfono:</b> {cliente.telefono or '-'}",
        est["Normal"])

    filas = [["SKU", "Descripción", "Cant.", "P. unitario", "Desc. %", "Subtotal"]]
    for d in orden.detalles:
        filas.append([d.producto.sku, Paragraph(d.producto.nombre + ("" if d.producto.aplica_iva else " (0% IVA)"),
                                                est["BodyText"]),
                      d.cantidad, f"{d.precio_unitario:,.2f}", f"{d.descuento_pct:.0f}", f"{d.subtotal:,.2f}"])
    detalle = Table(filas, colWidths=[2.6 * cm, 7 * cm, 1.4 * cm, 2.4 * cm, 1.6 * cm, 2.5 * cm], repeatRows=1)
    detalle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primario), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
    ]))

    totales = Table([
        ["Subtotal", f"$ {factura.subtotal:,.2f}"],
        ["Descuento", f"- $ {factura.descuento:,.2f}"],
        [f"IVA {factura.tasa_iva:.0f}%", f"$ {factura.iva:,.2f}"],
        ["TOTAL", f"$ {factura.total:,.2f}"],
    ], colWidths=[3.5 * cm, 3.5 * cm], hAlign="RIGHT")
    totales.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, primario), ("FONTSIZE", (0, -1), (-1, -1), 11),
    ]))

    elementos = [encabezado, Spacer(1, 0.5 * cm), datos_cliente, Spacer(1, 0.5 * cm), detalle,
                 Spacer(1, 0.4 * cm), totales]
    if factura.estado == "anulada":
        elementos += [Spacer(1, 0.6 * cm), Paragraph(
            f"<font color='red' size=14><b>FACTURA ANULADA</b></font><br/>Motivo: {factura.motivo_anulacion}",
            est["Normal"])]
    doc.build(elementos)
    return buffer.getvalue()
