import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Input, Button, Space, message, Empty, Spin, Typography, Tag, List, Badge, Row, Col, Statistic, Divider, notification,
} from 'antd';
import {
  SendOutlined, ReloadOutlined, RobotOutlined, HistoryOutlined,
  CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined, SyncOutlined,
} from '@ant-design/icons';
import { agentApi, getErrorMessage } from '../services/api';
import type { TaskStatus } from '../types';
import { formatTime } from '../utils/constants';

const { Text, Paragraph } = Typography;

function addActiveTask(taskId: string) {
  try {
    const stored = sessionStorage.getItem('tia_active_tasks');
    const taskIds: string[] = stored ? JSON.parse(stored) : [];
    taskIds.push(taskId);
    sessionStorage.setItem('tia_active_tasks', JSON.stringify(taskIds));
  } catch {
    // ignore
  }
}

const Agent: React.FC = () => {
  const [query, setQuery] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<TaskStatus | null>(null);
  const [history, setHistory] = useState<{ items: unknown[]; total: number } | null>(null);
  const [agentStatus, setAgentStatus] = useState<{ agents: unknown } | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchHistory = useCallback(async () => {
    try {
      const result = await agentApi.getHistory(20);
      setHistory(result);
    } catch {
      // ignore
    }
  }, []);

  const fetchAgentStatus = useCallback(async () => {
    try {
      const result = await agentApi.getStatus();
      setAgentStatus(result);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchHistory();
    fetchAgentStatus();
  }, [fetchHistory, fetchAgentStatus]);

  const handleSubmitQuery = async () => {
    if (!query.trim()) {
      message.warning('请输入查询内容');
      return;
    }
    try {
      setSubmitting(true);
      const result = await agentApi.submitQuery(query);
      setLastResult(result);
      addActiveTask(result.task_id);
      message.success('任务已提交，可在任务列表中查看进度');
      notification.info({
        message: '任务已提交',
        description: `任务ID: ${result.task_id}，可在仪表盘查看进度`,
        duration: 5,
      });
      setQuery('');
      fetchHistory();
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleTriggerCollection = async () => {
    try {
      setSubmitting(true);
      const result = await agentApi.triggerCollection();
      addActiveTask(result.task_id);
      message.success('情报收集任务已提交，可在任务列表中查看进度');
      notification.info({
        message: '情报收集已提交',
        description: `任务ID: ${result.task_id}，可在仪表盘查看进度`,
        duration: 5,
      });
      fetchHistory();
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleTriggerAnalysis = async () => {
    try {
      setSubmitting(true);
      const result = await agentApi.triggerAnalysis();
      addActiveTask(result.task_id);
      message.success('情报分析任务已提交，可在任务列表中查看进度');
      notification.info({
        message: '情报分析已提交',
        description: `任务ID: ${result.task_id}，可在仪表盘查看进度`,
        duration: 5,
      });
      fetchHistory();
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const statusIcon: Record<string, React.ReactNode> = {
    completed: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    running: <SyncOutlined spin style={{ color: '#1890ff' }} />,
    pending: <ClockCircleOutlined style={{ color: '#faad14' }} />,
    failed: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
  };

  const statusLabel: Record<string, string> = {
    completed: '已完成',
    running: '运行中',
    pending: '待执行',
    failed: '失败',
  };

  return (
    <div>
      <Card title="Agent 查询" style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="输入查询内容..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={handleSubmitQuery}
            size="large"
            disabled={submitting}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSubmitQuery}
            loading={submitting}
            size="large"
          >
            提交
          </Button>
        </Space.Compact>

        <Divider />

        <Space>
          <Button icon={<RobotOutlined />} onClick={handleTriggerCollection} loading={submitting}>
            触发情报收集
          </Button>
          <Button icon={<RobotOutlined />} onClick={handleTriggerAnalysis} loading={submitting}>
            触发情报分析
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => { fetchHistory(); fetchAgentStatus(); }}>
            刷新状态
          </Button>
        </Space>
      </Card>

      {lastResult && (
        <Card title="最近结果" style={{ marginBottom: 16 }}>
          <Space>
            <Text>任务ID: <Text strong copyable>{lastResult.task_id}</Text></Text>
            <Tag color={lastResult.status === 'completed' ? 'green' : lastResult.status === 'failed' ? 'red' : 'blue'}>
              {lastResult.status}
            </Tag>
          </Space>
          {lastResult.message && <Paragraph><Text strong>消息: </Text>{lastResult.message}</Paragraph>}
          {lastResult.results_summary && (
            <Paragraph>
              <Text strong>结果摘要: </Text>{lastResult.results_summary}
            </Paragraph>
          )}
        </Card>
      )}

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="执行历史" extra={<a onClick={fetchHistory}><ReloadOutlined /> 刷新</a>}>
            {!history || history.total === 0 ? (
              <Empty description="暂无执行记录" />
            ) : (
              <List
                size="small"
                dataSource={(history.items as Record<string, unknown>[]) || []}
                renderItem={(item: Record<string, unknown>) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={statusIcon[(item.status as string)] || <ClockCircleOutlined />}
                      title={
                        <span>
                          <Text>{(item.query as string) || '未知任务'}</Text>
                          <Tag
                            color={(item.status as string) === 'completed' ? 'green' : (item.status as string) === 'failed' ? 'red' : 'blue'}
                            style={{ marginLeft: 8 }}
                          >
                            {statusLabel[(item.status as string)] || (item.status as string)}
                          </Tag>
                        </span>
                      }
                      description={
                        <Text type="secondary">
                          {(item.start_time as string) && formatTime(item.start_time as string)}
                          {item.duration_seconds !== undefined && ` · ${(item.duration_seconds as number).toFixed(1)}s`}
                        </Text>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="Agent 状态">
            {!agentStatus ? (
              <Empty description="暂无Agent状态" />
            ) : (
              <div>
                {typeof agentStatus.agents === 'object' && agentStatus.agents !== null ? (
                  <List
                    size="small"
                    dataSource={Object.entries(agentStatus.agents as Record<string, Record<string, unknown>>)}
                    renderItem={([name, info]) => (
                      <List.Item>
                        <List.Item.Meta
                          avatar={<RobotOutlined />}
                          title={name}
                          description={
                            <Space>
                              <Badge
                                status={(info.status as string) === 'running' ? 'processing' : (info.status as string) === 'idle' ? 'default' : 'success'}
                                text={(info.status as string) === 'running' ? '运行中' : (info.status as string) === 'idle' ? '空闲' : '完成'}
                              />
                              {info.execution_count !== undefined && (
                                <Text type="secondary">执行: {info.execution_count as number}次</Text>
                              )}
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无Agent状态信息" />
                )}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Agent;
