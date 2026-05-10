import React, { useState, useEffect, useCallback } from 'react';
import { Row, Col, Card, List, Tag, Badge, Progress, Typography, Space, Timeline, Empty, Spin, Tooltip, Divider, Alert, Button, Skeleton } from 'antd';
import {
  SearchOutlined,
  AimOutlined,
  AlertOutlined,
  ApartmentOutlined,
  RobotOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import StatCard from '../components/StatCard';
import IntelCard from '../components/IntelCard';
import { dashboardApi, taskApi, extractErrorMessage } from '../services/api';
import type { DashboardStats, Intelligence, AgentStatus, ExecutionRecord, Task } from '../types';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

const threatLevelConfig: Record<string, { color: string; label: string }> = {
  critical: { color: '#ff4d4f', label: '严重' },
  high: { color: '#ff7a45', label: '高危' },
  medium: { color: '#faad14', label: '中危' },
  low: { color: '#52c41a', label: '低危' },
  info: { color: '#1890ff', label: '信息' },
};

const agentStatusIcons: Record<string, React.ReactNode> = {
  idle: <ClockCircleOutlined style={{ color: '#8c8c8c' }} />,
  running: <SyncOutlined spin style={{ color: '#1890ff' }} />,
  error: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
};

const executionStatusConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  running: { color: 'processing', icon: <SyncOutlined spin /> },
  completed: { color: 'success', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', icon: <CloseCircleOutlined /> },
};

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentTasks, setRecentTasks] = useState<Task[]>([]);

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const data = await dashboardApi.getDashboardStats();
      setStats(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTasks = useCallback(async () => {
    try {
      const result = await taskApi.getTasks({ limit: 5 });
      setRecentTasks(result.items);
    } catch {
      // task fetch failure is non-critical
    }
  }, []);

  useEffect(() => {
    fetchData();
    fetchTasks();
    const interval = setInterval(() => {
      fetchData();
      fetchTasks();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchData, fetchTasks]);

  const handleRetry = () => {
    setLoading(true);
    fetchData();
    fetchTasks();
  };

  if (loading) {
    return (
      <div>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Col xs={24} sm={12} lg={6} key={i}>
              <Card style={{ borderRadius: 8 }}>
                <Skeleton active paragraph={{ rows: 1 }} />
              </Card>
            </Col>
          ))}
        </Row>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} lg={14}>
            <Card style={{ borderRadius: 8 }}>
              <Skeleton active paragraph={{ rows: 6 }} />
            </Card>
          </Col>
          <Col xs={24} lg={10}>
            <Card style={{ borderRadius: 8, marginBottom: 16 }}>
              <Skeleton active paragraph={{ rows: 4 }} />
            </Card>
            <Card style={{ borderRadius: 8 }}>
              <Skeleton active paragraph={{ rows: 3 }} />
            </Card>
          </Col>
        </Row>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <Result
          status="error"
          title="数据加载失败"
          subTitle={error}
          extra={
            <Button type="primary" icon={<ReloadOutlined />} onClick={handleRetry}>
              重新加载
            </Button>
          }
        />
      </div>
    );
  }

  if (!stats) return null;

  const totalThreats = Object.values(stats.threat_level_distribution || {}).reduce((a, b) => a + b, 0) || 1;

  return (
    <div>
      {error && (
        <Alert
          message="部分数据刷新失败"
          description={error}
          type="warning"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={handleRetry}>
              重试
            </Button>
          }
        />
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="情报总量"
            value={stats.total_intelligence}
            icon={<SearchOutlined />}
            color="#1890ff"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="活跃PIR"
            value={stats.active_pirs}
            icon={<AimOutlined />}
            color="#722ed1"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="威胁告警"
            value={stats.threat_alerts}
            icon={<AlertOutlined />}
            color="#ff4d4f"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="图谱节点"
            value={stats.graph_nodes}
            icon={<ApartmentOutlined />}
            color="#52c41a"
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card
            title={
              <Space>
                <ThunderboltOutlined />
                <span>最新情报</span>
              </Space>
            }
            style={{ borderRadius: 8 }}
            styles={{ body: { padding: '8px 16px', maxHeight: 420, overflow: 'auto' } }}
          >
            {stats.recent_intelligence?.length ? (
              stats.recent_intelligence.map((intel) => (
                <IntelCard key={intel.id} intel={intel} />
              ))
            ) : (
              <Empty description="暂无最新情报" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <AlertOutlined />
                <span>威胁等级分布</span>
              </Space>
            }
            style={{ borderRadius: 8, marginBottom: 16 }}
            styles={{ body: { padding: '16px 24px' } }}
          >
            {Object.entries(stats.threat_level_distribution || {}).length > 0 ? (
              Object.entries(stats.threat_level_distribution).map(([level, count]) => {
                const config = threatLevelConfig[level] || threatLevelConfig.info;
                const percent = Math.round((count / totalThreats) * 100);
                return (
                  <div key={level} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontSize: 13 }}>
                        <Badge color={config.color} text={config.label} />
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>{count} ({percent}%)</Text>
                    </div>
                    <Progress
                      percent={percent}
                      showInfo={false}
                      strokeColor={config.color}
                      trailColor="#f0f0f0"
                      size="small"
                    />
                  </div>
                );
              })
            ) : (
              <Empty description="暂无威胁数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
          <Card
            title={
              <Space>
                <RobotOutlined />
                <span>Agent状态</span>
              </Space>
            }
            style={{ borderRadius: 8 }}
            styles={{ body: { padding: '12px 24px' } }}
          >
            {stats.agent_statuses?.length ? (
              <List
                dataSource={stats.agent_statuses}
                renderItem={(agent: AgentStatus) => (
                  <List.Item style={{ padding: '8px 0', border: 'none' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                      <Space>
                        {agentStatusIcons[agent.status]}
                        <Text style={{ fontSize: 13 }}>{agent.name}</Text>
                      </Space>
                      <Space size="small">
                        {agent.current_task && (
                          <Tooltip title={agent.current_task}>
                            <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
                              {agent.current_task.length > 10
                                ? agent.current_task.slice(0, 10) + '...'
                                : agent.current_task}
                            </Tag>
                          </Tooltip>
                        )}
                        <Tag
                          color={agent.status === 'running' ? 'processing' : agent.status === 'error' ? 'error' : 'default'}
                          style={{ fontSize: 11, margin: 0 }}
                        >
                          {agent.status === 'running' ? '运行中' : agent.status === 'error' ? '异常' : '空闲'}
                        </Tag>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {agent.execution_count}次
                        </Text>
                      </Space>
                    </div>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="暂无Agent状态" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <Card
            title={
              <Space>
                <ClockCircleOutlined />
                <span>最近执行记录</span>
              </Space>
            }
            style={{ borderRadius: 8 }}
            styles={{ body: { padding: '12px 24px' } }}
          >
            {stats.recent_executions?.length ? (
              <Timeline
                items={stats.recent_executions.map((exec: ExecutionRecord) => ({
                  color: executionStatusConfig[exec.status]?.color === 'success' ? 'green' : executionStatusConfig[exec.status]?.color === 'error' ? 'red' : 'blue',
                  children: (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Space>
                        {executionStatusConfig[exec.status]?.icon}
                        <Text style={{ fontSize: 13 }}>{exec.query}</Text>
                        <Tag style={{ fontSize: 11, margin: 0 }}>{exec.agent_name}</Tag>
                      </Space>
                      <Space>
                        {exec.result_summary && (
                          <Text type="secondary" style={{ fontSize: 12 }}>{exec.result_summary}</Text>
                        )}
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {dayjs(exec.started_at).format('HH:mm')}
                        </Text>
                      </Space>
                    </div>
                  ),
                }))}
              />
            ) : (
              <Empty description="暂无执行记录" />
            )}
          </Card>
        </Col>
      </Row>

      {recentTasks.length > 0 && (
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24}>
            <Card
              title={
                <Space>
                  <SyncOutlined />
                  <span>任务队列</span>
                </Space>
              }
              style={{ borderRadius: 8 }}
              styles={{ body: { padding: '12px 24px' } }}
            >
              <List
                size="small"
                dataSource={recentTasks}
                renderItem={(task) => (
                  <List.Item style={{ padding: '8px 0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                      <Space>
                        <Tag color={
                          task.status === 'running' ? 'processing' :
                          task.status === 'completed' ? 'success' :
                          task.status === 'failed' ? 'error' : 'default'
                        }>
                          {task.status === 'pending' ? '待执行' :
                           task.status === 'running' ? '执行中' :
                           task.status === 'completed' ? '已完成' :
                           task.status === 'failed' ? '失败' : '已取消'}
                        </Tag>
                        <Text style={{ fontSize: 13 }}>{task.type}</Text>
                      </Space>
                      <Space>
                        {task.status === 'running' && (
                          <Progress percent={Math.round(task.progress)} size="small" style={{ width: 100 }} />
                        )}
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {dayjs(task.created_at).format('HH:mm')}
                        </Text>
                      </Space>
                    </div>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
};

export default Dashboard;

function Result({ status, title, subTitle, extra }: { status: "error"; title: string; subTitle: string; extra: React.ReactNode }) {
  return (
    <Card style={{ borderRadius: 8, maxWidth: 480, textAlign: 'center' }}>
      <CloseCircleOutlined style={{ fontSize: 48, color: '#ff4d4f', marginBottom: 16 }} />
      <Title level={4} style={{ marginBottom: 8 }}>{title}</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>{subTitle}</Text>
      {extra}
    </Card>
  );
}
