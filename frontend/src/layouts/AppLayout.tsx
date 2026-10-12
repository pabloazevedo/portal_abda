import { Layout, Menu, theme, Button, Space, Typography, Dropdown, Input, AutoComplete } from 'antd'
import {
  HomeOutlined,
  TeamOutlined,
  UserOutlined,
  InboxOutlined,
  CustomerServiceOutlined,
  SettingOutlined,
  LogoutOutlined,
  SearchOutlined,
  MoonOutlined,
  SunOutlined,
  ReadOutlined,
  CalendarOutlined,
  ApartmentOutlined,
} from '@ant-design/icons'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { useMemo, useState } from 'react'
import { api } from '../api/client'

const { Header, Sider, Content, Footer } = Layout

type AppLayoutProps = {
  dark: boolean
  onToggleDark: () => void
}

export default function AppLayout({ dark, onToggleDark }: AppLayoutProps) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const loc = useLocation()
  const nav = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [options, setOptions] = useState<{ value: string; label: string }[]>([])
  const { token } = theme.useToken()
  const perms = user?.permissions

  const items = useMemo(() => {
    const list = [
      { key: '/', icon: <HomeOutlined />, label: <Link to="/">{t('nav_home')}</Link> },
      { key: '/musicians', icon: <TeamOutlined />, label: <Link to="/musicians">{t('nav_musicians')}</Link> },
      {
        key: '/musicians/organogram',
        icon: <ApartmentOutlined />,
        label: <Link to="/musicians/organogram">{t('nav_organogram', 'Organograma')}</Link>,
      },
      { key: '/patrimonio', icon: <InboxOutlined />, label: <Link to="/patrimonio">{t('nav_patrimonio', 'Patrimônio')}</Link> },
      {
        key: '/acervo',
        icon: <CustomerServiceOutlined />,
        label: <Link to="/acervo/obras">{t('nav_acervo', 'Acervo')}</Link>,
      },
      {
        key: '/acervo/programacao',
        icon: <CalendarOutlined />,
        label: <Link to="/acervo/programacao">{t('nav_programacao', 'Programação')}</Link>,
      },
    ]
    if (perms?.is_admin) {
      list.push({ key: '/users', icon: <UserOutlined />, label: <Link to="/users">{t('nav_users')}</Link> })
      list.push({ key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">{t('nav_settings')}</Link> })
    }
    list.push({
      key: '/releases',
      icon: <ReadOutlined />,
      label: <Link to="/releases">{t('nav_releases', 'Versões')}</Link>,
    })
    return list
  }, [t, perms])

  const selected = useMemo(() => {
    if (loc.pathname.startsWith('/musicians/organogram')) return ['/musicians/organogram']
    if (loc.pathname.startsWith('/musicians')) return ['/musicians']
    if (loc.pathname.startsWith('/patrimonio')) return ['/patrimonio']
    if (loc.pathname.startsWith('/acervo/programacao')) return ['/acervo/programacao']
    if (loc.pathname.startsWith('/acervo')) return ['/acervo']
    if (loc.pathname.startsWith('/users')) return ['/users']
    if (loc.pathname.startsWith('/settings')) return ['/settings']
    if (loc.pathname.startsWith('/releases') || loc.pathname.startsWith('/versoes')) return ['/releases']
    return ['/']
  }, [loc.pathname])

  const onSearchType = async (q: string) => {
    if (q.trim().length < 2) {
      setOptions([])
      return
    }
    try {
      const { data } = await api.get('/search', { params: { q } })
      const opts = [
        ...(data.musicians || []).map((m: { name: string; url: string }) => ({
          value: m.url,
          label: `Membro: ${m.name}`,
        })),
        ...(data.patrimonio || []).map((p: { identificador: string; url: string }) => ({
          value: p.url,
          label: `Patrimônio: ${p.identificador}`,
        })),
        ...(data.obras || []).map((o: { titulo: string; url: string }) => ({
          value: o.url,
          label: `Obra: ${o.titulo}`,
        })),
      ]
      setOptions(opts)
    } catch {
      setOptions([])
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme={dark ? 'dark' : 'light'}>
        <div style={{ padding: 16, color: dark ? '#fff' : token.colorPrimary, fontWeight: 700 }}>
          {collapsed ? 'OP' : t('app_title')}
        </div>
        <Menu mode="inline" selectedKeys={selected} items={items} theme={dark ? 'dark' : 'light'} />
      </Sider>
      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingInline: 20,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <AutoComplete
            options={options}
            style={{ maxWidth: 420, width: '100%' }}
            onSearch={onSearchType}
            onSelect={(url) => nav(String(url))}
          >
            <Input
              prefix={<SearchOutlined />}
              placeholder={t('search_placeholder', 'Buscar membros, patrimônio, obras...')}
              allowClear
              onPressEnter={(e) => {
                const q = (e.target as HTMLInputElement).value.trim()
                if (q.length >= 2) nav(`/search?q=${encodeURIComponent(q)}`)
              }}
            />
          </AutoComplete>
          <Space>
            <Button type="text" icon={dark ? <SunOutlined /> : <MoonOutlined />} onClick={onToggleDark} />
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'logout',
                    icon: <LogoutOutlined />,
                    label: t('btn_logout', 'Sair'),
                    onClick: async () => {
                      await logout()
                      nav('/login')
                    },
                  },
                ],
              }}
            >
              <Button type="text" icon={<UserOutlined />}>
                {user?.username}
              </Button>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: 24 }}>
          <div
            style={{
              background: token.colorBgContainer,
              padding: 24,
              borderRadius: token.borderRadiusLG,
              minHeight: 360,
            }}
          >
            <Outlet />
          </div>
        </Content>
        <Footer style={{ textAlign: 'center' }}>
          <Typography.Text type="secondary">Orchestra Portal</Typography.Text>
        </Footer>
      </Layout>
    </Layout>
  )
}
