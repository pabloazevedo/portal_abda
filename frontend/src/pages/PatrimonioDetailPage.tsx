import {
  Button, Descriptions, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message,
} from 'antd'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import {
  PatrimonioDetalhesFields,
  buildPatrimonioPayload,
  fillPatrimonioForm,
} from './PatrimonioPage'

type Etiqueta = {
  id: number
  tipo: string
  valor: string
  ativo: boolean
  is_system?: boolean
}

type Emprestimo = {
  id: number
  musician_name?: string
  data_emprestimo?: string
  data_devolucao?: string | null
  observacoes?: string | null
  ativo?: boolean
}

const TIPOS = ['Instrumento', 'Movel', 'Eletronico', 'Partitura', 'Decoracao', 'Outros']
const STATUS = ['Disponivel', 'Emprestado', 'Manutencao', 'Baixa']
const ETIQUETA_TIPOS = [
  { value: 'rfid_hf', label: 'RFID HF' },
  { value: 'rfid_uhf', label: 'RFID UHF' },
  { value: 'data_matrix', label: 'Data Matrix' },
]

async function fetchBlobUrl(path: string): Promise<string> {
  const { data } = await api.get(path, { responseType: 'blob' })
  return URL.createObjectURL(data)
}

export default function PatrimonioDetailPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_patrimonio
  const [item, setItem] = useState<Record<string, unknown> | null>(null)
  const [loanOpen, setLoanOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [etiquetaOpen, setEtiquetaOpen] = useState(false)
  const [musicians, setMusicians] = useState<{ id: number; full_name: string }[]>([])
  const [musicianId, setMusicianId] = useState<number | null>(null)
  const [loanObs, setLoanObs] = useState('')
  const [emprestimos, setEmprestimos] = useState<Emprestimo[]>([])
  const [qrUrl, setQrUrl] = useState<string | null>(null)
  const [barcodeUrl, setBarcodeUrl] = useState<string | null>(null)
  const [form] = Form.useForm()
  const [etiquetaForm] = Form.useForm()
  const tipoWatch = Form.useWatch('tipo_item', form)

  const load = async () => {
    if (!id) return
    const { data } = await api.get(`/patrimonio/${id}`)
    setItem(data)
  }

  const loadEmprestimos = async () => {
    if (!id) return
    try {
      const { data } = await api.get(`/patrimonio/${id}/emprestimos`)
      setEmprestimos(data.items || [])
    } catch {
      setEmprestimos([])
    }
  }

  useEffect(() => {
    let cancelled = false
    let localQr: string | null = null
    let localBc: string | null = null

    const run = async () => {
      await load()
      await loadEmprestimos()
      if (!id) return
      try {
        const [qr, bc] = await Promise.all([
          fetchBlobUrl(`/patrimonio/${id}/etiqueta/qr.png`),
          fetchBlobUrl(`/patrimonio/${id}/etiqueta/barcode.png`),
        ])
        if (cancelled) {
          URL.revokeObjectURL(qr)
          URL.revokeObjectURL(bc)
          return
        }
        localQr = qr
        localBc = bc
        setQrUrl(qr)
        setBarcodeUrl(bc)
      } catch {
        /* images may fail if codes missing */
      }
    }
    void run()
    return () => {
      cancelled = true
      if (localQr) URL.revokeObjectURL(localQr)
      if (localBc) URL.revokeObjectURL(localBc)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (!item) return null
  const emp = item.emprestimo_ativo as { musician_name?: string } | null
  const detalhes = (item.detalhes as Record<string, unknown>) || {}
  const etiquetas = (item.etiquetas as Etiqueta[]) || []

  const openEdit = () => {
    fillPatrimonioForm(form, item as Parameters<typeof fillPatrimonioForm>[1])
    setEditOpen(true)
  }

  const onSaveEdit = async () => {
    const values = await form.validateFields()
    const payload = buildPatrimonioPayload(values)
    await api.put(`/patrimonio/${id}`, payload)
    message.success('Item atualizado')
    setEditOpen(false)
    void load()
  }

  const printEtiqueta = async () => {
    const { data } = await api.get(`/patrimonio/${id}/etiqueta/print`)
    const [qrBlob, bcBlob] = await Promise.all([
      api.get(`/patrimonio/${id}/etiqueta/qr.png`, { responseType: 'blob' }),
      api.get(`/patrimonio/${id}/etiqueta/barcode.png`, { responseType: 'blob' }),
    ])
    const qr = URL.createObjectURL(qrBlob.data)
    const bc = URL.createObjectURL(bcBlob.data)
    const w = window.open('', '_blank')
    if (!w) {
      message.error('Permita pop-ups para imprimir')
      return
    }
    const ident = data.item?.identificador_interno || item.identificador_interno
    w.document.write(`<!DOCTYPE html><html><head><title>Etiqueta ${ident}</title>
      <style>
        body{font-family:sans-serif;padding:16px;text-align:center}
        img{max-width:240px;margin:8px}
        h2{margin:0 0 8px}
        @media print{button{display:none}}
      </style></head><body>
      <h2>${ident}</h2>
      <div>${data.item?.tipo_label || ''} · ${data.item?.fabricante || ''} ${data.item?.modelo || ''}</div>
      <div><img src="${qr}" alt="QR"/><img src="${bc}" alt="Barcode"/></div>
      <p style="font-size:12px;color:#666">${data.item?.barcode_value || ''}</p>
      <button onclick="window.print()">Imprimir</button>
      </body></html>`)
    w.document.close()
    setTimeout(() => { w.print() }, 400)
  }

  return (
    <div>
      <Link to="/patrimonio">← Patrimônio</Link>
      <Typography.Title level={3}>{String(item.identificador_interno)}</Typography.Title>
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="Tipo">{String(item.tipo_label)}</Descriptions.Item>
        <Descriptions.Item label="Status"><Tag>{String(item.status)}</Tag></Descriptions.Item>
        <Descriptions.Item label="Fabricante">{String(item.fabricante || '—')}</Descriptions.Item>
        <Descriptions.Item label="Modelo">{String(item.modelo || '—')}</Descriptions.Item>
        <Descriptions.Item label="Ano de compra">{String(item.ano_compra ?? '—')}</Descriptions.Item>
        <Descriptions.Item label="Valor">
          {item.valor_mercado != null ? Number(item.valor_mercado).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : '—'}
        </Descriptions.Item>
        <Descriptions.Item label="Observações">{String(item.observacoes || '—')}</Descriptions.Item>
        <Descriptions.Item label="Empréstimo">{emp?.musician_name || '—'}</Descriptions.Item>
        {Object.entries(detalhes).map(([k, v]) => (
          <Descriptions.Item key={k} label={k}>{String(v ?? '—')}</Descriptions.Item>
        ))}
      </Descriptions>

      {canEdit && (
        <Space wrap style={{ marginTop: 16 }}>
          <Button onClick={openEdit}>Editar</Button>
          {!emp ? (
            <Button
              type="primary"
              onClick={async () => {
                const { data } = await api.get('/musicians', { params: { page_size: 100, status: 'active' } })
                setMusicians(data.items)
                setMusicianId(null)
                setLoanObs('')
                setLoanOpen(true)
              }}
            >
              Emprestar
            </Button>
          ) : (
            <Button
              onClick={async () => {
                await api.post(`/patrimonio/${id}/devolver`)
                message.success('Devolvido')
                void load()
                void loadEmprestimos()
              }}
            >
              Devolver
            </Button>
          )}
          <Button onClick={() => void printEtiqueta()}>Imprimir etiqueta</Button>
        </Space>
      )}

      <Typography.Title level={5} style={{ marginTop: 32 }}>Etiquetas</Typography.Title>
      <Space align="start" size="large" wrap style={{ marginBottom: 16 }}>
        {qrUrl && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#888' }}>QR</div>
            <img src={qrUrl} alt="QR" style={{ maxWidth: 160 }} />
          </div>
        )}
        {barcodeUrl && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ marginBottom: 4, fontSize: 12, color: '#888' }}>Código de barras</div>
            <img src={barcodeUrl} alt="Barcode" style={{ maxWidth: 220 }} />
          </div>
        )}
      </Space>
      <Table
        size="small"
        rowKey="id"
        pagination={false}
        dataSource={etiquetas}
        columns={[
          { title: 'Tipo', dataIndex: 'tipo', render: (t: string) => <Tag>{t}</Tag> },
          { title: 'Valor', dataIndex: 'valor', render: (v: string) => <code>{v}</code> },
          {
            title: 'Status',
            dataIndex: 'ativo',
            render: (a: boolean) => (a ? <Tag color="green">Ativa</Tag> : <Tag>Inativa</Tag>),
          },
          {
            title: 'Ações',
            render: (_, e: Etiqueta) =>
              canEdit && e.ativo && !e.is_system ? (
                <Popconfirm
                  title="Desativar esta etiqueta?"
                  onConfirm={async () => {
                    await api.post(`/patrimonio/${id}/etiqueta/${e.id}/desativar`)
                    message.success('Etiqueta desativada')
                    void load()
                  }}
                >
                  <Button type="link" danger size="small">Desativar</Button>
                </Popconfirm>
              ) : null,
          },
        ]}
      />
      {canEdit && (
        <Button style={{ marginTop: 8 }} onClick={() => { etiquetaForm.resetFields(); setEtiquetaOpen(true) }}>
          Adicionar etiqueta
        </Button>
      )}

      <Typography.Title level={5} style={{ marginTop: 32 }}>Histórico de empréstimos</Typography.Title>
      <Table
        size="small"
        rowKey="id"
        pagination={false}
        dataSource={emprestimos}
        locale={{ emptyText: 'Nenhum empréstimo registrado.' }}
        columns={[
          { title: 'Membro', dataIndex: 'musician_name' },
          { title: 'Empréstimo', dataIndex: 'data_emprestimo', render: (v) => v ? new Date(v).toLocaleString('pt-BR') : '—' },
          { title: 'Devolução', dataIndex: 'data_devolucao', render: (v) => v ? new Date(v).toLocaleString('pt-BR') : '—' },
          { title: 'Obs.', dataIndex: 'observacoes' },
          {
            title: 'Status',
            dataIndex: 'ativo',
            render: (a) => (a ? <Tag color="orange">Ativo</Tag> : <Tag>Encerrado</Tag>),
          },
        ]}
      />

      <Modal
        open={loanOpen}
        title="Emprestar item"
        onCancel={() => setLoanOpen(false)}
        onOk={async () => {
          if (!musicianId) {
            message.warning('Selecione o membro')
            return
          }
          await api.post(`/patrimonio/${id}/emprestar`, {
            musician_id: musicianId,
            observacoes: loanObs || null,
          })
          message.success('Emprestado')
          setLoanOpen(false)
          void load()
          void loadEmprestimos()
        }}
      >
        <Select
          style={{ width: '100%', marginBottom: 12 }}
          showSearch
          optionFilterProp="label"
          placeholder="Selecione o membro"
          options={musicians.map((m) => ({ value: m.id, label: m.full_name }))}
          onChange={setMusicianId}
          value={musicianId}
        />
        <Input.TextArea
          rows={3}
          placeholder="Observações (opcional)"
          value={loanObs}
          onChange={(e) => setLoanObs(e.target.value)}
        />
      </Modal>

      <Modal
        open={editOpen}
        title="Editar patrimônio"
        onCancel={() => setEditOpen(false)}
        onOk={() => void onSaveEdit()}
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="tipo_item" label="Tipo" rules={[{ required: true }]}>
            <Select options={TIPOS.map((v) => ({ value: v, label: v }))} disabled />
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

      <Modal
        open={etiquetaOpen}
        title="Adicionar etiqueta"
        onCancel={() => setEtiquetaOpen(false)}
        onOk={async () => {
          const values = await etiquetaForm.validateFields()
          await api.post(`/patrimonio/${id}/etiqueta`, values)
          message.success('Etiqueta adicionada')
          setEtiquetaOpen(false)
          void load()
        }}
      >
        <Form form={etiquetaForm} layout="vertical">
          <Form.Item name="tipo" label="Tipo" rules={[{ required: true }]} initialValue="rfid_hf">
            <Select options={ETIQUETA_TIPOS} />
          </Form.Item>
          <Form.Item name="valor" label="Valor" rules={[{ required: true }]}>
            <Input placeholder="Código / UID da etiqueta" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
