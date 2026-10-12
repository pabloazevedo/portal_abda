import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, clearTokens, getAccessToken, getRefreshToken, setTokens } from '../api/client'

export type Permissions = {
  role: string
  is_admin: boolean
  can_manage_members: boolean
  can_manage_patrimonio: boolean
  can_manage_acervo: boolean
  is_system_user: boolean
}

export type AuthUser = {
  id: number
  username: string
  email: string
  role: string
  musician_id?: number | null
  permissions?: Permissions
}

type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshMe: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshMe = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null)
      return
    }
    const { data } = await api.get('/auth/me')
    setUser(data)
  }, [])

  useEffect(() => {
    ;(async () => {
      try {
        if (getAccessToken() || getRefreshToken()) {
          await refreshMe()
        }
      } catch {
        clearTokens()
        setUser(null)
      } finally {
        setLoading(false)
      }
    })()
  }, [refreshMe])

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await api.post('/auth/login', { username, password, client: 'spa' })
    setTokens(data.access_token, data.refresh_token)
    const me = await api.get('/auth/me')
    if (!me.data.permissions?.is_system_user) {
      clearTokens()
      setUser(null)
      throw new Error('Acesso ao portal restrito à equipe operacional. Use o app mobile (/m).')
    }
    setUser(me.data)
  }, [])

  const logout = useCallback(async () => {
    const rt = getRefreshToken()
    try {
      if (rt) await api.post('/auth/logout', { refresh_token: rt })
    } catch {
      /* ignore */
    }
    clearTokens()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshMe }),
    [user, loading, login, logout, refreshMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
