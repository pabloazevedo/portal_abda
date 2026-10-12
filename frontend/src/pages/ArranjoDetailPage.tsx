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
  Switch,
  Table,
  Typography,
  Upload,
  message,
} from 'antd'
import { InboxOutlined, PlusOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const COPYRIGHT_OPTS = [
  { value: 'dominio_publico', label: 'Domínio público' },
  { value: 'licenciado', label: 'Licenciado' },
  { value: 'pendente', label: 'Pendente' },
]

const DOC_TIPOS = [
  { value: 'grade', label: 'Grade' },
  { value: 'coral', label: 'Coral' },
  { value: 'instrumento', label: 'Instrumento' },
  { value: 'acompanhamento', label: 'Acompanhamento' },
]

type Documento = {
  id: number
  tipo: string
  tipo_label?: string
  instrumento_nome?: string
  voz_tipo?: string
  arquivo_caminho?: string
  tamanho_bytes?: number
}

type Arranjo = {
  id: number
  obra_id?: number
  obra_titulo?: string
  titulo_arranjo?: string
  arranjador_nome?: string
  arranjador_label?: string
  instrumentacao?: string
  duracao_segundos?: number
  duracao_label?: string
  editora?: string
  copyright_status?: string
  numero_licenca?: string
  ativo?: boolean
  documentos?: Documento[]
}

async function openDocumentoBlob(docId: number) {
  const { data } = await api.get(`/acervo/documentos/${docId}/view`, { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  window.open(url, '_blank')
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export default function ArranjoDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const { user } = useAuth()
  const canEdit = user?.permissions?.can_manage_acervo
  const [arranjo, setArranjo] = useState<Arranjo | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [form] = Form.useForm()
  const [uploadForm] = Form.useForm()
  const [fileList, setFileList] = useState<{ originFileObj?: File; name: string; uid: string }[]>([])

  const load = useCallback(async () => {
    if (!id) return
    const { data } = await api.get(`/acervo/arranjos/${id}`)
    setArranjo(data)
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  if (!arranjo) return null

  return (
    <div>
      <Link to="/acervo/arranjos">← Arranjos</Link>
      <Typography.Title level={3} style={{ marginTop: 8 }}>
        {arranjo.titulo_arranjo || `Arranjo #${arranjo.id}`}
      </Typography.Title>

      <Descriptions bordered column={1} size="small" style={{ maxWidth: 720 }}>
        <Descriptions.Item label="Obra">
          {arranjo.obra_id ? (
            <Link to={`/acervo/obras/${arranjo.obra_id}`}>{arranjo.obra_titulo || '—'}</Link>
          ) : (
            arranjo.obra_titulo || '—'
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Arranjador">
          {arranjo.arranjador_label || arranjo.arranjador_nome || '—'}
        </Descriptions.Item>
        <Descriptions.Item label="Instrumentação">{arranjo.instrumentacao || '—'}</Descriptions.Item>
        <Descriptions.Item label="Duração">{arranjo.duracao_label || arranjo.duracao_segundos || '—'}</Descriptions.Item>
        <Descriptions.Item label="Editora">{arranjo.editora || '—'}</Descriptions.Item>
        <Descriptions.Item label="Copyright">{arranjo.copyright_status || '—'}</Descriptions.Item>
        <Descriptions.Item label="Licença">{arranjo.numero_licenca || '—'}</Descriptions.Item>
        <Descriptions.Item label="Ativo">{arranjo.ativo === false ? 'Não' : 'Sim'}</Descriptions.Item>
      </Descriptions>

      {canEdit && (
        <Space style={{ marginTop: 16 }}>
          <Button
            onClick={() => {
              form.setFieldsValue(arranjo)
              setEditOpen(true)
            }}
          >
            Editar
          </Button>
          <Popconfirm
            title="Excluir este arranjo?"
            onConfirm={async () => {
              await api.delete(`/acervo/arranjos/${arranjo.id}`)
              message.success('Arranjo excluído')
              nav('/acervo/arranjos')
            }}
          >
            <Button danger>Excluir</Button>
          </Popconfirm>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              uploadForm.resetFields()
              uploadForm.setFieldsValue({ tipo: 'grade' })
              setFileList([])
              setUploadOpen(true)
            }}
          >
            Upload documento
          </Button>
        </Space>
      )}

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        Documentos
      </Typography.Title>
      <Table
        rowKey="id"
        dataSource={arranjo.documentos || []}
        pagination={false}
        columns={[
          {
            title: 'Tipo',
            render: (_, r) => r.tipo_label || r.tipo,
          },
          {
            title: 'Nome / instrumento',
            render: (_, r) => r.instrumento_nome || r.voz_tipo || r.arquivo_caminho?.split('/').pop() || '—',
          },
          {
            title: 'Tamanho',
            dataIndex: 'tamanho_bytes',
            width: 100,
            render: (v) => (v != null ? `${Math.round(Number(v) / 1024)} KB` : '—'),
          },
          {
            title: 'Ações',
            width: 180,
            render: (_, r) => (
              <Space>
                <Button type="link" size="small" onClick={() => void openDocumentoBlob(r.id)}>
                  Abrir
                </Button>
                {canEdit && (
                  <Popconfirm
                    title="Excluir documento?"
                    onConfirm={async () => {
                      await api.delete(`/acervo/documentos/${r.id}`)
                      message.success('Documento excluído')
                      void load()
                    }}
                  >
                    <Button type="link" danger size="small">
                      Excluir
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        open={editOpen}
        title="Editar arranjo"
        onCancel={() => setEditOpen(false)}
        onOk={async () => {
          const values = await form.validateFields()
          await api.put(`/acervo/arranjos/${arranjo.id}`, values)
          message.success('Arranjo atualizado')
          setEditOpen(false)
          void load()
        }}
        width={560}
      >
        <Form form={form} layout="vertical">
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
          <Form.Item name="numero_licenca" label="Nº licença">
            <Input />
          </Form.Item>
          <Form.Item name="duracao_segundos" label="Duração (s)">
            <InputNumber style={{ width: '100%' }} min={0} />
          </Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={uploadOpen}
        title="Upload de documento"
        onCancel={() => setUploadOpen(false)}
        onOk={async () => {
          const values = await uploadForm.validateFields()
          const file = fileList[0]?.originFileObj
          if (!file) {
            message.error('Selecione um arquivo')
            return
          }
          const fd = new FormData()
          fd.append('arquivo', file)
          fd.append('tipo', values.tipo)
          if (values.instrumento_nome) fd.append('instrumento_nome', values.instrumento_nome)
          if (values.voz_tipo) fd.append('voz_tipo', values.voz_tipo)
          await api.post(`/acervo/arranjos/${arranjo.id}/upload`, fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          message.success('Documento enviado')
          setUploadOpen(false)
          void load()
        }}
      >
        <Form form={uploadForm} layout="vertical">
          <Form.Item name="tipo" label="Tipo" rules={[{ required: true }]}>
            <Select options={DOC_TIPOS} />
          </Form.Item>
          <Form.Item name="instrumento_nome" label="Instrumento">
            <Input placeholder="Ex.: Violino I" />
          </Form.Item>
          <Form.Item name="voz_tipo" label="Voz / stab">
            <Input placeholder="Ex.: soprano" />
          </Form.Item>
          <Upload.Dragger
            multiple={false}
            maxCount={1}
            beforeUpload={() => false}
            fileList={fileList as never}
            onChange={({ fileList: fl }) => setFileList(fl as typeof fileList)}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">Clique ou arraste o arquivo</p>
          </Upload.Dragger>
        </Form>
      </Modal>
    </div>
  )
}
