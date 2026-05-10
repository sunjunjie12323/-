import React, { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Tag,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Progress,
  Typography,
  Descriptions,
  Divider,
  List,
  Badge,
  message,
  Spin,
  Tooltip,
  Empty,
  Alert,
} from 'antd';
import {
  PlusOutlined,
  ThunderboltOutlined,
  SplitCellsOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { pirApi, taskApi, extractErrorMessage } from '../services/api';
import type { PIR, PIRTask, Task } from '../types';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const priorityConfig: Record<string, { color: string; label: string }> = {
  critical: { color: 'red', label: '紧急' },
  high: { color: 'orange', label: '高' },
  medium: { color: 'gold', label: '中' },
  low: { color: 'green', label: '低' },
};

const statusConfig: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  draft: { color: 'default', label: '草稿', icon: <ClockCircleOutlined /> },
  active: { color: 'blue', label: '活跃', icon: <PlayCircleOutlined /> },
  executing: { color: 'processing', label: '执行中', icon: <SyncOutlined spin /> },
  completed: { color: 'success', label: '已完成', icon: <CheckCircleOutlined /> },
  archived: { color: 'default', label: '已归档', icon: <CloseCircleOutlined /> },
};

const taskStatusConfig: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待执行' },
  running: { color: 'processing', label: '执行中' },
  completed: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '失败' },
};

