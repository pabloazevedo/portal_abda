import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const GENEROS = [
  { value: 'sinfonia', label: 'Sinfonia' },
  { value: 'concerto', label: 'Concerto' },
  { value: 'camara', label: 'Câmara' },
  { value: 'coral', label: 'Coral' },
  { value: 'opera', label: 'Ópera' },
  { value: 'sacra', label: 'Sacra' },
  { value: 'popular', label: 'Popular' },
  { value: 'folclorica', label: 'Folclórica' },
  { value: 'contemporanea', label: 'Contemporânea' },
  { value: 'outro', label: 'Outro' },
]

const COPYRIGHT_OPTS = [
  { value: 'dominio_publico', label: 'Domínio público' },
  { value: 'licenciado', label: 'Licenciado' },
  { value: 'pendente', label: 'Pendente' },
]

function ObraFormFields() {
  return (
    <>
      <Form.Item name="titulo" label="Título" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="titulo_original" label="Título original">
        <Input />
      </Form.Item>
      <Form.Item name="compositor_nome" label="Compositor">
        <Input />
      </Form.Item>
      <Form.Item name="genero" label="Gênero" initialValue="outro">
        <Select options={GENEROS} />
      </Form.Item>
      <Form.Item name="tonalidade" label="Tonalidade">
        <Input />
      </Form.Item>
      <Form.Item name="ano_composicao" label="Ano de composição">
        <InputNumber style={{ width: '100%' }} min={1000} max={2100} />
      </Form.Item>
      <Form.Item name="observacoes" label="Observações">
        <Input.TextArea rows={3} />
      </Form.Item>
    </>
  )
}

function ObrasTab() {
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_acervo
  const [items, setItems] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Record<string, unknown> | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    const { data } = await api.get('/acervo/obras', { params: { q, page, page_size: 20 } })
    setItems(data.items)
    setTotal(data.total)
  }, [q, page])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ genero: 'outro' })
    setOpen(true)
  }

  const openEdit = (row: Record<string, unknown>) => {
    setEditing(row)
    form.setFieldsValue(row)
    setOpen(true)
  }

  return (
    <>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Input.Search
          allowClear
          onSearch={(v) => {
            setPage(1)
            setQ(v)
          }}
          style={{ width: 280 }}
        />
        {canEdit && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Nova obra
          </Button>
        )}
      </Space>
      <Table
        rowKey="id"
        dataSource={items}
        pagination={{ current: page, total, pageSize: 20, onChange: setPage }}
        columns={[
          {
            title: 'Título',
            render: (_, r) => <Link to={`/acervo/obras/${r.id}`}>{String(r.titulo)}</Link>,
          },
          { title: 'Compositor', dataIndex: 'compositor_label' },
          { title: 'Gênero', dataIndex: 'genero' },
          { title: 'Ano', dataIndex: 'ano_composicao', width: 80 },
          { title: 'Arranjos', dataIndex: 'arranjos_count', width: 90 },
          ...(canEdit
            ? [
                {
                  title: 'Ações',
                  width: 160,
                  render: (_: unknown, r: Record<string, unknown>) => (
                    <Space>
                      <Button type="link" size="small" onClick={() => openEdit(r)}>
                        Editar
                      </Button>
                      <Popconfirm
                        title="Excluir esta obra?"
                        onConfirm={async () => {
                          await api.delete(`/acervo/obras/${r.id}`)
                          message.success('Obra excluída')
                          void load()
                        }}
                      >
                        <Button type="link" danger size="small">
                          Excluir
                        </Button>
                      </Popconfirm>
                    </Space>
                  ),
                },
              ]
            : []),
        ]}
      />
      <Modal
        open={open}
        title={editing ? 'Editar obra' : 'Nova obra'}
        onCancel={() => setOpen(false)}
        onOk={async () => {
          const values = await form.validateFields()
          if (editing) {
            await api.put(`/acervo/obras/${editing.id}`, values)
            message.success('Obra atualizada')
          } else {
            await api.post('/acervo/obras', values)
            message.success('Obra criada')
          }
          setOpen(false)
          void load()
        }}
        width={560}
      >
        <Form form={form} layout="vertical">
          <ObraFormFields />
        </Form>
      </Modal>
    </>
  )
}

