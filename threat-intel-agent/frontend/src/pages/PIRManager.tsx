import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select, message,
  Empty, Spin, Typography, Popconfirm, Progress, List, Badge, Tooltip,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, PlayCircleOutlined,
  ScissorOutlined, EyeOutlined, CheckCircleOutlined, ClockCircleOutlined,
  ExclamationCircleOutlined, SyncOutlined,
} from '@ant-design/icons';
import { pirsApi, getErrorMessage } from '../services/api';
import type { PIR, PIRTask, PaginatedResponse } from '../types';

const { Text, Paragraph } = Typography;

const PRIORITY_CONFIG: Record<string, { color: string; label: string }> = {
  critical: { color: '#cf1322', label: '紧急' },
  high: { color: '#d4380d', label: '高' },
  medium: { color: '#d48806', label: '中' },
  low: { color: '#389e0d', label: '低' },
};

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  draft: { color: 'default', label: '草稿' },
  active: { color: 'processing', label: '活跃' },
  executing: { color: 'blue', label: '执行中' },
  fulfilled: { color: 'success', label: '已完成' },
  archived: { color: 'default', label: '已归档' },
};

const TASK_STATUS_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  pending: { color: 'default', label: '待执行', icon: <ClockCircleOutlined /> },
  running: { color: 'processing', label: '运行中', icon: <SyncOutlined spin /> },
  completed: { color: 'success', label: '已完成', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', label: '失败', icon: <ExclamationCircleOutlined /> },
};

