import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Tag, Input, Select, Button, Space, Modal, Form, message,
  Empty, Spin, Typography, Popconfirm, Badge, Tooltip,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, ReloadOutlined, DeleteOutlined,
  EyeOutlined, FilterOutlined,
} from '@ant-design/icons';
import { intelligenceApi, getErrorMessage } from '../services/api';
import type { IntelligenceItem, IntelligenceStats, PaginatedResponse } from '../types';

const { Text, Paragraph } = Typography;

const THREAT_LEVEL_CONFIG: Record<string, { color: string; label: string }> = {
  critical: { color: '#cf1322', label: '严重' },
  high: { color: '#d4380d', label: '高危' },
  medium: { color: '#d48806', label: '中危' },
  low: { color: '#389e0d', label: '低危' },
  info: { color: '#0958d9', label: '信息' },
};

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  raw: { color: 'default', label: '原始' },
  cleaned: { color: 'processing', label: '已清洗' },
  analyzed: { color: 'success', label: '已分析' },
};

const SOURCE_OPTIONS = [
  { value: 'telegram', label: 'Telegram' },
  { value: 'dark_web', label: '暗网' },
  { value: 'forum', label: '论坛' },
  { value: 'social_media', label: '社交媒体' },
  { value: 'other', label: '其他' },
];

const THREAT_LEVEL_OPTIONS = [
  { value: 'critical', label: '严重' },
  { value: 'high', label: '高危' },
  { value: 'medium', label: '中危' },
  { value: 'low', label: '低危' },
  { value: 'info', label: '信息' },
];

const Intelligence: React.FC = () => {
  const [data, setData] = useState<PaginatedResponse<IntelligenceItem>>({ items: [], total: 0, offset: 0, limit: 20 });
  const [stats, setStats] = useState<IntelligenceStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [sourceFilter, setSourceFilter] = useState<string | undefined>();
  const [threatFilter, setThreatFilter] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<IntelligenceItem | null>(null);
  const [detailData, setDetailData] = useState<unknown>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const result = await intelligenceApi.list({
        search: search || undefined,
        source: sourceFilter,
        threat_level: threatFilter,
        offset: (page - 1) * pageSize,
        limit: pageSize,
      });
      setData(result);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [search, sourceFilter, threatFilter, page, pageSize]);

  const fetchStats = useCallback(async () => {
    try {
      const s = await intelligenceApi.getStats();
      setStats(s);
    } catch {
      // ignore stats errors
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleCreate = async (values: { source: string; content: string; source_url?: string }) => {
    try {
      await intelligenceApi.create({
        source: values.source,
        content: values.content,
        source_url: values.source_url,
      });
      message.success('情报创建成功');
      setCreateModalOpen(false);
      form.resetFields();
      fetchData();
      fetchStats();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await intelligenceApi.delete(id);
      message.success('删除成功');
      fetchData();
      fetchStats();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleViewDetail = async (item: IntelligenceItem) => {
    setSelectedItem(item);
    setDetailModalOpen(true);
    setDetailLoading(true);
    try {
      const detail = await intelligenceApi.get(item.id);
      setDetailData(detail);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setDetailLoading(false);
    }
  };

  const handleStatusChange = async (id: string, status: string) => {
    try {
      await intelligenceApi.updateStatus(id, status);
      message.success('状态更新成功');
      fetchData();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      ellipsis: true,
      render: (id: string) => <Text copyable={{ text: id }}>{id.substring(0, 8)}...</Text>,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (source: string | null) => source ? <Tag>{source}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (content: string) => (
        <Tooltip title={content}>
          <Text ellipsis style={{ maxWidth: 300 }}>{content}</Text>
        </Tooltip>
      ),
    },
    {
      title: '威胁等级',
      dataIndex: 'threat_level',
      key: 'threat_level',
      width: 100,
      render: (level: string | null) => {
        if (!level) return <Text type="secondary">-</Text>;
        const config = THREAT_LEVEL_CONFIG[level];
        return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{level}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const config = STATUS_CONFIG[status];
        return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{status}</Tag>;
      },
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: '收集时间',
      dataIndex: 'collected_at',
      key: 'collected_at',
      width: 160,
      render: (time: string | null) => time ? new Date(time).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: IntelligenceItem) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)} />
          </Tooltip>
          {record.status === 'raw' && (
            <Tooltip title="标记为已清洗">
              <Button type="link" size="small" onClick={() => handleStatusChange(record.id, 'cleaned')}>清洗</Button>
            </Tooltip>
          )}
          {record.status === 'cleaned' && (
            <Tooltip title="标记为已分析">
              <Button type="link" size="small" onClick={() => handleStatusChange(record.id, 'analyzed')}>分析</Button>
            </Tooltip>
          )}
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)} okText="确认" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space wrap>
            <Input
              placeholder="搜索情报内容..."
              prefix={<SearchOutlined />}
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              style={{ width: 250 }}
              allowClear
            />
            <Select
              placeholder="来源筛选"
              value={sourceFilter}
              onChange={(v) => { setSourceFilter(v); setPage(1); }}
              options={SOURCE_OPTIONS}
              allowClear
              style={{ width: 130 }}
            />
            <Select
              placeholder="威胁等级"
              value={threatFilter}
              onChange={(v) => { setThreatFilter(v); setPage(1); }}
              options={THREAT_LEVEL_OPTIONS}
              allowClear
              style={{ width: 130 }}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          </Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            新增情报
          </Button>
        </Space>
      </Card>

      {stats && (
        <Card style={{ marginBottom: 16 }}>
          <Space size="large">
            <Text>总计: <Text strong>{stats.total}</Text></Text>
            {Object.entries(stats.by_status).map(([status, count]) => (
              <Text key={status}>
                {STATUS_CONFIG[status]?.label || status}: <Text strong>{count}</Text>
              </Text>
            ))}
          </Space>
        </Card>
      )}

      <Card>
        <Table
          columns={columns}
          dataSource={data.items}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: <Empty description="暂无情报数据" /> }}
          pagination={{
            current: page,
            pageSize,
            total: data.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          scroll={{ x: 1000 }}
        />
      </Card>

      <Modal
        title="新增情报"
        open={createModalOpen}
        onCancel={() => { setCreateModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="source" label="来源" initialValue="other">
            <Select options={SOURCE_OPTIONS} />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入情报内容' }]}>
            <Input.TextArea rows={4} placeholder="输入情报内容..." />
          </Form.Item>
          <Form.Item name="source_url" label="来源URL">
            <Input placeholder="可选，情报来源链接" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="情报详情"
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setSelectedItem(null); setDetailData(null); }}
        footer={null}
        width={700}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <div>
            {selectedItem && (
              <div style={{ marginBottom: 16 }}>
                <Space>
                  <Tag>{selectedItem.type}</Tag>
                  {selectedItem.threat_level && THREAT_LEVEL_CONFIG[selectedItem.threat_level] && (
                    <Tag color={THREAT_LEVEL_CONFIG[selectedItem.threat_level].color}>
                      {THREAT_LEVEL_CONFIG[selectedItem.threat_level].label}
                    </Tag>
                  )}
                  <Tag color={STATUS_CONFIG[selectedItem.status]?.color}>
                    {STATUS_CONFIG[selectedItem.status]?.label || selectedItem.status}
                  </Tag>
                </Space>
              </div>
            )}
            {detailData !== null && (
              <Paragraph>
                <pre style={{ maxHeight: 400, overflow: 'auto', background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                  {JSON.stringify(detailData, null, 2)}
                </pre>
              </Paragraph>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Intelligence;
