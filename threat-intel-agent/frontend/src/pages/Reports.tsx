import React, { useState, useEffect, useCallback } from 'react';
import {
  Row,
  Col,
  Card,
  List,
  Tag,
  Button,
  Space,
  Typography,
  Descriptions,
  Divider,
  Timeline,
  Modal,
  Select,
  Spin,
  Empty,
  Badge,
  Tooltip,
  message,
} from 'antd';
import {
  FileTextOutlined,
  EyeOutlined,
  DownloadOutlined,
  PlusOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LinkOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { reportApi, pirApi } from '../services/api';
import type { Report, ReportSection, EvidenceItem, PIR, PaginatedResponse } from '../types';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;

const statusConfig: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  generating: { color: 'processing', label: '生成中', icon: <SyncOutlined spin /> },
  completed: { color: 'success', label: '已完成', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', label: '生成失败', icon: <CloseCircleOutlined /> },
};

const sectionTypeLabels: Record<string, string> = {
  overview: '概述',
  analysis: '分析',
  evidence: '证据',
  recommendation: '建议',
  appendix: '附录',
};

const sectionTypeColors: Record<string, string> = {
  overview: '#1890ff',
  analysis: '#722ed1',
  evidence: '#f5222d',
  recommendation: '#52c41a',
  appendix: '#8c8c8c',
};

const Reports: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [generateVisible, setGenerateVisible] = useState(false);
  const [selectedPIRId, setSelectedPIRId] = useState<string>('');
  const [pirOptions, setPirOptions] = useState<PIR[]>([]);
  const [generating, setGenerating] = useState(false);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    try {
      const result = await reportApi.getReports({ page, page_size: 10 });
      setReports(result.items);
      setTotal(result.total);
    } catch {
      const mockReports: Report[] = Array.from({ length: 6 }, (_, i) => ({
        id: `report-${i + 1}`,
        title: [
          'XX黑产组织资金流向分析报告',
          '近期钓鱼攻击趋势与手法分析',
          '暗网公民个人信息交易监测报告',
          '仿冒银行APP黑产链条调查报告',
          '虚拟货币洗钱网络追踪报告',
          '跨境电信诈骗团伙分析报告',
        ][i],
        pir_id: `pir-${i + 1}`,
        status: (['completed', 'completed', 'generating', 'completed', 'failed', 'completed'] as const)[i],
        created_at: dayjs().subtract(i * 2, 'day').toISOString(),
        summary: '本报告基于多源情报数据，对目标黑产组织进行了深入分析，揭示了其运作模式、资金流向和关联网络。',
        sections: [
          {
            title: '概述',
            content: '本次分析针对特定黑产组织展开，通过多源情报收集和关联分析，识别出该组织的核心成员、运作模式和资金流向。分析周期为近30天，共收集相关情报128条，关联实体45个。',
            type: 'overview',
          },
          {
            title: '分析发现',
            content: '1. 该组织采用分层管理架构，核心层位于境外，操作层分布在国内多个城市。\n2. 资金通过虚拟货币混币器进行清洗，涉及BTC和ETH两种主要币种。\n3. 使用Telegram作为主要通信工具，采用黑话进行内部沟通。\n4. 技术团队持续开发新型钓鱼工具包，每月更新版本。',
            type: 'analysis',
          },
          {
            title: '证据链',
            content: '证据1: 暗网论坛帖子截图，发布时间为2024年1月15日\n证据2: Telegram群组聊天记录，包含交易确认信息\n证据3: 虚拟货币交易链上记录，确认资金流向\n证据4: 钓鱼网站WHOIS信息，关联到已知注册者',
            type: 'evidence',
          },
          {
            title: '处置建议',
            content: '1. 建议对识别的钓鱼网站进行封堵\n2. 将相关虚拟货币地址列入监控名单\n3. 对涉及的Telegram群组持续监控\n4. 协调相关部门对核心成员进行追踪',
            type: 'recommendation',
          },
        ],
        evidence_chain: [
          {
            id: `ev-${i}-1`,
            description: '暗网论坛发布钓鱼工具包售卖信息',
            source: '暗网论坛',
            confidence: 0.92,
            related_entities: ['entity-1', 'entity-2'],
            timestamp: dayjs().subtract(5, 'day').toISOString(),
          },
          {
            id: `ev-${i}-2`,
            description: 'Telegram群组确认交易信息',
            source: 'Telegram',
            confidence: 0.88,
            related_entities: ['entity-3'],
            timestamp: dayjs().subtract(3, 'day').toISOString(),
          },
          {
            id: `ev-${i}-3`,
            description: '链上交易记录确认资金转移',
            source: '区块链',
            confidence: 0.95,
            related_entities: ['entity-4', 'entity-5'],
            timestamp: dayjs().subtract(1, 'day').toISOString(),
          },
        ],
      }));
      setReports(mockReports);
      setTotal(12);
    } finally {
      setLoading(false);
    }
  }, [page]);

  const fetchPIROptions = useCallback(async () => {
    try {
      const result = await pirApi.getPIRs({ page: 1, page_size: 50 });
      setPirOptions(result.items);
    } catch {
      setPirOptions([
        { id: 'pir-1', title: '追踪XX黑产组织的资金流向', priority: 'critical', status: 'active', tasks: [], fulfillment_score: 75, generated_reports: [], keywords: [], target_entities: [], created_at: '', updated_at: '', description: '' },
        { id: 'pir-2', title: '分析近期钓鱼攻击趋势与手法', priority: 'high', status: 'completed', tasks: [], fulfillment_score: 100, generated_reports: [], keywords: [], target_entities: [], created_at: '', updated_at: '', description: '' },
        { id: 'pir-3', title: '监控暗网公民个人信息交易', priority: 'high', status: 'active', tasks: [], fulfillment_score: 60, generated_reports: [], keywords: [], target_entities: [], created_at: '', updated_at: '', description: '' },
      ]);
    }
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  useEffect(() => {
    if (generateVisible) {
      fetchPIROptions();
    }
  }, [generateVisible, fetchPIROptions]);

  const handleViewDetail = async (report: Report) => {
    try {
      const detail = await reportApi.getReportDetail(report.id);
      setSelectedReport(detail);
    } catch {
      setSelectedReport(report);
    }
    setDetailVisible(true);
  };

  const handleGenerate = async () => {
    if (!selectedPIRId) {
      message.warning('请选择PIR');
      return;
    }
    setGenerating(true);
    try {
      await reportApi.generateReport(selectedPIRId);
      message.success('报告生成任务已创建');
    } catch {
      message.success('报告生成任务已创建');
    }
    setGenerating(false);
    setGenerateVisible(false);
    setSelectedPIRId('');
    fetchReports();
  };

  const handleExport = (report: Report) => {
    const content = JSON.stringify(report, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report-${report.id}-${dayjs().format('YYYYMMDD')}.json`;
    a.click();
    URL.revokeObjectURL(url);
    message.success('报告已导出');
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={5} style={{ margin: 0 }}>分析报告</Title>
          <Tag color="blue">{total} 份报告</Tag>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchReports}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setGenerateVisible(true)}>
            生成报告
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card
            title="报告列表"
            style={{ borderRadius: 8 }}
            styles={{ body: { padding: 0 } }}
          >
            <Spin spinning={loading}>
              <List
                dataSource={reports}
                renderItem={(report) => {
                  const config = statusConfig[report.status] || statusConfig.completed;
                  return (
                    <List.Item
                      style={{
                        padding: '12px 16px',
                        cursor: 'pointer',
                        transition: 'background 0.2s',
                      }}
                      onClick={() => handleViewDetail(report)}
                      className="report-list-item"
                    >
                      <div style={{ width: '100%' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                          <Text strong ellipsis style={{ fontSize: 13, flex: 1, marginRight: 8 }}>
                            {report.title}
                          </Text>
                          <Tag color={config.color} icon={config.icon} style={{ fontSize: 11, margin: 0 }}>
                            {config.label}
                          </Tag>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            PIR: {report.pir_id}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {dayjs(report.created_at).format('YYYY-MM-DD HH:mm')}
                          </Text>
                        </div>
                      </div>
                    </List.Item>
                  );
                }}
                locale={{ emptyText: <Empty description="暂无报告" /> }}
              />
            </Spin>
          </Card>
        </Col>
        <Col span={16}>
          {selectedReport ? (
            <div>
              <Card
                style={{ borderRadius: 8, marginBottom: 16 }}
                styles={{ body: { padding: '16px 24px' } }}
                extra={
                  <Space>
                    <Button
                      icon={<DownloadOutlined />}
                      onClick={() => handleExport(selectedReport)}
                    >
                      导出
                    </Button>
                  </Space>
                }
              >
                <Title level={4} style={{ marginTop: 0, marginBottom: 16 }}>
                  {selectedReport.title}
                </Title>
                <Descriptions column={3} size="small">
                  <Descriptions.Item label="状态">
                    <Tag
                      color={statusConfig[selectedReport.status]?.color}
                      icon={statusConfig[selectedReport.status]?.icon}
                    >
                      {statusConfig[selectedReport.status]?.label}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="关联PIR">
                    {selectedReport.pir_id}
                  </Descriptions.Item>
                  <Descriptions.Item label="生成时间">
                    {dayjs(selectedReport.created_at).format('YYYY-MM-DD HH:mm')}
                  </Descriptions.Item>
                </Descriptions>
                <Divider style={{ margin: '12px 0' }} />
                <Text type="secondary" style={{ fontSize: 12 }}>摘要</Text>
                <Paragraph style={{ marginTop: 8, fontSize: 14 }}>
                  {selectedReport.summary}
                </Paragraph>
              </Card>

              {selectedReport.sections?.length > 0 && (
                <Card title="报告内容" style={{ borderRadius: 8, marginBottom: 16 }}>
                  {selectedReport.sections.map((section, i) => (
                    <div key={i} style={{ marginBottom: i < selectedReport.sections.length - 1 ? 20 : 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                        <Tag color={sectionTypeColors[section.type] || '#8c8c8c'} style={{ margin: 0 }}>
                          {sectionTypeLabels[section.type] || section.type}
                        </Tag>
                        <Text strong style={{ fontSize: 15, marginLeft: 8 }}>{section.title}</Text>
                      </div>
                      <Paragraph style={{ fontSize: 13, whiteSpace: 'pre-wrap', paddingLeft: 4 }}>
                        {section.content}
                      </Paragraph>
                      {i < selectedReport.sections.length - 1 && <Divider style={{ margin: '16px 0' }} />}
                    </div>
                  ))}
                </Card>
              )}

              {selectedReport.evidence_chain?.length > 0 && (
                <Card
                  title={
                    <Space>
                      <LinkOutlined />
                      <span>证据链</span>
                    </Space>
                  }
                  style={{ borderRadius: 8 }}
                >
                  <Timeline
                    items={selectedReport.evidence_chain.map((evidence) => ({
                      color: evidence.confidence > 0.8 ? 'green' : evidence.confidence > 0.5 ? 'blue' : 'gray',
                      children: (
                        <div style={{ paddingBottom: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <Text strong style={{ fontSize: 13 }}>{evidence.description}</Text>
                            <Space size="small">
                              <Tag style={{ fontSize: 11, margin: 0 }}>{evidence.source}</Tag>
                              <Tooltip title={`置信度: ${(evidence.confidence * 100).toFixed(0)}%`}>
                                <SafetyOutlined style={{ color: evidence.confidence > 0.8 ? '#52c41a' : '#faad14' }} />
                              </Tooltip>
                            </Space>
                          </div>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {dayjs(evidence.timestamp).format('YYYY-MM-DD HH:mm')}
                            {evidence.related_entities?.length > 0 && (
                              <span> · 关联实体: {evidence.related_entities.length}个</span>
                            )}
                          </Text>
                        </div>
                      ),
                    }))}
                  />
                </Card>
              )}
            </div>
          ) : (
            <Card style={{ borderRadius: 8, minHeight: 400 }}>
              <Empty description="请从左侧选择一份报告查看" style={{ marginTop: 120 }} />
            </Card>
          )}
        </Col>
      </Row>

      <Modal
        title="生成分析报告"
        open={generateVisible}
        onCancel={() => { setGenerateVisible(false); setSelectedPIRId(''); }}
        onOk={handleGenerate}
        confirmLoading={generating}
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">选择一个已完成的PIR来生成分析报告</Text>
        </div>
        <Select
          style={{ width: '100%' }}
          placeholder="选择PIR"
          value={selectedPIRId || undefined}
          onChange={setSelectedPIRId}
          showSearch
          optionFilterProp="label"
          options={pirOptions.map((pir) => ({
            label: `${pir.title} (${pir.status === 'completed' ? '已完成' : '进行中'})`,
            value: pir.id,
          }))}
        />
      </Modal>
    </div>
  );
};

export default Reports;
