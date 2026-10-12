import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api/client'

export default function ForgotPasswordPage() {
  const { t } = useTranslation()
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  const onFinish = async (values: { email: string }) => {
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', values)
      setSent(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0f2744', padding: 24 }}>
      <Card style={{ width: 400, maxWidth: '100%' }}>
        <Typography.Title level={3}>{t('forgot_title', 'Recuperar senha')}</Typography.Title>
        {sent ? (
          <Alert type="success" showIcon message={t('forgot_sent', 'Se o e-mail existir, enviaremos instruções.')} />
        ) : (
          <Form layout="vertical" onFinish={onFinish}>
            <Form.Item name="email" label={t('label_email')} rules={[{ required: true, type: 'email' }]}>
              <Input />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              {t('forgot_submit', 'Enviar link')}
            </Button>
          </Form>
        )}
        <div style={{ marginTop: 16 }}>
          <Link to="/login">Login</Link>
        </div>
      </Card>
    </div>
  )
}
