import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Card, Spin, message, Empty, Tag, Typography, Row, Col, Statistic, List, Badge, Progress, Button, Space } from 'antd';
import {
  AlertOutlined,
  DatabaseOutlined,
  NodeIndexOutlined,
  FileSearchOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  SyncOutlined,
  TranslationOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { dashboardApi, agentApi } from '../services/api';
import type { DashboardStats, RecentIntelligence, AgentStatus, RecentExecution, TaskStatus } from '../types';
import { THREAT_LEVEL_CONFIG } from '../utils/constants';
import { formatTime } from '../utils/constants';

const { Title, Text, Paragraph } = Typography;

const AGENT_STATUS_ICON: Record<string, React.ReactNode> = {
  idle: <ClockCircleOutlined />,
  running: <SyncOutlined spin />,
  completed: <CheckCircleOutlined />,
  error: <ExclamationCircleOutlined />,
};

const STEP_LABELS: Record<string, string> = {
  collecting: '情报采集中',
  cleaning: '数据清洗中',
  analyzing: '分析处理中',
  building_graph: '构建图谱中',
  generating_report: '生成报告中',
};

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [taskProgresses, setTaskProgresses] = useState<TaskStatus[]>([]);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStats = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      setError(null);
      const data = await dashboardApi.getStats();
      setStats(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '获取仪表盘数据失败';
      setError(msg);
      if (showLoading) message.error(msg);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(() => fetchStats(false), 60000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const fetchTaskProgresses = useCallback(async () => {
    try {
      const stored = sessionStorage.getItem('tia_active_tasks');
      if (!stored) return;
      const taskIds: string[] = JSON.parse(stored);
      const activeIds = taskIds.filter(Boolean);
      if (activeIds.length === 0) return;
      const results: TaskStatus[] = [];
      for (const taskId of activeIds.slice(0, 5)) {
        try {
          const status = await agentApi.getTaskStatus(taskId);
          results.push(status);
          if (status.status === 'completed' || status.status === 'failed') {
            const current = sessionStorage.getItem('tia_active_tasks');
            if (current) {
              const ids: string[] = JSON.parse(current);
              const updated = ids.filter((id) => id !== taskId);
              sessionStorage.setItem('tia_active_tasks', JSON.stringify(updated));
            }
          }
        } catch {
          // ignore individual task fetch errors
        }
      }
      setTaskProgresses(results);
    } catch {
      // ignore parse errors
    }
  }, []);

  useEffect(() => {
    fetchTaskProgresses();
    pollingRef.current = setInterval(fetchTaskProgresses, 5000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [fetchTaskProgresses]);

  if (loading && !stats) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Empty description={`加载失败: ${error}`}>
          <a onClick={() => fetchStats()}><ReloadOutlined /> 重新加载</a>
        </Empty>
      </div>
    );
  }

  const threatDist = stats?.threat_level_distribution || {};
  const sourceDist = stats?.source_type_distribution || {};
  const knowledgeGraph = stats?.knowledge_graph || { node_count: 0, edge_count: 0 };
  const blacktalk = stats?.blacktalk || { total_terms: 0, categories: {} };

  return (
    <div style={{ padding: '0 0 24px' }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="情报总量"
              value={stats?.total_intelligence ?? 0}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#0958d9' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="活跃PIR"
              value={stats?.active_pirs ?? 0}
              prefix={<FileSearchOutlined />}
              valueStyle={{ color: '#389e0d' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="威胁告警"
              value={stats?.threat_alerts ?? 0}
              prefix={<AlertOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card hoverable>
            <Statistic
              title="图谱节点"
              value={knowledgeGraph.node_count ?? 0}
              prefix={<NodeIndexOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12}>
          <Card hoverable>
            <Statistic
              title="图谱关系"
              value={knowledgeGraph.edge_count ?? 0}
              prefix={<ShareAltOutlined />}
              valueStyle={{ color: '#13c2c2' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card hoverable>
            <Statistic
              title="黑话术语"
              value={blacktalk.total_terms ?? 0}
              prefix={<TranslationOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="最近情报" extra={<a onClick={() => fetchStats()}><ReloadOutlined style={{ marginRight: 4 }} />刷新</a>} style={{ height: '100%' }}>
            {(!stats?.recent_intelligence || stats.recent_intelligence.length === 0) ? (
              <Empty description="暂无情报数据，点击上方按钮开始采集" />
            ) : (
              <List
                dataSource={stats.recent_intelligence.slice(0, 10)}
                renderItem={(item: RecentIntelligence) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <span>
                          {item.title || item.content?.substring(0, 60) || '未命名'}
                          {item.threat_level && THREAT_LEVEL_CONFIG[item.threat_level] && (
                            <Tag
                              color={THREAT_LEVEL_CONFIG[item.threat_level].color}
                              style={{ marginLeft: 8 }}
                            >
                              {THREAT_LEVEL_CONFIG[item.threat_level].label}
                            </Tag>
                          )}
                        </span>
                      }
                      description={
                        <div>
                          <Text type="secondary">
                            {item.source || item.source_type || '未知来源'}
                            {item.collected_at && ` · ${formatTime(item.collected_at)}`}
                          </Text>
                          {item.is_processed !== undefined && (
                            <Tag color={item.is_processed ? 'green' : 'orange'} style={{ marginLeft: 8 }}>
                              {item.is_processed ? '已处理' : '待处理'}
                            </Tag>
                          )}
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card title="威胁等级分布" style={{ marginBottom: 16 }}>
            {Object.keys(threatDist).length === 0 ? (
              <Empty description="暂无威胁数据" />
            ) : (
              <div>
                {Object.entries(THREAT_LEVEL_CONFIG).map(([key, config]) => {
                  const total = Object.values(threatDist).reduce((a, b) => a + b, 0);
                  const count = threatDist[key] || 0;
                  const percent = total > 0 ? Math.round((count / total) * 100) : 0;
                  return (
                    <div key={key} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text>{config.label}</Text>
                        <Text>{count} ({percent}%)</Text>
                      </div>
                      <Progress
                        percent={percent}
                        strokeColor={config.color}
                        showInfo={false}
                        size="small"
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          <Card title="情报来源分布">
            {Object.keys(sourceDist).length === 0 ? (
              <Empty description="暂无来源数据" />
            ) : (
              <div>
                {Object.entries(sourceDist).map(([source, count]) => (
                  <div key={source} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <Tag>{source}</Tag>
                    <Text strong>{count}</Text>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="Agent 状态">
            {(!stats?.agent_statuses || stats.agent_statuses.length === 0) ? (
              <Empty description="暂无Agent状态" />
            ) : (
              <List
                dataSource={stats.agent_statuses}
                renderItem={(agent: AgentStatus) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={AGENT_STATUS_ICON[agent.status] || <ClockCircleOutlined />}
                      title={agent.name}
                      description={
                        <div>
                          <Badge
                            status={agent.status === 'running' ? 'processing' : agent.status === 'idle' ? 'default' : agent.status === 'error' ? 'error' : 'success'}
                            text={agent.status === 'running' ? '运行中' : agent.status === 'idle' ? '空闲' : agent.status === 'error' ? '错误' : '完成'}
                          />
                          {agent.current_task && <Text type="secondary" style={{ marginLeft: 8 }}>任务: {agent.current_task}</Text>}
                          {agent.execution_count !== undefined && <Text type="secondary" style={{ marginLeft: 8 }}>执行: {agent.execution_count}次</Text>}
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="最近执行">
            {(!stats?.recent_executions || stats.recent_executions.length === 0) ? (
              <Empty description="暂无执行记录" />
            ) : (
              <List
                dataSource={stats.recent_executions.slice(0, 5)}
                renderItem={(exec: RecentExecution) => (
                  <List.Item>
                    <List.Item.Meta
                      title={exec.query || exec.agent_name || '未知任务'}
                      description={
                        <div>
                          <Tag color={exec.status === 'completed' ? 'green' : exec.status === 'running' ? 'blue' : exec.status === 'failed' ? 'red' : 'default'}>
                            {exec.status || '未知'}
                          </Tag>
                          {(exec.started_at || exec.start_time) && (
                            <Text type="secondary" style={{ marginLeft: 8 }}>
                              {formatTime(exec.started_at || exec.start_time || '')}
                            </Text>
                          )}
                          {exec.duration_seconds !== undefined && (
                            <Text type="secondary" style={{ marginLeft: 8 }}>{exec.duration_seconds.toFixed(1)}s</Text>
                          )}
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {taskProgresses.length > 0 && (
        <Card title="任务进度" style={{ marginTop: 16 }}>
          <List
            dataSource={taskProgresses}
            renderItem={(task) => (
              <List.Item
                actions={[
                  <Button
                    type="link"
                    size="small"
                    onClick={() => {
                      if (task.status === 'completed' || task.status === 'failed') {
                        setTaskProgresses((prev) => prev.filter((t) => t.task_id !== task.task_id));
                      }
                    }}
                  >
                    {task.status === 'completed' || task.status === 'failed' ? '关闭' : '查看'}
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  avatar={
                    task.status === 'running' ? <SyncOutlined spin style={{ color: '#1890ff' }} /> :
                    task.status === 'completed' ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                    task.status === 'failed' ? <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} /> :
                    <ClockCircleOutlined style={{ color: '#faad14' }} />
                  }
                  title={
                    <Space>
                      <Text>任务 {task.task_id?.substring(0, 8)}...</Text>
                      <Tag color={task.status === 'completed' ? 'green' : task.status === 'running' ? 'blue' : task.status === 'failed' ? 'red' : 'default'}>
                        {task.status === 'completed' ? '已完成' : task.status === 'running' ? '运行中' : task.status === 'failed' ? '失败' : '待执行'}
                      </Tag>
                    </Space>
                  }
                  description={
                    <div>
                      {task.current_step && (
                        <Text type="secondary">{STEP_LABELS[task.current_step] || task.current_step}</Text>
                      )}
                      {task.progress !== undefined && task.progress > 0 && (
                        <Progress percent={task.progress} size="small" style={{ maxWidth: 200, marginTop: 4 }} />
                      )}
                      {task.results_summary && (
                        <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 12 }}>
                          {task.results_summary}
                        </Paragraph>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  );
};

export default Dashboard;
