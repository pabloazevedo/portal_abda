import { Alert, Button, Card, Form, Input, Typography, message } from 'antd'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'

export default function ResetPasswordPage() {
  const { token } = useParams()
  const { t } = useTranslation()
  const nav = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onFinish = async (values: { password: string; confirm_password: string }) => {
    setLoading(true)
    setError(null)
    try {
      await api.post('/auth/reset-password', { token, ...values })
      message.success(t('reset_success_title', 'Senha atualizada'))
      nav('/login')
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(String(msg || 'Token inválido'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0f2744', padding: 24 }}>
      <Card style={{ width: 400, maxWidth: '100%' }}>
        <Typography.Title level={3}>{t('reset_title', 'Nova senha')}</Typography.Title>
        {error && <Alert type="error" message={error} style={{ marginBottom: 12 }} showIcon />}
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="password" label={t('reset_label_new', 'Nova senha')} rules={[{ required: true, min: 8 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label={t('reset_label_confirm', 'Confirmar')}
            dependencies={['password']}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) return Promise.resolve()
                  return Promise.reject(new Error(t('error_password_mismatch')))
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            {t('reset_submit', 'Salvar')}
          </Button>
        </Form>
        <div style={{ marginTop: 16 }}>
          <Link to="/login">Login</Link>
        </div>
      </Card>
    </div>
  )
}
