import {
  Button,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
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

type Arranjo = {
  id: number
  titulo_arranjo?: string
  arranjador_label?: string
  instrumentacao?: string
  copyright_status?: string
  duracao_label?: string
}

type Obra = {
  id: number
  titulo: string
  titulo_original?: string
  compositor_label?: string
  compositor_nome?: string
  genero?: string
  tonalidade?: string
  ano_composicao?: number
  observacoes?: string
  arranjos?: Arranjo[]
}

export default function ObraDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_acervo
  const [obra, setObra] = useState<Obra | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [arranjoOpen, setArranjoOpen] = useState(false)
  const [form] = Form.useForm()
  const [arranjoForm] = Form.useForm()

  const load = useCallback(async () => {
    if (!id) return
    const { data } = await api.get(`/acervo/obras/${id}`)
    setObra(data)
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  if (!obra) return null

  return (
    <div>
      <Link to="/acervo/obras">← Acervo</Link>
      <Typography.Title level={3} style={{ marginTop: 8 }}>
        {obra.titulo}
      </Typography.Title>

      <Descriptions bordered column={1} size="small" style={{ maxWidth: 720 }}>
        <Descriptions.Item label="Título original">{obra.titulo_original || '—'}</Descriptions.Item>
        <Descriptions.Item label="Compositor">{obra.compositor_label || obra.compositor_nome || '—'}</Descriptions.Item>
        <Descriptions.Item label="Gênero">{obra.genero || '—'}</Descriptions.Item>
        <Descriptions.Item label="Tonalidade">{obra.tonalidade || '—'}</Descriptions.Item>
        <Descriptions.Item label="Ano">{obra.ano_composicao ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="Observações">{obra.observacoes || '—'}</Descriptions.Item>
      </Descriptions>

      {canEdit && (
        <Space style={{ marginTop: 16 }}>
          <Button
            onClick={() => {
              form.setFieldsValue(obra)
              setEditOpen(true)
            }}
          >
            Editar
          </Button>
          <Popconfirm
            title="Excluir esta obra?"
            onConfirm={async () => {
              await api.delete(`/acervo/obras/${obra.id}`)
              message.success('Obra excluída')
              nav('/acervo/obras')
            }}
          >
            <Button danger>Excluir</Button>
          </Popconfirm>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              arranjoForm.resetFields()
              arranjoForm.setFieldsValue({
                obra_id: obra.id,
                copyright_status: 'pendente',
              })
              setArranjoOpen(true)
            }}
          >
            Novo arranjo
          </Button>
        </Space>
      )}

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        Arranjos
      </Typography.Title>
      <Table
        rowKey="id"
        dataSource={obra.arranjos || []}
        pagination={false}
        columns={[
          {
            title: 'Título',
            render: (_, r) => (
              <Link to={`/acervo/arranjos/${r.id}`}>{r.titulo_arranjo || `Arranjo #${r.id}`}</Link>
            ),
          },
          { title: 'Arranjador', dataIndex: 'arranjador_label' },
          { title: 'Instrumentação', dataIndex: 'instrumentacao', ellipsis: true },
          { title: 'Duração', dataIndex: 'duracao_label', width: 100 },
          { title: 'Copyright', dataIndex: 'copyright_status', width: 120 },
        ]}
      />

      <Modal
        open={editOpen}
        title="Editar obra"
        onCancel={() => setEditOpen(false)}
        onOk={async () => {
          const values = await form.validateFields()
          await api.put(`/acervo/obras/${obra.id}`, values)
          message.success('Obra atualizada')
          setEditOpen(false)
          void load()
        }}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="titulo" label="Título" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="titulo_original" label="Título original">
            <Input />
          </Form.Item>
          <Form.Item name="compositor_nome" label="Compositor">
            <Input />
          </Form.Item>
          <Form.Item name="genero" label="Gênero">
            <Select options={GENEROS} />
          </Form.Item>
          <Form.Item name="tonalidade" label="Tonalidade">
            <Input />
          </Form.Item>
          <Form.Item name="ano_composicao" label="Ano">
            <InputNumber style={{ width: '100%' }} min={1000} max={2100} />
          </Form.Item>
          <Form.Item name="observacoes" label="Observações">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={arranjoOpen}
        title="Novo arranjo"
        onCancel={() => setArranjoOpen(false)}
        onOk={async () => {
          const values = await arranjoForm.validateFields()
          const { data } = await api.post('/acervo/arranjos', values)
          message.success('Arranjo criado')
          setArranjoOpen(false)
          nav(`/acervo/arranjos/${data.id}`)
        }}
        width={560}
      >
        <Form form={arranjoForm} layout="vertical">
          <Form.Item name="obra_id" hidden>
            <InputNumber />
          </Form.Item>
          <Form.Item name="titulo_arranjo" label="Título">
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
          <Form.Item name="duracao_segundos" label="Duração (s)">
            <InputNumber style={{ width: '100%' }} min={0} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
