import {
  Button, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message, Switch, DatePicker, Typography,
} from 'antd'
import type { FormInstance } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import dayjs from 'dayjs'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type Musician = {
  id: number
  full_name: string
  email: string
  celular: string
  telefone?: string
  apelido?: string
  is_active: boolean
  role_labels: string[]
  instrument_names: string[]
  first_name?: string
  last_name?: string
  birth_date?: string
  roles?: { role_type: string; maestro_order?: number | null; voice_type?: string | null }[]
  instruments?: { id: number }[]
  has_app_access?: boolean
}

type InstrumentOpt = { id: number; nome: string; categoria?: string }

const ROLE_OPTS = [
  { value: 'musico', label: 'Músico' },
  { value: 'maestro', label: 'Maestro' },
  { value: 'chefe_naipe', label: 'Chefe de Naipe' },
  { value: 'arquivista', label: 'Arquivista' },
  { value: 'arranjador', label: 'Arranjador' },
  { value: 'cantor', label: 'Coralista' },
  { value: 'compositor', label: 'Compositor' },
]

const VOICE_OPTS = [
  { value: 'soprano', label: 'Soprano' },
  { value: 'alto', label: 'Alto' },
  { value: 'tenor', label: 'Tenor' },
  { value: 'baixo', label: 'Baixo' },
]

const STATUS_OPTS = [
  { value: 'all', label: 'Todos' },
  { value: 'active', label: 'Ativos' },
  { value: 'inactive', label: 'Inativos' },
]

export function MusicianFormFields({
  form,
  editing,
  instruments,
}: {
  form: FormInstance
  editing: boolean
  instruments: InstrumentOpt[]
}) {
  const { t } = useTranslation()
  const roles: string[] = Form.useWatch('roles', form) || []
  const showMaestro = roles.includes('maestro')
  const showVoice = roles.includes('cantor')
  const appAccess = Form.useWatch('app_access', form)

  return (
    <>
      <Form.Item name="first_name" label={t('label_first_name')} rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="last_name" label={t('label_last_name')} rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="apelido" label="Apelido">
        <Input placeholder="Nome artístico ou apelido (opcional)" />
      </Form.Item>
      <Form.Item name="email" label={t('label_email')} rules={[{ required: true, type: 'email' }]}>
        <Input />
      </Form.Item>
      <Form.Item name="celular" label={t('label_celular')} rules={[{ required: true }]}>
        <Input placeholder="11999999999" />
      </Form.Item>
      <Form.Item name="telefone" label="Telefone">
        <Input placeholder="Opcional" />
      </Form.Item>
      <Form.Item name="birth_date" label={t('label_birth_date')} rules={[{ required: true }]}>
        <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
      </Form.Item>
      <Form.Item name="roles" label={t('label_roles')}>
        <Select mode="multiple" options={ROLE_OPTS} placeholder="Selecione os papéis" />
      </Form.Item>
      {showMaestro && (
        <Form.Item name="maestro_order" label="Ordem do maestro" rules={[{ required: true, message: 'Informe a ordem' }]}>
          <InputNumber min={1} max={20} style={{ width: '100%' }} placeholder="1 = principal" />
        </Form.Item>
      )}
      {showVoice && (
        <Form.Item name="voice_type" label="Tipo de voz" rules={[{ required: true, message: 'Selecione o tipo de voz' }]}>
          <Select options={VOICE_OPTS} placeholder="Soprano, Alto, Tenor ou Baixo" />
        </Form.Item>
      )}
      <Form.Item name="instrumento_ids" label={t('label_instruments', 'Instrumentos')}>
        <Select
          mode="multiple"
          allowClear
          showSearch
          optionFilterProp="label"
          options={instruments.map((i) => ({
            value: i.id,
            label: i.categoria ? `${i.nome} (${i.categoria})` : i.nome,
          }))}
          placeholder="Selecione instrumentos"
        />
      </Form.Item>
      <Form.Item name="is_active" label={t('label_status')} valuePropName="checked">
        <Switch checkedChildren="Ativo" unCheckedChildren="Inativo" />
      </Form.Item>
      {!editing && (
        <Form.Item name="app_password" label={t('label_app_password')}>
          <Input.Password placeholder="Opcional — libera acesso ao app" />
        </Form.Item>
      )}
      {editing && (
        <>
          <Form.Item
            name="app_access"
            label="Acesso ao App / PWA"
            valuePropName="checked"
            extra="Desligar revoga o login no app. Para conceder ou trocar senha, informe uma nova senha abaixo."
          >
            <Switch checkedChildren="Ativo" unCheckedChildren="Revogado" />
          </Form.Item>
          {appAccess && (
            <Form.Item name="app_password" label="Senha do App">
              <Input.Password placeholder="Deixe em branco para manter a atual" />
            </Form.Item>
          )}
        </>
      )}
    </>
  )
}