const PIRManager: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pirs, setPirs] = useState<PIR[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createVisible, setCreateVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedPIR, setSelectedPIR] = useState<PIR | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [executing, setExecuting] = useState<string | null>(null);
  const [decomposing, setDecomposing] = useState<string | null>(null);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm] = Form.useForm();

  const fetchPIRs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await pirApi.getPIRs({ page, page_size: pageSize });
      setPirs(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(extractErrorMessage(err));
      setPirs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchPIRs();
  }, [fetchPIRs]);

  const handleCreate = async (values: Record<string, unknown>) => {
    setCreateLoading(true);
    try {
      await pirApi.createPIR(values as Partial<PIR>);
      message.success('PIR创建成功');
    } catch (err) {
      message.error(`创建失败: ${extractErrorMessage(err)}`);
    }
    setCreateLoading(false);
    setCreateVisible(false);
    createForm.resetFields();
    fetchPIRs();
  };

  const handleDecompose = async (pirId: string) => {
    setDecomposing(pirId);
    try {
      await pirApi.decomposePIR(pirId);
      message.success('PIR分解完成');
    } catch (err) {
      message.error(`分解失败: ${extractErrorMessage(err)}`);
    }
    setDecomposing(null);
    fetchPIRs();
  };

  const handleExecute = async (pirId: string) => {
    setExecuting(pirId);
    try {
      const result = await pirApi.executePIR(pirId);
      message.success('PIR执行已启动');
      if (result.id) {
        try {
          const task = await taskApi.waitForCompletion(result.id, 2000, 30);
          if (task.status === 'completed') {
            message.success('PIR执行完成');
          } else if (task.status === 'failed') {
            message.error(`PIR执行失败: ${task.error || '未知错误'}`);
          }
        } catch {
          message.info('执行中，请稍后刷新查看结果');
        }
      }
    } catch (err) {
      message.error(`执行失败: ${extractErrorMessage(err)}`);
    }
    setExecuting(null);
    fetchPIRs();
  };

  const handleViewDetail = async (pir: PIR) => {
    setDetailLoading(true);
    setDetailVisible(true);
    try {
      const detail = await pirApi.getPIRDetail(pir.id);
      setSelectedPIR(detail);
    } catch (err) {
      message.warning('详情加载失败，显示基本信息');
      setSelectedPIR(pir);
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
      render: (text: string, record: PIR) => (
        <Button type="link" style={{ padding: 0, height: 'auto' }} onClick={() => handleViewDetail(record)}>
          {text}
        </Button>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 90,
      render: (priority: string) => {
        const config = priorityConfig[priority] || priorityConfig.medium;
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: string) => {
        const config = statusConfig[status] || statusConfig.draft;
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.label}
          </Tag>
        );
      },
    },
    {
      title: '完成度',
      dataIndex: 'fulfillment_score',
      key: 'fulfillment_score',
      width: 160,
      render: (score: number) => (
        <Progress
          percent={score}
          size="small"
          status={score >= 100 ? 'success' : score > 60 ? 'active' : 'normal'}
          strokeColor={score >= 100 ? '#52c41a' : score > 60 ? '#1890ff' : '#faad14'}
        />
      ),
    },
    {
      title: '子任务',
      dataIndex: 'tasks',
      key: 'tasks',
      width: 100,
      render: (tasks: PIRTask[]) => {
        const completed = tasks?.filter((t) => t.status === 'completed').length || 0;
        return (
          <Text style={{ fontSize: 12 }}>
            {completed}/{tasks?.length || 0}
          </Text>
        );
      },
    },
    {
      title: '报告',
      dataIndex: 'generated_reports',
      key: 'generated_reports',
      width: 80,
      render: (reports: string[]) => (
        <Badge count={reports?.length || 0} size="small">
          <FileTextOutlined style={{ fontSize: 16 }} />
        </Badge>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (date: string) => dayjs(date).format('MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: PIR) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record)}
            />
          </Tooltip>
          <Tooltip title="分解任务">
            <Button
              size="small"
              icon={<SplitCellsOutlined />}
              onClick={() => handleDecompose(record.id)}
              loading={decomposing === record.id}
              disabled={record.status === 'executing' || record.status === 'completed'}
            />
          </Tooltip>
          <Tooltip title="执行PIR">
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => handleExecute(record.id)}
              loading={executing === record.id}
              disabled={record.status === 'executing' || record.status === 'completed'}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {error && (
        <Alert
          message="数据加载失败"
          description={error}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={fetchPIRs}>
              重试
            </Button>
          }
        />
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={5} style={{ margin: 0 }}>
            情报需求管理
          </Title>
          <Tag color="blue">{total} 个PIR</Tag>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchPIRs}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
            新建PIR
          </Button>
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={pirs}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: error ? <Empty description="数据加载失败" /> : <Empty description="暂无PIR数据" /> }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 个PIR`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
        style={{ borderRadius: 8, overflow: 'hidden' }}
      />

      <Modal
        title="新建情报需求 (PIR)"
        open={createVisible}
        onCancel={() => setCreateVisible(false)}
        onOk={() => createForm.submit()}
        confirmLoading={createLoading}
        width={640}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入PIR标题' }]}>
            <Input placeholder="输入情报需求标题" />
          </Form.Item>
          <Form.Item name="priority" label="优先级" initialValue="medium" rules={[{ required: true }]}>
            <Select
              options={Object.entries(priorityConfig).map(([value, config]) => ({
                label: config.label,
                value,
              }))}
            />
          </Form.Item>
          <Form.Item name="description" label="描述" rules={[{ required: true, message: '请输入PIR描述' }]}>
            <TextArea rows={4} placeholder="详细描述情报需求，包含关注的目标、范围和期望输出" />
          </Form.Item>
          <Form.Item name="keywords" label="关键词">
            <Select mode="tags" placeholder="输入关键词后回车" />
          </Form.Item>
          <Form.Item name="target_entities" label="目标实体">
            <Select mode="tags" placeholder="输入目标实体ID或名称" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="PIR详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        width={760}
        footer={[
          <Button key="close" onClick={() => setDetailVisible(false)}>
            关闭
          </Button>,
          selectedPIR?.status !== 'completed' && (
            <Button
              key="decompose"
              icon={<SplitCellsOutlined />}
              onClick={() => {
                if (selectedPIR) handleDecompose(selectedPIR.id);
              }}
            >
              分解任务
            </Button>
          ),
          (selectedPIR?.status === 'active' || selectedPIR?.status === 'draft') && (
            <Button
              key="execute"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => {
                if (selectedPIR) handleExecute(selectedPIR.id);
              }}
            >
              执行PIR
            </Button>
          ),
        ].filter(Boolean)}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" tip="加载详情..." />
          </div>
        ) : selectedPIR ? (
          <div>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="标题" span={2}>
                <Text strong>{selectedPIR.title}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="优先级">
                <Tag color={priorityConfig[selectedPIR.priority]?.color}>
                  {priorityConfig[selectedPIR.priority]?.label}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusConfig[selectedPIR.status]?.color} icon={statusConfig[selectedPIR.status]?.icon}>
                  {statusConfig[selectedPIR.status]?.label}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {dayjs(selectedPIR.created_at).format('YYYY-MM-DD HH:mm')}
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">
                {dayjs(selectedPIR.updated_at).format('YYYY-MM-DD HH:mm')}
              </Descriptions.Item>
              <Descriptions.Item label="完成度" span={2}>
                <Progress
                  percent={selectedPIR.fulfillment_score}
                  status={selectedPIR.fulfillment_score >= 100 ? 'success' : 'active'}
                />
              </Descriptions.Item>
            </Descriptions>

            <Divider orientation="left">描述</Divider>
            <Paragraph>{selectedPIR.description}</Paragraph>

            {selectedPIR.keywords?.length > 0 && (
              <>
                <Divider orientation="left">关键词</Divider>
                <Space wrap>
                  {selectedPIR.keywords.map((kw, i) => (
                    <Tag key={i} color="blue">{kw}</Tag>
                  ))}
                </Space>
              </>
            )}

            <Divider orientation="left">子任务列表</Divider>
            {selectedPIR.tasks?.length > 0 ? (
              <List
                size="small"
                dataSource={selectedPIR.tasks}
                renderItem={(task: PIRTask) => (
                  <List.Item>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                      <Space>
                        <Tag color={taskStatusConfig[task.status]?.color}>
                          {taskStatusConfig[task.status]?.label}
                        </Tag>
                        <Tag>{task.task_type}</Tag>
                        <Text style={{ fontSize: 13 }}>{task.description}</Text>
                      </Space>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {dayjs(task.created_at).format('HH:mm')}
                      </Text>
                    </div>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="暂无子任务，请先分解PIR" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}

            {selectedPIR.generated_reports?.length > 0 && (
              <>
                <Divider orientation="left">生成报告</Divider>
                <Space wrap>
                  {selectedPIR.generated_reports.map((reportId, i) => (
                    <Tag key={i} icon={<FileTextOutlined />} color="green">
                      报告 {reportId}
                    </Tag>
                  ))}
                </Space>
              </>
            )}
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default PIRManager;
