import { Card, Col, List, Row, Statistic, Typography, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type Dash = {
  stats: Record<string, number>
  mes_nome: string
  proximos_eventos: { id: number; titulo: string; data_inicio?: string; local?: string }[]
  atencao_itens: { id: string; identificador: string; status: string; tipo: string }[]
  aniversariantes: { id: number; full_name: string; birth_date?: string }[]
}

const INV_KPIS: { key: string; label: string; to: string }[] = [
  { key: 'inv_instrumentos', label: 'Instrumentos', to: '/patrimonio' },
  { key: 'inv_moveis', label: 'Móveis', to: '/patrimonio' },
  { key: 'inv_eletronicos', label: 'Eletrônicos', to: '/patrimonio' },
  { key: 'inv_partituras', label: 'Partituras', to: '/patrimonio' },
  { key: 'inv_decoracoes', label: 'Decorações', to: '/patrimonio' },
]

export default function HomePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [data, setData] = useState<Dash | null>(null)

  useEffect(() => {
    api.get('/dashboard').then((r) => setData(r.data)).catch(() => setData(null))
  }, [])

  const stats = data?.stats || {}
  const invPresent = INV_KPIS.filter((k) => stats[k.key] != null)

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        {t('home_greeting')} {user?.username}
      </Typography.Title>
      <Typography.Paragraph type="secondary">{t('home_description')}</Typography.Paragraph>
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Link to="/musicians">
            <Card hoverable>
              <Statistic title={t('home_total_active')} value={stats.active ?? '—'} />
            </Card>
          </Link>
        </Col>
        <Col xs={12} md={6}>
          <Link to="/patrimonio">
            <Card hoverable>
              <Statistic title={t('home_kpi_loaned')} value={stats.inv_emprestados ?? '—'} />
            </Card>
          </Link>
        </Col>
        <Col xs={12} md={6}>
          <Link to="/patrimonio">
            <Card hoverable>
              <Statistic title={t('home_kpi_maintenance')} value={stats.inv_manutencao ?? '—'} />
            </Card>
          </Link>
        </Col>
        <Col xs={12} md={6}>
          <Link to="/acervo/programacao">
            <Card hoverable>
              <Statistic title={t('home_kpi_events_7d')} value={stats.eventos_7d ?? '—'} />
            </Card>
          </Link>
        </Col>
      </Row>

      {invPresent.length > 0 && (
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          {invPresent.map((k) => (
            <Col xs={12} md={Math.max(4, Math.floor(24 / invPresent.length))} key={k.key}>
              <Link to={k.to}>
                <Card hoverable size="small">
                  <Statistic title={k.label} value={stats[k.key]} />
                </Card>
              </Link>
            </Col>
          ))}
        </Row>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} md={12}>
          <Card
            title={t('home_agenda', 'Próximos eventos')}
            extra={<Link to="/acervo/programacao">Ver programação</Link>}
          >
            <List
              locale={{ emptyText: t('home_agenda_empty') }}
              dataSource={data?.proximos_eventos || []}
              renderItem={(e) => (
                <List.Item>
                  <List.Item.Meta
                    title={<Link to="/acervo/programacao">{e.titulo}</Link>}
                    description={[e.data_inicio?.slice(0, 16), e.local].filter(Boolean).join(' · ')}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title={t('home_attention')}>
            <List
              locale={{ emptyText: t('home_attention_empty') }}
              dataSource={data?.atencao_itens || []}
              renderItem={(p) => (
                <List.Item>
                  <Link to={`/patrimonio/${p.id}`}>{p.identificador}</Link>
                  <Tag style={{ marginLeft: 8 }}>{p.status}</Tag>
                </List.Item>
              )}
            />
          </Card>
          <Card title={`${t('home_birthdays', 'Aniversariantes')} — ${data?.mes_nome || ''}`} style={{ marginTop: 16 }}>
            <List
              dataSource={data?.aniversariantes || []}
              locale={{ emptyText: '—' }}
              renderItem={(m) => (
                <List.Item>
                  <Link to={`/musicians/${m.id}`}>{m.full_name}</Link>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