function ArranjosTab() {
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_acervo
  const [items, setItems] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [obras, setObras] = useState<{ id: number; titulo: string }[]>([])
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    const { data } = await api.get('/acervo/arranjos', { params: { q, page, page_size: 20 } })
    setItems(data.items)
    setTotal(data.total)
  }, [q, page])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = async () => {
    form.resetFields()
    form.setFieldsValue({ copyright_status: 'pendente', ativo: true })
    const { data } = await api.get('/acervo/obras', { params: { page_size: 100 } })
    setObras(data.items || [])
    setOpen(true)
  }

  return (
    <>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Input.Search
          allowClear
          onSearch={(v) => {
            setPage(1)
            setQ(v)
          }}
          style={{ width: 280 }}
        />
        {canEdit && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => void openCreate()}>
            Novo arranjo
          </Button>
        )}
      </Space>
      <Table
        rowKey="id"
        dataSource={items}
        pagination={{ current: page, total, pageSize: 20, onChange: setPage }}
        columns={[
          {
            title: 'Obra',
            render: (_, r) =>
              r.obra_id ? (
                <Link to={`/acervo/obras/${r.obra_id}`}>{String(r.obra_titulo || '—')}</Link>
              ) : (
                String(r.obra_titulo || '—')
              ),
          },
          {
            title: 'Título',
            render: (_, r) => (
              <Link to={`/acervo/arranjos/${r.id}`}>{String(r.titulo_arranjo || `Arranjo #${r.id}`)}</Link>
            ),
          },
          { title: 'Arranjador', dataIndex: 'arranjador_label' },
          { title: 'Instrumentação', dataIndex: 'instrumentacao', ellipsis: true },
          { title: 'Copyright', dataIndex: 'copyright_status', width: 120 },
          ...(canEdit
            ? [
                {
                  title: 'Ações',
                  width: 100,
                  render: (_: unknown, r: Record<string, unknown>) => (
                    <Popconfirm
                      title="Excluir este arranjo?"
                      onConfirm={async () => {
                        await api.delete(`/acervo/arranjos/${r.id}`)
                        message.success('Arranjo excluído')
                        void load()
                      }}
                    >
                      <Button type="link" danger size="small">
                        Excluir
                      </Button>
                    </Popconfirm>
                  ),
                },
              ]
            : []),
        ]}
      />
      <Modal
        open={open}
        title="Novo arranjo"
        onCancel={() => setOpen(false)}
        onOk={async () => {
          const values = await form.validateFields()
          await api.post('/acervo/arranjos', values)
          message.success('Arranjo criado')
          setOpen(false)
          void load()
        }}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="obra_id" label="Obra" rules={[{ required: true }]}>
            <Select
              showSearch
              optionFilterProp="label"
              options={obras.map((o) => ({ value: o.id, label: o.titulo }))}
            />
          </Form.Item>
          <Form.Item name="titulo_arranjo" label="Título do arranjo">
            <Input />
          </Form.Item>
          <Form.Item name="instrumentacao" label="Instrumentação" rules={[{ required: true }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="arranjador_nome" label="Arranjador">
            <Input />
          </Form.Item>
          <Form.Item name="copyright_status" label="Copyright">
            <Select options={COPYRIGHT_OPTS} />
          </Form.Item>
          <Form.Item name="editora" label="Editora">
            <Input />
          </Form.Item>
          <Form.Item name="duracao_segundos" label="Duração (segundos)">
            <InputNumber style={{ width: '100%' }} min={0} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}

function BuscaTab() {
  const [form] = Form.useForm()
  const [items, setItems] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(false)

  const onSearch = async () => {
    const values = await form.validateFields()
    setLoading(true)
    try {
      const { data } = await api.get('/acervo/busca', { params: values })
      setItems(data.items || [])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Form form={form} layout="inline" style={{ marginBottom: 16, gap: 8, flexWrap: 'wrap' }} onFinish={() => void onSearch()}>
        <Form.Item name="q" label="Busca">
          <Input placeholder="Título / instrumentação" allowClear style={{ width: 200 }} />
        </Form.Item>
        <Form.Item name="compositor" label="Compositor">
          <Input allowClear style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="arranjador" label="Arranjador">
          <Input allowClear style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="instrumento" label="Instrumento">
          <Input allowClear style={{ width: 140 }} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          Buscar
        </Button>
      </Form>
      <Table
        rowKey={(r) => `${r.arranjo_id}-${r.obra_id}`}
        loading={loading}
        dataSource={items}
        pagination={{ pageSize: 20 }}
        columns={[
          {
            title: 'Obra',
            render: (_, r) =>
              r.obra_id ? <Link to={`/acervo/obras/${r.obra_id}`}>{String(r.titulo || '—')}</Link> : '—',
          },
          { title: 'Compositor', dataIndex: 'compositor' },
          {
            title: 'Arranjo',
            render: (_, r) => (
              <Link to={`/acervo/arranjos/${r.arranjo_id}`}>{String(r.titulo_arranjo || '—')}</Link>
            ),
          },
          { title: 'Arranjador', dataIndex: 'arranjador' },
          { title: 'Instrumentação', dataIndex: 'instrumentacao', ellipsis: true },
        ]}
      />
    </>
  )
}

function HistoricoTab() {
  const [execucoes, setExecucoes] = useState<Record<string, unknown>[]>([])
  const [topMais, setTopMais] = useState<{ titulo: string; total: number }[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api
      .get('/acervo/historico')
      .then((r) => {
        setExecucoes(r.data.execucoes || [])
        setTopMais(r.data.top_mais || [])
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      {topMais.length > 0 && (
        <Table
          size="small"
          style={{ marginBottom: 24, maxWidth: 480 }}
          pagination={false}
          rowKey="titulo"
          dataSource={topMais}
          title={() => 'Obras mais executadas'}
          columns={[
            { title: 'Obra', dataIndex: 'titulo' },
            { title: 'Execuções', dataIndex: 'total', width: 100 },
          ]}
        />
      )}
      <Table
        rowKey="id"
        loading={loading}
        dataSource={execucoes}
        pagination={{ pageSize: 25 }}
        columns={[
          {
            title: 'Data',
            dataIndex: 'data_execucao',
            render: (v) => (v ? String(v).slice(0, 16).replace('T', ' ') : '—'),
          },
          {
            title: 'Obra',
            render: (_, r) =>
              r.obra_id ? (
                <Link to={`/acervo/obras/${r.obra_id}`}>{String(r.obra_titulo || '—')}</Link>
              ) : (
                String(r.obra_titulo || '—')
              ),
          },
          {
            title: 'Arranjo',
            render: (_, r) =>
              r.arranjo_id ? (
                <Link to={`/acervo/arranjos/${r.arranjo_id}`}>{String(r.titulo_arranjo || '—')}</Link>
              ) : (
                '—'
              ),
          },
          { title: 'Concerto', dataIndex: 'concerto_titulo' },
          {
            title: 'Duração (s)',
            dataIndex: 'duracao_real_s',
            width: 110,
          },
          { title: 'Obs.', dataIndex: 'observacoes', ellipsis: true },
        ]}
      />
    </>
  )
}

export default function AcervoPage() {
  const { tab } = useParams()
  const nav = useNavigate()
  const active = tab || 'obras'

  return (
    <Tabs
      activeKey={active}
      onChange={(k) => {
        if (k === 'concertos') {
          nav('/acervo/programacao')
          return
        }
        nav(`/acervo/${k}`)
      }}
      items={[
        { key: 'obras', label: 'Obras', children: <ObrasTab /> },
        { key: 'arranjos', label: 'Arranjos', children: <ArranjosTab /> },
        { key: 'busca', label: 'Busca', children: <BuscaTab /> },
        { key: 'historico', label: 'Histórico', children: <HistoricoTab /> },
        { key: 'concertos', label: 'Programação →' },
      ]}
    />
  )
}
