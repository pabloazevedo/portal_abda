import {
  Button, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag, message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type Item = {
  id: string
  identificador_interno: string
  tipo_item: string
  tipo_label: string
  status: string
  fabricante?: string
  modelo?: string
  ano_compra?: number
  valor_mercado?: number
  observacoes?: string
  detalhes?: Record<string, unknown>
  emprestimo_ativo?: { musician_name?: string } | null
}

const TIPOS = ['Instrumento', 'Movel', 'Eletronico', 'Partitura', 'Decoracao', 'Outros']
const STATUS = ['Disponivel', 'Emprestado', 'Manutencao', 'Baixa']
const CONDICAO_OPTS = [
  { value: 'Otimo', label: 'Ótimo' },
  { value: 'Bom', label: 'Bom' },
  { value: 'Regular', label: 'Regular' },
  { value: 'Ruim', label: 'Ruim' },
]

export function PatrimonioDetalhesFields({ tipo }: { tipo?: string }) {
  if (tipo === 'Instrumento') {
    return (
      <>
        <Form.Item name="ano_fabricacao" label="Ano de fabricação">
          <InputNumber style={{ width: '100%' }} min={1700} max={2100} />
        </Form.Item>
        <Form.Item name="avaliacao_condicao" label="Avaliação / condição">
          <Select allowClear options={CONDICAO_OPTS} />
        </Form.Item>
      </>
    )
  }
  if (tipo === 'Partitura') {
    return (
      <>
        <Form.Item name="nome_obra" label="Nome da obra" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="compositor" label="Compositor">
          <Input />
        </Form.Item>
        <Form.Item name="arranjador" label="Arranjador">
          <Input />
        </Form.Item>
      </>
    )
  }
  if (tipo === 'Outros') {
    return (
      <>
        <Form.Item name="descricao_livre" label="Descrição">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="local_armazenamento" label="Local de armazenamento">
          <Input />
        </Form.Item>
      </>
    )
  }
  return null
}

export function buildPatrimonioPayload(values: Record<string, unknown>) {
  const tipo = values.tipo_item as string
  const detalhes: Record<string, unknown> = {}
  if (tipo === 'Instrumento') {
    if (values.ano_fabricacao != null) detalhes.ano_fabricacao = values.ano_fabricacao
    if (values.avaliacao_condicao) detalhes.avaliacao_condicao = values.avaliacao_condicao
  } else if (tipo === 'Partitura') {
    if (values.nome_obra) detalhes.nome_obra = values.nome_obra
    if (values.compositor) detalhes.compositor = values.compositor
    if (values.arranjador) detalhes.arranjador = values.arranjador
  } else if (tipo === 'Outros') {
    if (values.descricao_livre) detalhes.descricao_livre = values.descricao_livre
    if (values.local_armazenamento) detalhes.local_armazenamento = values.local_armazenamento
  }
  return {
    tipo_item: tipo,
    status: values.status,
    fabricante: values.fabricante || null,
    modelo: values.modelo || null,
    ano_compra: values.ano_compra ?? null,
    valor_mercado: values.valor_mercado ?? null,
    observacoes: values.observacoes || null,
    detalhes,
  }
}

export function fillPatrimonioForm(form: { setFieldsValue: (v: Record<string, unknown>) => void }, data: Item) {
  const det = data.detalhes || {}
  form.setFieldsValue({
    tipo_item: data.tipo_item,
    status: data.status,
    fabricante: data.fabricante,
    modelo: data.modelo,
    ano_compra: data.ano_compra,
    valor_mercado: data.valor_mercado,
    observacoes: data.observacoes,
    ano_fabricacao: det.ano_fabricacao,
    avaliacao_condicao: det.avaliacao_condicao,
    nome_obra: det.nome_obra,
    compositor: det.compositor,
    arranjador: det.arranjador,
    descricao_livre: det.descricao_livre,
    local_armazenamento: det.local_armazenamento,
  })
}

export default function PatrimonioPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_patrimonio
  const [items, setItems] = useState<Item[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [tipo, setTipo] = useState<string | undefined>()
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Item | null>(null)
  const [form] = Form.useForm()
  const tipoWatch = Form.useWatch('tipo_item', form)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { q, page, page_size: 20 }
      if (tipo) params.tipo = tipo
      if (statusFilter) params.status = statusFilter
      const { data } = await api.get('/patrimonio', { params })
      setItems(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [q, page, tipo, statusFilter])

  useEffect(() => { void load() }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ tipo_item: 'Instrumento', status: 'Disponivel' })
    setOpen(true)
  }

  const openEdit = async (id: string) => {
    const { data } = await api.get(`/patrimonio/${id}`)
    setEditing(data)
    fillPatrimonioForm(form, data)
    setOpen(true)
  }

  const onSave = async () => {
    const values = await form.validateFields()
    const payload = buildPatrimonioPayload(values)
    if (editing) {
      await api.put(`/patrimonio/${editing.id}`, payload)
      message.success('Item atualizado')
    } else {
      await api.post('/patrimonio', payload)
      message.success('Item criado')
    }
    setOpen(false)
    void load()
  }

  return (
    <div>
      <Space wrap style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Space wrap>
          <Input.Search
            placeholder="Buscar identificador, fabricante..."
            allowClear
            onSearch={(v) => { setPage(1); setQ(v) }}
            style={{ width: 260 }}
          />
          <Select
            allowClear
            placeholder="Tipo"
            style={{ width: 160 }}
            options={TIPOS.map((v) => ({ value: v, label: v }))}
            value={tipo}
            onChange={(v) => { setPage(1); setTipo(v) }}
          />
          <Select
            allowClear
            placeholder="Status"
            style={{ width: 150 }}
            options={STATUS.map((v) => ({ value: v, label: v }))}
            value={statusFilter}
            onChange={(v) => { setPage(1); setStatusFilter(v) }}
          />
        </Space>
        {canEdit && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Novo item
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
            title: 'ID',
            render: (_, r) => <Link to={`/patrimonio/${r.id}`}>{r.identificador_interno}</Link>,
          },
          { title: 'Tipo', dataIndex: 'tipo_label' },
          { title: 'Status', dataIndex: 'status', render: (s) => <Tag>{s}</Tag> },
          { title: 'Fabricante', dataIndex: 'fabricante' },
          { title: 'Modelo', dataIndex: 'modelo' },
          {
            title: 'Empréstimo',
            render: (_, r) => r.emprestimo_ativo?.musician_name || '—',
          },
          {
            title: 'Ações',
            render: (_, r) =>
              canEdit ? (
                <Space>
                  <Button type="link" onClick={() => void openEdit(r.id)}>Editar</Button>
                  <Popconfirm
                    title="Excluir este item?"
                    okType="danger"
                    onConfirm={async () => {
                      await api.delete(`/patrimonio/${r.id}`)
                      message.success('Excluído')
                      void load()
                    }}
                  >
                    <Button type="link" danger>Excluir</Button>
                  </Popconfirm>
                </Space>
              ) : null,
          },
        ]}
      />
      <Modal
        open={open}
        title={editing ? 'Editar patrimônio' : 'Novo patrimônio'}
        onCancel={() => setOpen(false)}
        onOk={() => void onSave()}
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="tipo_item" label="Tipo" rules={[{ required: true }]}>
            <Select options={TIPOS.map((v) => ({ value: v, label: v }))} disabled={!!editing} />
          </Form.Item>
          <Form.Item name="status" label="Status">
            <Select options={STATUS.map((v) => ({ value: v, label: v }))} />
          </Form.Item>
          <Form.Item name="fabricante" label="Fabricante"><Input /></Form.Item>
          <Form.Item name="modelo" label="Modelo"><Input /></Form.Item>
          <Form.Item name="ano_compra" label="Ano de compra"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="valor_mercado" label="Valor"><InputNumber style={{ width: '100%' }} min={0} /></Form.Item>
          <PatrimonioDetalhesFields tipo={tipoWatch} />
          <Form.Item name="observacoes" label="Observações"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
      <span style={{ display: 'none' }}>{t('nav_home')}</span>
    </div>
  )
}
