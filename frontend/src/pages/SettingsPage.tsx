import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Upload,
  message,
} from 'antd'
import { DownloadOutlined, InboxOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import i18n from '../i18n'
import { useAuth } from '../auth/AuthContext'

async function downloadBlob(path: string, params?: Record<string, string | number>) {
  const res = await api.get(path, { params, responseType: 'blob' })
  const disposition = res.headers['content-disposition'] as string | undefined
  let filename = 'download'
  if (disposition) {
    const m = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(disposition)
    if (m?.[1]) filename = decodeURIComponent(m[1])
  }
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function SettingsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const isAdmin = user?.permissions?.is_admin
  const [form] = Form.useForm()
  const [smtpForm] = Form.useForm()
  const [logo, setLogo] = useState<string | null>(null)
  const [health, setHealth] = useState<{
    status: string
    services: Record<string, { status: string; label: string; detail: string }>
  } | null>(null)
  const [audit, setAudit] = useState<{ items: Record<string, unknown>[]; total: number }>({
    items: [],
    total: 0,
  })
  const [auditQ, setAuditQ] = useState('')
  const [auditAction, setAuditAction] = useState('')
  const [auditPage, setAuditPage] = useState(1)

  const loadSettings = useCallback(async () => {
    const { data } = await api.get('/settings')
    form.setFieldsValue(data.config)
    setLogo(data.config?.logo || null)
    if (data.config?.idioma) void i18n.changeLanguage(data.config.idioma)
  }, [form])

  const loadSmtp = useCallback(async () => {
    if (!isAdmin) return
    const { data } = await api.get('/settings/smtp')
    smtpForm.setFieldsValue(data)
  }, [isAdmin, smtpForm])

  const loadAudit = useCallback(async () => {
    if (!isAdmin) return
    const { data } = await api.get('/settings/audit', {
      params: { q: auditQ, action: auditAction, page: auditPage, page_size: 50 },
    })
    setAudit(data)
  }, [isAdmin, auditQ, auditAction, auditPage])

  const loadHealth = useCallback(async () => {
    if (!isAdmin) return
    try {
      const { data } = await api.get('/settings/health')
      setHealth(data)
    } catch {
      setHealth(null)
    }
  }, [isAdmin])

  useEffect(() => {
    void loadSettings()
  }, [loadSettings])

  useEffect(() => {
    void loadSmtp()
    void loadHealth()
  }, [loadSmtp, loadHealth])

  useEffect(() => {
    void loadAudit()
  }, [loadAudit])

  const onSaveGeral = async () => {
    const values = await form.validateFields()
    const { data } = await api.put('/settings', values)
    message.success('Configurações salvas')
    setLogo(data.config?.logo || null)
    if (data.config?.idioma) void i18n.changeLanguage(data.config.idioma)
  }

  const tabs = [
    {
      key: 'geral',
      label: 'Geral',
      children: (
        <Form form={form} layout="vertical" style={{ maxWidth: 560 }} onFinish={() => void onSaveGeral()}>
          <Form.Item name="nome_institucional" label={t('settings_footer_name', 'Nome institucional')}>
            <Input />
          </Form.Item>
          <Form.Item name="endereco" label={t('settings_footer_address', 'Endereço')}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="link_estatuto" label="Link estatuto">
            <Input />
          </Form.Item>
          <Form.Item name="link_repositorio" label="Link repositório">
            <Input />
          </Form.Item>
          <Form.Item name="app_base_url" label="URL base da aplicação">
            <Input placeholder="https://portal.exemplo.org" />
          </Form.Item>
          <Form.Item name="idioma" label={t('nav_language')}>
            <Select
              options={[
                { value: 'pt', label: 'Português' },
                { value: 'en', label: 'English' },
                { value: 'es', label: 'Español' },
              ]}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit">
            {t('btn_save', 'Salvar')}
          </Button>
        </Form>
      ),
    },
    {
      key: 'aparencia',
      label: 'Aparência',
      children: (
        <div style={{ maxWidth: 480 }}>
          {logo ? (
            <img
              src={`/uploads/${logo}`}
              alt="Logo"
              style={{ maxHeight: 96, marginBottom: 16, display: '1px solid #ddd', borderRadius: 8, padding: 8 }}
            />
          ) : (
            <p style={{ color: '#888' }}>Nenhum logo personalizado.</p>
          )}
          {isAdmin && (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Upload.Dragger
                accept=".png,.jpg,.jpeg,.svg,.webp"
                maxCount={1}
                showUploadList={false}
                customRequest={async ({ file, onSuccess, onError }) => {
                  try {
                    const fd = new FormData()
                    fd.append('logo', file as File)
                    const { data } = await api.post('/settings/logo', fd, {
                      headers: { 'Content-Type': 'multipart/form-data' },
                    })
                    setLogo(data.logo)
                    message.success('Logo atualizado')
                    onSuccess?.(data)
                  } catch (e) {
                    message.error('Falha no upload')
                    onError?.(e as Error)
                  }
                }}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">Enviar logo (PNG, JPG, SVG, WebP)</p>
              </Upload.Dragger>
              {logo && (
                <Button
                  danger
                  onClick={async () => {
                    await api.post('/settings/logo/remove')
                    setLogo(null)
                    message.success('Logo removido')
                  }}
                >
                  Remover logo
                </Button>
              )}
            </Space>
          )}
        </div>
      ),
    },
    ...(isAdmin
      ? [
          {
            key: 'email',
            label: 'E-mail',
            children: (
              <Form
                form={smtpForm}
                layout="vertical"
                style={{ maxWidth: 560 }}
                onFinish={async () => {
                  const values = await smtpForm.validateFields()
                  await api.put('/settings/smtp', values)
                  message.success('SMTP salvo')
                  void loadSmtp()
                }}
              >
                <Form.Item name="smtp_host" label="Host">
                  <Input />
                </Form.Item>
                <Form.Item name="smtp_port" label="Porta">
                  <InputNumber style={{ width: '100%' }} min={1} max={65535} />
                </Form.Item>
                <Form.Item name="smtp_user" label="Usuário">
                  <Input />
                </Form.Item>
                <Form.Item name="smtp_password" label="Senha">
                  <Input.Password placeholder="Deixe em branco para manter" />
                </Form.Item>
                <Form.Item name="smtp_from" label="Remetente (From)">
                  <Input />
                </Form.Item>
                <Form.Item name="smtp_tls" label="TLS" valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit">
                    Salvar
                  </Button>
                  <Button
                    onClick={async () => {
                      const { data } = await api.post('/settings/smtp/test', {})
                      message.success(`E-mail de teste enviado para ${data.to}`)
                    }}
                  >
                    Testar envio
                  </Button>
                </Space>
              </Form>
            ),
          },
          {
            key: 'dados',
            label: 'Dados',
            children: (
              <Space direction="vertical" size="middle">
                <Card size="small" title="Membros">
                  <Space wrap>
                    <Button icon={<DownloadOutlined />} onClick={() => void downloadBlob('/settings/export', { format: 'xlsx' })}>
                      Excel
                    </Button>
                    <Button icon={<DownloadOutlined />} onClick={() => void downloadBlob('/settings/export', { format: 'csv' })}>
                      CSV
                    </Button>
                    <Button icon={<DownloadOutlined />} onClick={() => void downloadBlob('/settings/export', { format: 'json' })}>
                      JSON
                    </Button>
                  </Space>
                </Card>
                <Card size="small" title="Patrimônio">
                  <Space wrap>
                    <Button
                      icon={<DownloadOutlined />}
                      onClick={() => void downloadBlob('/settings/export-patrimonio', { format: 'xlsx' })}
                    >
                      Excel
                    </Button>
                    <Button
                      icon={<DownloadOutlined />}
                      onClick={() => void downloadBlob('/settings/export-patrimonio', { format: 'csv' })}
                    >
                      CSV
                    </Button>
                  </Space>
                </Card>
                <Card size="small" title="Aniversariantes do mês">
                  <Button
                    icon={<DownloadOutlined />}
                    onClick={() => void downloadBlob('/settings/export-aniversariantes', { format: 'xlsx' })}
                  >
                    Excel
                  </Button>
                </Card>
              </Space>
            ),
          },
          {
            key: 'sistema',
            label: 'Sistema',
            children: (
              <div>
                <Form form={form} layout="vertical" style={{ maxWidth: 560, marginBottom: 24 }} onFinish={() => void onSaveGeral()}>
                  <Form.Item name="pwa_enabled" label="PWA / site mobile" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                  <Form.Item name="audit_retention_days" label="Retenção auditoria (dias)">
                    <InputNumber min={7} max={90} style={{ width: '100%' }} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">
                    Salvar
                  </Button>
                </Form>
                <Space style={{ marginBottom: 12 }}>
                  <Button onClick={() => void loadHealth()}>Atualizar health</Button>
                  {health && (
                    <Tag color={health.status === 'ok' ? 'green' : health.status === 'degraded' ? 'orange' : 'red'}>
                      {health.status}
                    </Tag>
                  )}
                </Space>
                {health && (
                  <Row gutter={[12, 12]}>
                    {Object.entries(health.services || {}).map(([key, svc]) => (
                      <Col xs={24} md={8} key={key}>
                        <Card size="small" title={svc.label}>
                          <Tag color={svc.status === 'ok' ? 'green' : svc.status === 'degraded' ? 'orange' : 'red'}>
                            {svc.status}
                          </Tag>
                          <p style={{ marginTop: 8, marginBottom: 0 }}>{svc.detail}</p>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                )}
              </div>
            ),
          },
          {
            key: 'auditoria',
            label: 'Auditoria',
            children: (
              <>
                <Space style={{ marginBottom: 16 }} wrap>
                  <Input.Search
                    placeholder="Buscar"
                    allowClear
                    style={{ width: 240 }}
                    onSearch={(v) => {
                      setAuditPage(1)
                      setAuditQ(v)
                    }}
                  />
                  <Input
                    placeholder="Ação"
                    allowClear
                    style={{ width: 180 }}
                    onChange={(e) => setAuditAction(e.target.value)}
                    onPressEnter={() => {
                      setAuditPage(1)
                      void loadAudit()
                    }}
                  />
                  <Button
                    type="primary"
                    onClick={() => {
                      setAuditPage(1)
                      void loadAudit()
                    }}
                  >
                    Filtrar
                  </Button>
                </Space>
                <Table
                  rowKey="id"
                  dataSource={audit.items}
                  pagination={{
                    total: audit.total,
                    pageSize: 50,
                    current: auditPage,
                    onChange: setAuditPage,
                  }}
                  columns={[
                    { title: 'Quando', dataIndex: 'created_at', width: 180 },
                    { title: 'Quem', dataIndex: 'actor_username', width: 120 },
                    { title: 'Ação', dataIndex: 'action' },
                    { title: 'Resumo', dataIndex: 'summary', ellipsis: true },
                  ]}
                />
              </>
            ),
          },
        ]
      : []),
  ]

  return (
    <div>
      <h2>{t('nav_settings')}</h2>
      <Tabs destroyInactiveTabPane items={tabs} />
    </div>
  )
}
