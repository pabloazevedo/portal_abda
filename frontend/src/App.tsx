import { ConfigProvider, App as AntApp, theme } from 'antd'
import ptBR from 'antd/locale/pt_BR'
import enUS from 'antd/locale/en_US'
import esES from 'antd/locale/es_ES'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AuthProvider, useAuth } from './auth/AuthContext'
import AppLayout from './layouts/AppLayout'
import LoginPage from './pages/LoginPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import HomePage from './pages/HomePage'
import MusiciansPage from './pages/MusiciansPage'
import MusicianDetailPage from './pages/MusicianDetailPage'
import OrganogramPage from './pages/OrganogramPage'
import UsersPage from './pages/UsersPage'
import PatrimonioPage from './pages/PatrimonioPage'
import PatrimonioDetailPage from './pages/PatrimonioDetailPage'
import AcervoPage from './pages/AcervoPage'
import ObraDetailPage from './pages/ObraDetailPage'
import ArranjoDetailPage from './pages/ArranjoDetailPage'
import ProgramacaoPage from './pages/ProgramacaoPage'
import SettingsPage from './pages/SettingsPage'
import SearchPage from './pages/SearchPage'
import ReleasesPage from './pages/ReleasesPage'
import './i18n'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  if (!user.permissions?.is_system_user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes({ dark, onToggleDark }: { dark: boolean; onToggleDark: () => void }) {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <AppLayout dark={dark} onToggleDark={onToggleDark} />
          </PrivateRoute>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="musicians" element={<MusiciansPage />} />
        <Route path="musicians/organogram" element={<OrganogramPage />} />
        <Route path="musicians/:id" element={<MusicianDetailPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="patrimonio" element={<PatrimonioPage />} />
        <Route path="patrimonio/:id" element={<PatrimonioDetailPage />} />
        <Route path="acervo" element={<Navigate to="/acervo/obras" replace />} />
        <Route path="acervo/programacao" element={<ProgramacaoPage />} />
        <Route path="acervo/obras/:id" element={<ObraDetailPage />} />
        <Route path="acervo/arranjos/:id" element={<ArranjoDetailPage />} />
        <Route path="acervo/:tab" element={<AcervoPage />} />
        <Route path="programacao" element={<ProgramacaoPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="releases" element={<ReleasesPage />} />
        <Route path="versoes" element={<ReleasesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  const { i18n } = useTranslation()
  const [dark, setDark] = useState(() => localStorage.getItem('portal-theme') === 'dark')

  useEffect(() => {
    localStorage.setItem('portal-theme', dark ? 'dark' : 'light')
  }, [dark])

  const locale = useMemo(() => {
    if (i18n.language === 'en') return enUS
    if (i18n.language === 'es') return esES
    return ptBR
  }, [i18n.language])

  return (
    <ConfigProvider
      locale={locale}
      theme={{
        algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1A365C',
          borderRadius: 8,
          fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
        },
      }}
    >
      <AntApp>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes dark={dark} onToggleDark={() => setDark((d) => !d)} />
          </BrowserRouter>
        </AuthProvider>
      </AntApp>
    </ConfigProvider>
  )
}
