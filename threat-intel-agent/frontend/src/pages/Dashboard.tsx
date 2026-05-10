import React, { useState, useEffect } from 'react';
import { Row, Col, Card, List, Tag, Badge, Progress, Typography, Space, Timeline, Empty, Spin, Tooltip, Divider } from 'antd';
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
} from '@ant-design/icons';
import StatCard from '../components/StatCard';
import IntelCard from '../components/IntelCard';
import { dashboardApi } from '../services/api';
import type { DashboardStats, Intelligence, AgentStatus, ExecutionRecord } from '../types';
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
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const data = await dashboardApi.getDashboardStats();
        setStats(data);
      } catch {
        setStats({
          total_intelligence: 1284,
          active_pirs: 23,
          threat_alerts: 47,
          graph_nodes: 3562,
          threat_level_distribution: {
            critical: 12,
            high: 35,
            medium: 89,
            low: 156,
            info: 992,
          },
          source_type_distribution: {
            telegram: 420,
            dark_web: 280,
            forum: 350,
            social_media: 180,
            other: 54,
          },
          recent_intelligence: [
            {
              id: '1',
              title: '某暗网论坛出现新型钓鱼工具包售卖信息',
              content: '检测到暗网论坛新帖，售卖针对金融平台的钓鱼工具包，包含模板和部署脚本',
              source: '暗网论坛',
              source_type: 'dark_web',
              threat_level: 'high',
              collected_at: dayjs().subtract(1, 'hour').toISOString(),
              is_processed: true,
              entities: [],
              tags: ['钓鱼', '金融'],
            },
            {
              id: '2',
              title: 'Telegram群组传播公民个人信息数据集',
              content: '某Telegram群组正在传播包含约50万条公民个人信息的数据集',
              source: 'Telegram',
              source_type: 'telegram',
              threat_level: 'critical',
              collected_at: dayjs().subtract(2, 'hour').toISOString(),
              is_processed: true,
              entities: [],
              tags: ['数据泄露', '个人信息'],
            },
            {
              id: '3',
              title: '发现仿冒银行APP的安卓恶意软件',
              content: '监测到仿冒某大型银行APP的安卓恶意软件，具有短信拦截和键盘记录功能',
              source: '社交媒体',
              source_type: 'social_media',
              threat_level: 'high',
              collected_at: dayjs().subtract(3, 'hour').toISOString(),
              is_processed: false,
              entities: [],
              tags: ['恶意软件', '银行'],
            },
            {
              id: '4',
              title: '某黑产团伙使用新型洗钱通道',
              content: '追踪到某黑产团伙通过虚拟货币混币器进行洗钱的新型通道',
              source: 'Telegram',
              source_type: 'telegram',
              threat_level: 'medium',
              collected_at: dayjs().subtract(5, 'hour').toISOString(),
              is_processed: true,
              entities: [],
              tags: ['洗钱', '虚拟货币'],
            },
            {
              id: '5',
              title: '论坛出现新型DDoS攻击服务广告',
              content: '某黑客论坛出现提供DDoS攻击服务的广告，声称可突破主流CDN防护',
              source: '黑客论坛',
              source_type: 'forum',
              threat_level: 'medium',
              collected_at: dayjs().subtract(6, 'hour').toISOString(),
              is_processed: true,
              entities: [],
              tags: ['DDoS', '攻击服务'],
            },
          ] as Intelligence[],
          agent_statuses: [
            { name: '收集Agent', status: 'running', current_task: '监控Telegram群组', execution_count: 156 },
            { name: '清洗Agent', status: 'idle', execution_count: 89 },
            { name: '分析Agent', status: 'running', current_task: '分析钓鱼工具包关联', execution_count: 67 },
            { name: '图谱Agent', status: 'idle', execution_count: 45 },
          ] as AgentStatus[],
          recent_executions: [
            { id: '1', query: '分析近期钓鱼攻击趋势', status: 'completed', started_at: dayjs().subtract(1, 'hour').toISOString(), agent_name: '分析Agent', result_summary: '发现3个新钓鱼团伙' },
            { id: '2', query: '追踪虚拟货币洗钱路径', status: 'running', started_at: dayjs().subtract(30, 'minute').toISOString(), agent_name: '图谱Agent' },
            { id: '3', query: '关联暗网数据泄露事件', status: 'completed', started_at: dayjs().subtract(2, 'hour').toISOString(), agent_name: '分析Agent', result_summary: '关联5个数据泄露源' },
          ] as ExecutionRecord[],
        });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="加载态势数据..." />
      </div>
    );
  }

  if (!stats) return null;

  const totalThreats = Object.values(stats.threat_level_distribution).reduce((a, b) => a + b, 0) || 1;

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="情报总量"
            value={stats.total_intelligence}
            icon={<SearchOutlined />}
            color="#1890ff"
            trend="up"
            trendValue="12%"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="活跃PIR"
            value={stats.active_pirs}
            icon={<AimOutlined />}
            color="#722ed1"
            trend="up"
            trendValue="5%"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="威胁告警"
            value={stats.threat_alerts}
            icon={<AlertOutlined />}
            color="#ff4d4f"
            trend="down"
            trendValue="8%"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="图谱节点"
            value={stats.graph_nodes}
            icon={<ApartmentOutlined />}
            color="#52c41a"
            trend="up"
            trendValue="15%"
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
            {Object.entries(stats.threat_level_distribution || {}).map(([level, count]) => {
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
            })}
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
            <List
              dataSource={stats.agent_statuses || []}
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
            <Timeline
              items={(stats.recent_executions || []).map((exec: ExecutionRecord) => ({
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
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
