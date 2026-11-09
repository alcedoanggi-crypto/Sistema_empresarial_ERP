import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

const DEMO = [
  ['Administrador', 'admin@empresa.com', 'Admin123!'],
  ['Gerente', 'gerente@empresa.com', 'Gerente123!'],
  ['Empleado', 'empleado@empresa.com', 'Empleado123!'],
]

export default function Login() {
  const { usuario, login } = useAuth()
  const [email, setEmail] = useState('admin@empresa.com')
  const [password, setPassword] = useState('Admin123!')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to="/" replace />

  async function entrar(e) {
    e.preventDefault()
    setEnviando(true)
    setError('')
    try {
      await login(email, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 p-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
        <h1 className="text-2xl font-bold text-slate-800">ERP<span className="text-indigo-600">lite</span></h1>
        <p className="mb-5 text-sm text-slate-500">Sistema de Administración Empresarial</p>
        <form onSubmit={entrar} className="space-y-3">
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Correo" required />
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Contraseña" required />
          {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
          <button className="btn-primario w-full" disabled={enviando}>{enviando ? 'Ingresando...' : 'Ingresar'}</button>
        </form>
        <div className="mt-5 border-t pt-3 text-xs text-slate-500">
          <p className="mb-1 font-medium">Usuarios de demostración:</p>
          {DEMO.map(([rol, e, p]) => (
            <button key={e} className="block hover:text-indigo-600" onClick={() => { setEmail(e); setPassword(p) }}>
              {rol}: {e}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