const PIRManager: React.FC = () => {
  const [pirs, setPirs] = useState<PaginatedResponse<PIR>>({ items: [], total: 0, offset: 0, limit: 20 });
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedPir, setSelectedPir] = useState<PIR | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [form] = Form.useForm();

  const fetchPirs = useCallback(async () => {
    try {
      setLoading(true);
      const result = await pirsApi.list({
        status: statusFilter,
        offset: (page - 1) * pageSize,
        limit: pageSize,
      });
      setPirs(result);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page, pageSize]);

  useEffect(() => {
    fetchPirs();
  }, [fetchPirs]);

  const handleCreate = async (values: { title: string; description?: string; priority?: string; keywords?: string; target_sources?: string }) => {
    try {
      await pirsApi.create({
        title: values.title,
        description: values.description || '',
        priority: values.priority || 'medium',
        keywords: values.keywords ? values.keywords.split(',').map((k: string) => k.trim()).filter(Boolean) : [],
        target_sources: values.target_sources ? values.target_sources.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      });
      message.success('PIR创建成功');
      setCreateModalOpen(false);
      form.resetFields();
      fetchPirs();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleDelete = async (pirId: string) => {
    try {
      await pirsApi.delete(pirId);
      message.success('删除成功');
      fetchPirs();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleDecompose = async (pirId: string) => {
    try {
      const result = await pirsApi.decompose(pirId);
      message.success(`任务分解完成，共 ${result.task_count} 个任务`);
      fetchPirs();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleExecute = async (pirId: string) => {
    try {
      const result = await pirsApi.execute(pirId);
      message.success(`PIR执行已提交，任务ID: ${result.task_id}`);
      fetchPirs();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleViewDetail = async (pirId: string) => {
    setDetailModalOpen(true);
    setDetailLoading(true);
    try {
      const pir = await pirsApi.get(pirId);
      setSelectedPir(pir);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setDetailLoading(false);
    }
  };

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title: string) => <Text strong>{title}</Text>,
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: string) => {
        const config = PRIORITY_CONFIG[priority];
        return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{priority}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config = STATUS_CONFIG[status];
        return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{status}</Tag>;
      },
    },
    {
      title: '完成度',
      dataIndex: 'fulfillment_score',
      key: 'fulfillment_score',
      width: 120,
      render: (score: number) => (
        <Progress
          percent={score || 0}
          size="small"
          status={score >= 100 ? 'success' : 'active'}
        />
      ),
    },
    {
      title: '关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      width: 200,
      render: (keywords: string[]) => (
        <Space size={[4, 4]} wrap>
          {(keywords || []).slice(0, 3).map((kw, idx) => <Tag key={idx}>{kw}</Tag>)}
          {keywords && keywords.length > 3 && <Tag>+{keywords.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: PIR) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record.id)} />
          </Tooltip>
          {record.status === 'draft' && (
            <>
              <Tooltip title="任务分解">
                <Button type="link" size="small" icon={<ScissorOutlined />} onClick={() => handleDecompose(record.id)} />
              </Tooltip>
              <Tooltip title="执行">
                <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleExecute(record.id)} />
              </Tooltip>
            </>
          )}
          {record.status === 'active' && (
            <Tooltip title="执行">
              <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleExecute(record.id)} />
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
            <Select
              placeholder="状态筛选"
              value={statusFilter}
              onChange={(v) => { setStatusFilter(v); setPage(1); }}
              options={Object.entries(STATUS_CONFIG).map(([value, config]) => ({ value, label: config.label }))}
              allowClear
              style={{ width: 130 }}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchPirs}>刷新</Button>
          </Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            新建PIR
          </Button>
        </Space>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={pirs.items}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: <Empty description="暂无PIR数据" /> }}
          pagination={{
            current: page,
            pageSize,
            total: pirs.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
        />
      </Card>

      <Modal
        title="新建PIR"
        open={createModalOpen}
        onCancel={() => { setCreateModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入PIR标题' }]}>
            <Input placeholder="输入PIR标题" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="描述情报需求..." />
          </Form.Item>
          <Form.Item name="priority" label="优先级" initialValue="medium">
            <Select options={Object.entries(PRIORITY_CONFIG).map(([value, config]) => ({ value, label: config.label }))} />
          </Form.Item>
          <Form.Item name="keywords" label="关键词（逗号分隔）">
            <Input placeholder="例如: 暗网,数据泄露,黑客" />
          </Form.Item>
          <Form.Item name="target_sources" label="目标来源（逗号分隔）">
            <Input placeholder="例如: telegram,dark_web" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="PIR详情"
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setSelectedPir(null); }}
        footer={null}
        width={700}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : selectedPir ? (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Tag color={PRIORITY_CONFIG[selectedPir.priority]?.color}>
                  {PRIORITY_CONFIG[selectedPir.priority]?.label || selectedPir.priority}
                </Tag>
                <Tag color={STATUS_CONFIG[selectedPir.status]?.color}>
                  {STATUS_CONFIG[selectedPir.status]?.label || selectedPir.status}
                </Tag>
              </Space>
            </div>

            <Paragraph><Text strong>标题: </Text>{selectedPir.title}</Paragraph>
            {selectedPir.description && <Paragraph><Text strong>描述: </Text>{selectedPir.description}</Paragraph>}

            {selectedPir.keywords && selectedPir.keywords.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <Text strong>关键词: </Text>
                <Space size={[4, 4]} wrap>{selectedPir.keywords.map((kw, idx) => <Tag key={idx}>{kw}</Tag>)}</Space>
              </div>
            )}

            <div style={{ marginBottom: 12 }}>
              <Text strong>完成度: </Text>
              <Progress percent={selectedPir.fulfillment_score || 0} style={{ maxWidth: 300, display: 'inline-block', marginLeft: 8 }} />
            </div>

            {selectedPir.tasks && selectedPir.tasks.length > 0 && (
              <div>
                <Text strong style={{ display: 'block', marginBottom: 8 }}>任务列表:</Text>
                <List
                  size="small"
                  dataSource={selectedPir.tasks}
                  renderItem={(task: PIRTask) => {
                    const taskConfig = TASK_STATUS_CONFIG[task.status] || TASK_STATUS_CONFIG.pending;
                    return (
                      <List.Item>
                        <List.Item.Meta
                          avatar={taskConfig.icon}
                          title={
                            <span>
                              <Tag color={taskConfig.color}>{taskConfig.label}</Tag>
                              {task.agent_type}
                            </span>
                          }
                          description={task.task_description || `PIR任务 - ${task.agent_type}`}
                        />
                      </List.Item>
                    );
                  }}
                />
              </div>
            )}
          </div>
        ) : (
          <Empty description="未找到PIR数据" />
        )}
      </Modal>
    </div>
  );
};

export default PIRManager;
