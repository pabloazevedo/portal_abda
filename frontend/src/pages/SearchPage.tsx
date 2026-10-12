import { Card, Col, Empty, List, Row, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'

export default function SearchPage() {
  const [params] = useSearchParams()
  const q = params.get('q') || ''
  const [data, setData] = useState<{
    musicians: { id: number; name: string; email: string; url: string }[]
    patrimonio: { id: string; identificador: string; tipo: string; url: string }[]
    obras: { id: number; titulo: string; compositor: string; url: string }[]
  } | null>(null)

  useEffect(() => {
    if (q.length < 2) {
      setData({ musicians: [], patrimonio: [], obras: [] })
      return
    }
    api.get('/search', { params: { q } }).then((r) => setData(r.data))
  }, [q])

  if (!data) return null
  const empty = !data.musicians.length && !data.patrimonio.length && !data.obras.length

  return (
    <div>
      <Typography.Title level={3}>Busca: “{q}”</Typography.Title>
      {empty ? (
        <Empty description="Nenhum resultado" />
      ) : (
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Card title="Membros">
              <List
                dataSource={data.musicians}
                renderItem={(m) => (
                  <List.Item>
                    <Link to={`/musicians/${m.id}`}>{m.name}</Link>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card title="Patrimônio">
              <List
                dataSource={data.patrimonio}
                renderItem={(p) => (
                  <List.Item>
                    <Link to={`/patrimonio/${p.id}`}>{p.identificador}</Link>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card title="Obras">
              <List
                dataSource={data.obras}
                renderItem={(o) => (
                  <List.Item>
                    <Link to={`/acervo/obras/${o.id}`}>{o.titulo}</Link>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}
