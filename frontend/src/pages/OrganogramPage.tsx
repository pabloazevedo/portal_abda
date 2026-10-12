import { Avatar, Collapse, Input, Select, Space, Tag, Typography, Spin } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

type Node = {
  id: string
  pid?: string | null
  type: string
  name: string
  role?: string
  musician_id?: number
  member_count?: number
  profile_url?: string
  photo?: string | null
}

const ROLE_FILTER_OPTS = [
  { value: '', label: 'Todos os papéis' },
  { value: 'maestro', label: 'Maestro' },
  { value: 'chefe_naipe', label: 'Chefe de Naipe' },
  { value: 'arranjador', label: 'Arranjador' },
  { value: 'compositor', label: 'Compositor' },
  { value: 'arquivista', label: 'Arquivista' },
]

export default function OrganogramPage() {
  const [nodes, setNodes] = useState<Node[]>([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [roleFilter, setRoleFilter] = useState('')

  useEffect(() => {
    api
      .get('/musicians/organogram')
      .then((r) => setNodes(r.data.nodes || []))
      .finally(() => setLoading(false))
  }, [])

  const groups = useMemo(
    () => nodes.filter((n) => n.type === 'group' || n.type === 'subgroup'),
    [nodes],
  )
  const members = useMemo(
    () => nodes.filter((n) => n.type === 'member'),
    [nodes],
  )

  const filteredMembers = useMemo(() => {
    const term = q.trim().toLowerCase()
    return members.filter((m) => {
      if (roleFilter && !m.id.endsWith(`_${roleFilter}`)) return false
      if (!term) return true
      return [m.name, m.role].some((s) => (s || '').toLowerCase().includes(term))
    })
  }, [members, q, roleFilter])

  if (loading) return <Spin />

  const items = groups.map((g) => {
    const kids = filteredMembers.filter((m) => m.pid === g.id)
    return {
      key: g.id,
      label: (
        <span>
          {g.name}{' '}
          {typeof g.member_count === 'number' ? (
            <Tag>{g.member_count}</Tag>
          ) : (
            <Tag>{kids.length}</Tag>
          )}
        </span>
      ),
      children:
        kids.length === 0 ? (
          <Typography.Text type="secondary">{g.role || 'Nenhum membro neste filtro'}</Typography.Text>
        ) : (
          kids.map((m) => (
            <Space key={m.id} style={{ display: 'flex', marginBottom: 10 }} align="start">
              <Avatar size={36} src={m.photo || undefined} icon={<UserOutlined />} />
              <div>
                <Link to={m.profile_url || `/musicians/${m.musician_id}`}>{m.name}</Link>
                <div>
                  <Typography.Text type="secondary">{m.role}</Typography.Text>
                </div>
              </div>
            </Space>
          ))
        ),
    }
  })

  return (
    <div>
      <Typography.Title level={3}>Organograma</Typography.Title>
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Buscar membro..."
          allowClear
          onSearch={setQ}
          onChange={(e) => { if (!e.target.value) setQ('') }}
          style={{ width: 260 }}
        />
        <Select
          style={{ width: 200 }}
          options={ROLE_FILTER_OPTS}
          value={roleFilter}
          onChange={setRoleFilter}
        />
      </Space>
      <Collapse defaultActiveKey={groups.map((g) => g.id)} items={items} />
    </div>
  )
}
