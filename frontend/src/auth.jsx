import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [sesion, setSesion] = useState(null)
  const [cargando, setCargando] = useState(!!localStorage.getItem('token'))

  useEffect(() => {
    if (!localStorage.getItem('token')) return
    api('/auth/me').then(setSesion).catch(() => localStorage.removeItem('token')).finally(() => setCargando(false))
  }, [])

  async function login(email, password) {
    const data = await api('/auth/login', { method: 'POST', body: { email, password } })
    localStorage.setItem('token', data.access_token)
    setSesion(data)
  }

  function logout() {
    localStorage.removeItem('token')
    setSesion(null)
  }

  // puede('inventario', 'crear')
  const puede = (modulo, accion = 'ver') => !!sesion?.permisos?.[modulo]?.[accion]

  return (
    <AuthContext.Provider value={{ usuario: sesion?.usuario, puede, login, logout, cargando }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
