import {
  Avatar, Button, Descriptions, Form, Modal, Popconfirm, Space, Tag, Typography, Upload, message,
} from 'antd'
import { UploadOutlined, UserOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import dayjs from 'dayjs'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { MusicianFormFields, buildMusicianPayload } from './MusiciansPage'

type InstrumentOpt = { id: number; nome: string; categoria?: string }

function photoSrc(photo?: string | null) {
  if (!photo) return undefined
  if (String(photo).startsWith('/')) return String(photo)
  return `/uploads/${photo}`
}

export default function MusicianDetailPage() {
  const { id } = useParams()
  const { t } = useTranslation()
  const { user } = useAuth()
  const nav = useNavigate()
  const [m, setM] = useState<Record<string, unknown> | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [instruments, setInstruments] = useState<InstrumentOpt[]>([])
  const [form] = Form.useForm()
  const canEdit = user?.permissions?.can_manage_members

  const load = async () => {
    if (!id) return
    const { data } = await api.get(`/musicians/${id}`)
    setM(data)
  }

  useEffect(() => { void load() }, [id])

  useEffect(() => {
    api.get('/musicians/instruments').then((r) => setInstruments(r.data || [])).catch(() => undefined)
  }, [])

  if (!m) return null

  const openEdit = () => {
    const roles = (m.roles as { role_type: string; maestro_order?: number | null; voice_type?: string | null }[]) || []
    const maestroRole = roles.find((r) => r.role_type === 'maestro')
    const cantorRole = roles.find((r) => r.role_type === 'cantor')
    form.setFieldsValue({
      ...m,
      birth_date: m.birth_date ? dayjs(String(m.birth_date)) : null,
      roles: roles.map((r) => r.role_type),
      instrumento_ids: ((m.instruments as { id: number }[]) || []).map((i) => i.id),
      maestro_order: maestroRole?.maestro_order ?? undefined,
      voice_type: cantorRole?.voice_type ?? undefined,
      app_access: !!m.has_app_access,
      app_password: undefined,
    })
    setEditOpen(true)
  }

  const onSave = async () => {
    const values = await form.validateFields()
    const payload = buildMusicianPayload(values, true)
    await api.put(`/musicians/${id}`, payload)
    message.success('Membro atualizado')
    setEditOpen(false)
    void load()
  }

  const onUploadPhoto = async (file: File) => {
    const formData = new FormData()
    formData.append('photo', file)
    const { data } = await api.post(`/musicians/${id}/photo`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    setM(data)
    message.success('Foto atualizada')
    return false
  }

  const src = photoSrc(m.photo as string | undefined)

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/musicians">← {t('musicians_list')}</Link>
      </Space>

      <Space align="start" size="large" style={{ marginBottom: 24 }}>
        <Avatar size={96} src={src} icon={<UserOutlined />} />
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>{String(m.full_name)}</Typography.Title>
          {m.apelido ? (
            <Typography.Text type="secondary"><em>{String(m.apelido)}</em></Typography.Text>
          ) : null}
          {canEdit && (
            <div style={{ marginTop: 8 }}>
              <Upload
                accept="image/*"
                showUploadList={false}
                beforeUpload={(file) => {
                  void onUploadPhoto(file)
                  return false
                }}
              >
                <Button icon={<UploadOutlined />} size="small">Enviar foto</Button>
              </Upload>
            </div>
          )}
        </div>
      </Space>

      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label={t('label_email')}>{String(m.email)}</Descriptions.Item>
        <Descriptions.Item label={t('label_celular')}>{String(m.celular || '')}</Descriptions.Item>
        <Descriptions.Item label="Telefone">{String(m.telefone || '—')}</Descriptions.Item>
        <Descriptions.Item label="Apelido">{String(m.apelido || '—')}</Descriptions.Item>
        <Descriptions.Item label={t('label_birth_date')}>{String(m.birth_date || '')}</Descriptions.Item>
        <Descriptions.Item label={t('label_roles')}>
          {(m.role_labels as string[] || []).map((l) => <Tag key={l}>{l}</Tag>)}
        </Descriptions.Item>
        <Descriptions.Item label={t('label_instruments')}>
          {(m.instrument_names as string[] || []).join(', ') || '—'}
        </Descriptions.Item>
        <Descriptions.Item label={t('label_status')}>
          {m.is_active ? <Tag color="green">{t('status_active')}</Tag> : <Tag>{t('status_inactive')}</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="Acesso ao App">
          {m.has_app_access ? <Tag color="blue">Sim</Tag> : <Tag>Não</Tag>}
          {m.app_username ? ` · ${String(m.app_username)}` : ''}
        </Descriptions.Item>
      </Descriptions>

      {canEdit && (
        <Space wrap style={{ marginTop: 16 }}>
          <Button type="primary" onClick={openEdit}>{t('btn_edit', 'Editar')}</Button>
          <Button
            onClick={async () => {
              await api.post(`/musicians/${id}/toggle-status`)
              message.success('Status alterado')
              void load()
            }}
          >
            Alternar status
          </Button>
          {!!m.has_app_access && (
            <Popconfirm
              title="Remover o acesso ao App deste membro?"
              onConfirm={async () => {
                await api.post(`/musicians/${id}/revoke-app`)
                message.success('Acesso ao app revogado')
                void load()
              }}
            >
              <Button>Revogar app access</Button>
            </Popconfirm>
          )}
          <Popconfirm
            title="Excluir este membro?"
            okType="danger"
            onConfirm={async () => {
              await api.delete(`/musicians/${id}`)
              message.success('Removido')
              nav('/musicians')
            }}
          >
            <Button danger>{t('btn_delete', 'Excluir')}</Button>
          </Popconfirm>
        </Space>
      )}

      <Modal
        title={t('musicians_edit')}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={() => void onSave()}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <MusicianFormFields form={form} editing instruments={instruments} />
        </Form>
      </Modal>
    </div>
  )
}