export function buildMusicianPayload(
  values: Record<string, unknown>,
  editing: boolean,
) {
  const roles = (values.roles as string[]) || []
  const payload: Record<string, unknown> = {
    first_name: values.first_name,
    last_name: values.last_name,
    apelido: values.apelido || null,
    email: values.email,
    celular: values.celular,
    telefone: values.telefone || null,
    birth_date: (values.birth_date as dayjs.Dayjs | undefined)?.format?.('YYYY-MM-DD')
      ?? values.birth_date,
    roles,
    instrumento_ids: values.instrumento_ids || [],
    is_active: values.is_active ?? true,
  }
  if (roles.includes('maestro')) payload.maestro_order = values.maestro_order
  if (roles.includes('cantor')) payload.voice_type = values.voice_type

  if (!editing) {
    if (values.app_password) payload.app_password = values.app_password
  } else if (values.app_access === false) {
    payload.grant_app = false
  } else if (values.app_password) {
    payload.app_password = values.app_password
  }
  return payload
}

export default function MusiciansPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_members
  const [items, setItems] = useState<Musician[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [roleFilter, setRoleFilter] = useState<string | undefined>()
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Musician | null>(null)
  const [instruments, setInstruments] = useState<InstrumentOpt[]>([])
  const [form] = Form.useForm()

  useEffect(() => {
    api.get('/musicians/instruments').then((r) => setInstruments(r.data || [])).catch(() => undefined)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { q, page, page_size: 20 }
      if (roleFilter) params.role = roleFilter
      if (status && status !== 'all') params.status = status
      const { data } = await api.get('/musicians', { params })
      setItems(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [q, page, roleFilter, status])

  useEffect(() => { void load() }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ is_active: true, roles: [], instrumento_ids: [] })
    setOpen(true)
  }

  const openEdit = async (id: number) => {
    const { data } = await api.get(`/musicians/${id}`)
    setEditing(data)
    const roles = (data.roles || []) as Musician['roles']
    const maestroRole = roles?.find((r) => r.role_type === 'maestro')
    const cantorRole = roles?.find((r) => r.role_type === 'cantor')
    form.setFieldsValue({
      ...data,
      birth_date: data.birth_date ? dayjs(data.birth_date) : null,
      roles: (roles || []).map((r) => r.role_type),
      instrumento_ids: (data.instruments || []).map((i: { id: number }) => i.id),
      maestro_order: maestroRole?.maestro_order ?? undefined,
      voice_type: cantorRole?.voice_type ?? undefined,
      app_access: !!data.has_app_access,
      app_password: undefined,
    })
    setOpen(true)
  }

  const onSave = async () => {
    const values = await form.validateFields()
    const payload = buildMusicianPayload(values, !!editing)
    if (editing) {
      await api.put(`/musicians/${editing.id}`, payload)
      message.success('Membro atualizado')
    } else {
      await api.post('/musicians', payload)
      message.success('Membro criado')
    }
    setOpen(false)
    void load()
  }

  return (
    <div>
      <Space wrap style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Space wrap>
          <Input.Search
            placeholder={t('musicians_search')}
            allowClear
            onSearch={(v) => { setPage(1); setQ(v) }}
            style={{ width: 240 }}
          />
          <Select
            allowClear
            placeholder="Papel"
            style={{ width: 180 }}
            options={ROLE_OPTS}
            value={roleFilter}
            onChange={(v) => { setPage(1); setRoleFilter(v) }}
          />
          <Select
            style={{ width: 140 }}
            options={STATUS_OPTS}
            value={status}
            onChange={(v) => { setPage(1); setStatus(v) }}
          />
        </Space>
        {canEdit && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            {t('musicians_add')}
          </Button>
        )}
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        pagination={{ current: page, total, pageSize: 20, onChange: setPage }}
        columns={[
          {
            title: t('label_first_name'),
            render: (_, r) => <Link to={`/musicians/${r.id}`}>{r.full_name}</Link>,
          },
          { title: t('label_email'), dataIndex: 'email' },
          {
            title: t('label_roles'),
            render: (_, r) => (r.role_labels || []).map((l) => <Tag key={l}>{l}</Tag>),
          },
          {
            title: t('label_status'),
            dataIndex: 'is_active',
            render: (v) => (v ? <Tag color="green">{t('status_active')}</Tag> : <Tag>{t('status_inactive')}</Tag>),
          },
          {
            title: t('label_actions'),
            render: (_, r) =>
              canEdit ? (
                <Button type="link" onClick={() => void openEdit(r.id)}>{t('btn_edit', 'Editar')}</Button>
              ) : null,
          },
        ]}
      />

      <Modal
        title={editing ? t('musicians_edit') : t('musicians_add')}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void onSave()}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <MusicianFormFields form={form} editing={!!editing} instruments={instruments} />
        </Form>
        {editing && (
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 12 }}>
            Para revogar o acesso ao app sem editar o restante, use o botão na página de detalhe.
          </Typography.Paragraph>
        )}
      </Modal>
    </div>
  )
}
