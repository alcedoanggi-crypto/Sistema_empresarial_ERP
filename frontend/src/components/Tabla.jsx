/**
 * Tabla con búsqueda, filtros y paginación.
 *  listado:  resultado de useListado()
 *  columnas: [{ key, label, render?(fila) }]
 *  filtros:  [{ name, label, options: [{value,label}] }]
 *  acciones: (fila) => JSX
 */
export default function Tabla({ listado, columnas, filtros = [], acciones, busqueda = true }) {
  const { data, cargando, page, setPage, q, setQ } = listado

  return (
    <div className="card p-0">
      {(busqueda || filtros.length > 0) && (
        <div className="flex flex-wrap gap-2 border-b p-3">
          {busqueda && (
            <input className="input max-w-xs" placeholder="Buscar..." value={q} onChange={(e) => setQ(e.target.value)} />
          )}
          {filtros.map((f) => (
            <select key={f.name} className="input w-auto" value={listado.filtros[f.name] ?? ''}
                    onChange={(e) => listado.setFiltro(f.name, e.target.value)}>
              <option value="">{f.label}: todos</option>
              {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ))}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              {columnas.map((c) => <th key={c.key} className="whitespace-nowrap px-3 py-2 font-medium">{c.label}</th>)}
              {acciones && <th className="px-3 py-2" />}
            </tr>
          </thead>
          <tbody className={cargando ? 'opacity-50' : ''}>
            {data.items.map((fila, i) => (
              <tr key={fila.id ?? fila.producto_id ?? i} className="border-t hover:bg-slate-50">
                {columnas.map((c) => (
                  <td key={c.key} className="whitespace-nowrap px-3 py-2 text-slate-700">
                    {c.render ? c.render(fila) : fila[c.key] ?? '—'}
                  </td>
                ))}
                {acciones && <td className="whitespace-nowrap px-3 py-2 text-right">{acciones(fila)}</td>}
              </tr>
            ))}
            {!data.items.length && (
              <tr><td colSpan={columnas.length + 1} className="px-3 py-8 text-center text-slate-400">
                {cargando ? 'Cargando...' : 'Sin resultados'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t px-3 py-2 text-sm text-slate-500">
        <span>{data.total} registro(s)</span>
        <div className="flex items-center gap-2">
          <button className="btn-secundario px-2 py-1" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button>
          <span>Página {page} de {data.pages}</span>
          <button className="btn-secundario px-2 py-1" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>›</button>
        </div>
      </div>
    </div>
  )
}
