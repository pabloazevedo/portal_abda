import {
  Button,
  Checkbox,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import type { EventClickArg, EventInput, EventSourceFuncArg } from '@fullcalendar/core'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import dayjs from 'dayjs'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type ProgramaItem = {
  id: number
  arranjo_id: number
  ordem?: number
  titulo?: string
  data_execucao?: string
  duracao_real_s?: number
  observacoes?: string
  documentos?: { id: number; tipo: string; tipo_label?: string; instrumento_nome?: string }[]
}

type Concerto = {
  id: number
  titulo: string
  data_inicio?: string
  data_fim?: string
  local?: string
  maestro_id?: number
  maestro_nome?: string
  descricao?: string
  publico?: boolean
  programa?: ProgramaItem[]
}

type DistSugestao = {
  musician_id: number
  musician_name: string
  musician_email?: string
  documento_ids: number[]
  documentos: { id: number; tipo: string; tipo_label?: string; instrumento_nome?: string }[]
}

export default function ProgramacaoPage() {
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_acervo
  const [view, setView] = useState<'calendario' | 'lista'>('calendario')
  const [items, setItems] = useState<Concerto[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Concerto | null>(null)
  const [detail, setDetail] = useState<Concerto | null>(null)
  const [maestros, setMaestros] = useState<{ id: number; full_name: string }[]>([])
  const [arranjos, setArranjos] = useState<{ id: number; label: string }[]>([])
  const [form] = Form.useForm()
  const [addArranjoId, setAddArranjoId] = useState<number | null>(null)
  const [execOpen, setExecOpen] = useState(false)
  const [execItem, setExecItem] = useState<ProgramaItem | null>(null)
  const [execForm] = Form.useForm()
  const [distOpen, setDistOpen] = useState(false)
  const [distSugestoes, setDistSugestoes] = useState<DistSugestao[]>([])
  const [distChecked, setDistChecked] = useState<Record<number, number[]>>({})
  const [enviarEmail, setEnviarEmail] = useState(false)
  const [calKey, setCalKey] = useState(0)

  const loadLista = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/programacao/concertos')
      setItems(data.items || [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (view === 'lista') void loadLista()
  }, [view, loadLista])

  const loadMaestros = async () => {
    const { data } = await api.get('/musicians', {
      params: { role: 'maestro', status: 'active', page_size: 100 },
    })
    setMaestros(data.items || [])
  }

  const openCreate = async () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ publico: true })
    await loadMaestros()
    setOpen(true)
  }

  const openEdit = async (c: Concerto) => {
    setEditing(c)
    form.setFieldsValue({
      ...c,
      data_inicio: c.data_inicio ? dayjs(c.data_inicio) : null,
      data_fim: c.data_fim ? dayjs(c.data_fim) : null,
    })
    await loadMaestros()
    setOpen(true)
  }

  const openDetail = async (id: number) => {
    const { data } = await api.get(`/programacao/concertos/${id}`)
    setDetail(data)
    setAddArranjoId(null)
  }

  const refreshDetail = async () => {
    if (!detail) return
    const { data } = await api.get(`/programacao/concertos/${detail.id}`)
    setDetail(data)
  }

  const loadArranjos = async () => {
    const { data } = await api.get('/acervo/arranjos', { params: { page_size: 100 } })
    setArranjos(
      (data.items || []).map((a: Record<string, unknown>) => ({
        id: a.id as number,
        label: `${a.obra_titulo || 'Obra'} — ${a.titulo_arranjo || `#${a.id}`}`,
      })),
    )
  }

  const openDistribuicao = async () => {
    if (!detail) return
    const { data } = await api.get(`/programacao/concertos/${detail.id}/distribuicao`)
    const sugestoes: DistSugestao[] = data.sugestoes || []
    setDistSugestoes(sugestoes)
    const checked: Record<number, number[]> = {}
    for (const s of sugestoes) {
      checked[s.musician_id] = [...(s.documento_ids || [])]
    }
    setDistChecked(checked)
    setEnviarEmail(false)
    setDistOpen(true)
  }

  const fetchEvents = async (
    info: EventSourceFuncArg,
    success: (events: EventInput[]) => void,
    failure: (err: Error) => void,
  ) => {
    try {
      const { data } = await api.get('/programacao/eventos', {
        params: {
          start: info.startStr,
          end: info.endStr,
        },
      })
      success(
        (data || []).map((e: Record<string, unknown>) => ({
          ...e,
          url: undefined,
        })) as EventInput[],
      )
    } catch (err) {
      failure(err as Error)
    }
  }

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Programação
        </Typography.Title>
        <Space>
          <Segmented
            value={view}
            onChange={(v) => setView(v as 'calendario' | 'lista')}
            options={[
              { label: 'Calendário', value: 'calendario' },
              { label: 'Lista', value: 'lista' },
            ]}
          />
          {canEdit && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => void openCreate()}>
              Novo evento
            </Button>
          )}
        </Space>
      </Space>

      {view === 'calendario' ? (
        <FullCalendar
          key={calKey}
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay',
          }}
          locale="pt-br"
          height="auto"
          events={(info, success, failure) => void fetchEvents(info, success, failure)}
          eventClick={(arg: EventClickArg) => {
            arg.jsEvent.preventDefault()
            const id = Number(arg.event.id)
            if (id) void openDetail(id)
          }}
        />
      ) : (
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          columns={[
            {
              title: 'Título',
              render: (_, r) => (
                <Button type="link" onClick={() => void openDetail(r.id)}>
                  {r.titulo}
                </Button>
              ),
            },
            {
              title: 'Início',
              dataIndex: 'data_inicio',
              render: (v) => (v ? dayjs(v).format('DD/MM/YYYY HH:mm') : '—'),
            },
            { title: 'Local', dataIndex: 'local' },
            { title: 'Maestro', dataIndex: 'maestro_nome' },
            {
              title: 'Público',
              dataIndex: 'publico',
              render: (v) => (v ? <Tag color="green">sim</Tag> : <Tag>não</Tag>),
            },
            ...(canEdit
              ? [
                  {
                    title: 'Ações',
                    width: 160,
                    render: (_: unknown, r: Concerto) => (
                      <Space>
                        <Button type="link" size="small" onClick={() => void openEdit(r)}>
                          Editar
                        </Button>
                        <Popconfirm
                          title="Excluir evento?"
                          onConfirm={async () => {
                            await api.delete(`/programacao/concertos/${r.id}`)
                            message.success('Excluído')
                            void loadLista()
                            setCalKey((k) => k + 1)
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
      )}

      <Modal
        open={open}
        title={editing ? 'Editar evento' : 'Novo evento'}
        onCancel={() => setOpen(false)}
        onOk={async () => {
          const values = await form.validateFields()
          const payload = {
            ...values,
            data_inicio: values.data_inicio.toISOString(),
            data_fim: values.data_fim ? values.data_fim.toISOString() : null,
          }
          if (editing) {
            await api.put(`/programacao/concertos/${editing.id}`, payload)
            message.success('Atualizado')
          } else {
            await api.post('/programacao/concertos', payload)
            message.success('Criado')
          }
          setOpen(false)
          void loadLista()
          setCalKey((k) => k + 1)
          if (detail && editing && detail.id === editing.id) void refreshDetail()
        }}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="titulo" label="Título" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="data_inicio" label="Início" rules={[{ required: true }]}>
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="data_fim" label="Fim">
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="local" label="Local">
            <Input />
          </Form.Item>
          <Form.Item name="maestro_id" label="Maestro">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={maestros.map((m) => ({ value: m.id, label: m.full_name }))}
            />
          </Form.Item>
          <Form.Item name="descricao" label="Descrição">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="publico" label="Público" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        open={!!detail}
        onClose={() => setDetail(null)}
        width={560}
        title={detail?.titulo}
        extra={
          canEdit && detail ? (
            <Space>
              <Button onClick={() => void openEdit(detail)}>Editar</Button>
              <Button onClick={() => void openDistribuicao()}>Distribuição</Button>
            </Space>
          ) : null
        }
      >
        {detail && (
          <>
            <p>
              {detail.data_inicio ? dayjs(detail.data_inicio).format('DD/MM/YYYY HH:mm') : ''}
              {detail.local ? ` · ${detail.local}` : ''}
              {detail.maestro_nome ? ` · ${detail.maestro_nome}` : ''}
            </p>
            {detail.descricao && <p style={{ color: '#666' }}>{detail.descricao}</p>}

            <Typography.Title level={5}>Programa</Typography.Title>
            <Table
              size="small"
              rowKey="id"
              pagination={false}
              dataSource={detail.programa || []}
              columns={[
                {
                  title: 'Peça',
                  render: (_, r) => (
                    <Link to={`/acervo/arranjos/${r.arranjo_id}`}>{r.titulo || `Arranjo #${r.arranjo_id}`}</Link>
                  ),
                },
                {
                  title: 'Execução',
                  render: (_, r) =>
                    r.data_execucao ? dayjs(r.data_execucao).format('DD/MM/YY HH:mm') : '—',
                },
                ...(canEdit
                  ? [
                      {
                        title: '',
                        width: 200,
                        render: (_: unknown, r: ProgramaItem) => (
                          <Space size={0}>
                            {!r.data_execucao && (
                              <Button
                                type="link"
                                size="small"
                                onClick={() => {
                                  setExecItem(r)
                                  execForm.resetFields()
                                  execForm.setFieldsValue({ data_execucao: dayjs() })
                                  setExecOpen(true)
                                }}
                              >
                                Execução
                              </Button>
                            )}
                            {!r.data_execucao && (
                              <Popconfirm
                                title="Remover do programa?"
                                onConfirm={async () => {
                                  await api.delete(`/programacao/concertos/${detail.id}/programa/${r.id}`)
                                  message.success('Removido')
                                  void refreshDetail()
                                }}
                              >
                                <Button type="link" danger size="small">
                                  Remover
                                </Button>
                              </Popconfirm>
                            )}
                          </Space>
                        ),
                      },
                    ]
                  : []),
              ]}
            />

            {canEdit && (
              <Space style={{ marginTop: 12 }} wrap>
                <Select
                  style={{ width: 280 }}
                  showSearch
                  optionFilterProp="label"
                  placeholder="Adicionar arranjo"
                  value={addArranjoId}
                  onFocus={() => void loadArranjos()}
                  onChange={setAddArranjoId}
                  options={arranjos.map((a) => ({ value: a.id, label: a.label }))}
                />
                <Button
                  type="primary"
                  disabled={!addArranjoId}
                  onClick={async () => {
                    if (!addArranjoId) return
                    await api.post(`/programacao/concertos/${detail.id}/programa`, {
                      arranjo_id: addArranjoId,
                    })
                    message.success('Adicionado')
                    setAddArranjoId(null)
                    void refreshDetail()
                  }}
                >
                  Adicionar
                </Button>
              </Space>
            )}
          </>
        )}
      </Drawer>

      <Modal
        open={execOpen}
        title="Registrar execução"
        onCancel={() => setExecOpen(false)}
        onOk={async () => {
          if (!detail || !execItem) return
          const values = await execForm.validateFields()
          await api.post(`/programacao/concertos/${detail.id}/programa/${execItem.id}/execucao`, {
            data_execucao: values.data_execucao.toISOString(),
            duracao_real_s: values.duracao_real_s ?? null,
            observacoes: values.observacoes || null,
          })
          message.success('Execução registrada')
          setExecOpen(false)
          void refreshDetail()
        }}
      >
        <Form form={execForm} layout="vertical">
          <Form.Item name="data_execucao" label="Data" rules={[{ required: true }]}>
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="duracao_real_s" label="Duração (segundos)">
            <InputNumber style={{ width: '100%' }} min={0} />
          </Form.Item>
          <Form.Item name="observacoes" label="Observações">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={distOpen}
        title="Distribuição de partituras"
        width={720}
        onCancel={() => setDistOpen(false)}
        onOk={async () => {
          if (!detail) return
          const atribuicoes = Object.entries(distChecked)
            .filter(([, docs]) => docs.length > 0)
            .map(([mid, documento_ids]) => ({
              musician_id: Number(mid),
              documento_ids,
            }))
          const { data } = await api.post(`/programacao/concertos/${detail.id}/distribuir`, {
            atribuicoes,
            enviar_email: enviarEmail,
          })
          message.success(
            `Distribuído (${data.atribuicoes} atribuições${data.emails_enviados ? `, ${data.emails_enviados} e-mails` : ''})`,
          )
          setDistOpen(false)
        }}
      >
        <Space style={{ marginBottom: 16 }}>
          <Switch checked={enviarEmail} onChange={setEnviarEmail} />
          <span>Enviar e-mail com link de acesso</span>
        </Space>
        {distSugestoes.length === 0 ? (
          <p>Nenhuma sugestão — verifique se o programa tem documentos.</p>
        ) : (
          distSugestoes.map((s) => (
            <div key={s.musician_id} style={{ marginBottom: 16, borderBottom: '1px solid #eee', paddingBottom: 8 }}>
              <Typography.Text strong>
                {s.musician_name}
                {s.musician_email ? ` (${s.musician_email})` : ''}
              </Typography.Text>
              <div style={{ marginTop: 8 }}>
                <Checkbox.Group
                  value={distChecked[s.musician_id] || []}
                  onChange={(vals) =>
                    setDistChecked((prev) => ({
                      ...prev,
                      [s.musician_id]: vals as number[],
                    }))
                  }
                  options={(s.documentos || []).map((d) => ({
                    value: d.id,
                    label: `${d.tipo_label || d.tipo}${d.instrumento_nome ? ` — ${d.instrumento_nome}` : ''}`,
                  }))}
                />
              </div>
            </div>
          ))
        )}
      </Modal>
    </div>
  )
}
