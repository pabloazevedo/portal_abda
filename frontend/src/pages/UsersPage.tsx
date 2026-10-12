import { Button, Form, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tag, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type UserRow = {
  id: number
  username: string
  email: string
  role: string
  is_active: boolean
}

const ROLES = [
  { value: 'admin', label: 'Administrador' },
  { value: 'maestro', label: 'Maestro' },
  { value: 'arquivista', label: 'Arquivista' },
  { value: 'secretaria', label: 'Secretaria' },
]

export default function UsersPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [items, setItems] = useState<UserRow[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<UserRow | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/users')
      setItems(data.items)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const onSave = async () => {
    const values = await form.validateFields()
    if (editing) {
      const payload = { ...values }
      if (!payload.password) delete payload.password
      await api.put(`/users/${editing.id}`, payload)
      message.success('Usuário atualizado')
    } else {
      await api.post('/users', values)
      message.success('Usuário criado')
    }
    setOpen(false)
    void load()
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>{t('nav_users')}</h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditing(null)
            form.resetFields()
            form.setFieldsValue({ role: 'secretaria', is_active: true })
            setOpen(true)
          }}
        >
          {t('nav_add_user')}
        </Button>
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={[
          {
            title: t('label_username'),
            render: (_, r) => (
              <Space>
                <span>{r.username}</span>
                {user?.id === r.id && <Tag color="blue">você</Tag>}
              </Space>
            ),
          },
          { title: t('label_email'), dataIndex: 'email' },
          { title: t('label_role'), dataIndex: 'role', render: (r) => <Tag>{r}</Tag> },
          {
            title: t('label_status'),
            dataIndex: 'is_active',
            render: (v, r) => (
              <Switch
                checked={v}
                checkedChildren="Ativo"
                unCheckedChildren="Inativo"
                disabled={user?.id === r.id}
                onChange={async () => {
                  try {
                    await api.post(`/users/${r.id}/toggle-status`)
                    message.success('Status alterado')
                    void load()
                  } catch (e: unknown) {
                    const err = e as { response?: { data?: { detail?: string } } }
                    message.error(err.response?.data?.detail || 'Não foi possível alterar')
                  }
                }}
              />
            ),
          },
          {
            title: t('label_actions'),
            render: (_, r) => (
              <Space>
                <Button
                  type="link"
                  onClick={() => {
                    setEditing(r)
                    form.setFieldsValue({ ...r, password: undefined })
                    setOpen(true)
                  }}
                >
                  {t('btn_edit', 'Editar')}
                </Button>
                <Popconfirm
                  title="Excluir este usuário?"
                  okType="danger"
                  disabled={user?.id === r.id}
                  onConfirm={async () => {
                    try {
                      await api.delete(`/users/${r.id}`)
                      message.success('Usuário excluído')
                      void load()
                    } catch (e: unknown) {
                      const err = e as { response?: { data?: { detail?: string } } }
                      message.error(err.response?.data?.detail || 'Não foi possível excluir')
                    }
                  }}
                >
                  <Button type="link" danger disabled={user?.id === r.id}>
                    {t('btn_delete', 'Excluir')}
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        open={open}
        title={editing ? 'Editar usuário' : 'Novo usuário'}
        onCancel={() => setOpen(false)}
        onOk={() => void onSave()}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="username" label={t('label_username')} rules={[{ required: true, min: 3 }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label={t('label_email')} rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label={t('label_password')}
            rules={editing ? [] : [{ required: true, min: 6 }]}
          >
            <Input.Password placeholder={editing ? t('password_leave_blank') : undefined} />
          </Form.Item>
          <Form.Item name="role" label={t('label_role')} rules={[{ required: true }]}>
            <Select options={ROLES} />
          </Form.Item>
          {editing && (
            <Form.Item name="is_active" label={t('label_status')} valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
