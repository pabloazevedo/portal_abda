import { Button, Form, Input, List, Modal, Switch, Tag, Typography, message, DatePicker } from 'antd'
import { EditOutlined, PlusOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type Note = {
  id: number
  version: string
  title: string
  body: string
  released_at?: string
  is_current?: boolean
}

function renderBody(body: string) {
  const lines = (body || '').split('\n')
  return (
    <div style={{ whiteSpace: 'pre-wrap' }}>
      {lines.map((line, i) => {
        if (line.startsWith('### ')) {
          return (
            <Typography.Title key={i} level={5} style={{ marginTop: 12, marginBottom: 4 }}>
              {line.slice(4)}
            </Typography.Title>
          )
        }
        if (line.startsWith('## ')) {
          return (
            <Typography.Title key={i} level={4} style={{ marginTop: 12, marginBottom: 4 }}>
              {line.slice(3)}
            </Typography.Title>
          )
        }
        if (line.startsWith('# ')) {
          return (
            <Typography.Title key={i} level={3} style={{ marginTop: 12, marginBottom: 4 }}>
              {line.slice(2)}
            </Typography.Title>
          )
        }
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return (
            <div key={i} style={{ paddingLeft: 12 }}>
              • {line.slice(2)}
            </div>
          )
        }
        if (/^\*\*.+\*\*$/.test(line.trim())) {
          return (
            <div key={i}>
              <strong>{line.trim().slice(2, -2)}</strong>
            </div>
          )
        }
        return (
          <div key={i}>
            {line || '\u00A0'}
          </div>
        )
      })}
    </div>
  )
}

export default function ReleasesPage() {
  const { user } = useAuth()
  const isAdmin = user?.permissions?.is_admin
  const [items, setItems] = useState<Note[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Note | null>(null)
  const [form] = Form.useForm()

  const load = () => api.get('/release-notes').then((r) => setItems(r.data.items || []))

  useEffect(() => {
    void load()
  }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ released_at: dayjs(), is_current: false })
    setOpen(true)
  }

  const openEdit = (n: Note) => {
    setEditing(n)
    form.setFieldsValue({
      ...n,
      released_at: n.released_at ? dayjs(n.released_at) : null,
    })
    setOpen(true)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Histórico de versões
        </Typography.Title>
        {isAdmin && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Nova versão
          </Button>
        )}
      </div>
      <List
        style={{ marginTop: 16 }}
        itemLayout="vertical"
        dataSource={items}
        locale={{ emptyText: 'Nenhuma release note cadastrada.' }}
        renderItem={(n) => (
          <List.Item
            actions={
              isAdmin
                ? [
                    <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => openEdit(n)}>
                      Editar
                    </Button>,
                    <Button
                      key="del"
                      danger
                      type="link"
                      onClick={async () => {
                        await api.delete(`/release-notes/${n.id}`)
                        message.success('Removida')
                        void load()
                      }}
                    >
                      Excluir
                    </Button>,
                  ]
                : undefined
            }
          >
            <List.Item.Meta
              title={
                <span>
                  v{n.version} — {n.title} {n.is_current && <Tag color="blue">atual</Tag>}
                </span>
              }
              description={n.released_at}
            />
            {renderBody(n.body)}
          </List.Item>
        )}
      />
      <Modal
        open={open}
        title={editing ? 'Editar release' : 'Nova release'}
        onCancel={() => setOpen(false)}
        onOk={async () => {
          const values = await form.validateFields()
          const payload = {
            ...values,
            released_at: values.released_at?.format('YYYY-MM-DD'),
          }
          if (editing) {
            await api.put(`/release-notes/${editing.id}`, payload)
            message.success('Atualizada')
          } else {
            await api.post('/release-notes', payload)
            message.success('Criada')
          }
          setOpen(false)
          void load()
        }}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="version" label="Versão" rules={[{ required: true }]}>
            <Input placeholder="1.2.0" />
          </Form.Item>
          <Form.Item name="title" label="Título">
            <Input />
          </Form.Item>
          <Form.Item name="body" label="Notas">
            <Input.TextArea rows={8} placeholder="Suporta # ## ### e listas com - " />
          </Form.Item>
          <Form.Item name="released_at" label="Data">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_current" label="Versão atual" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
