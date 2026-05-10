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
  Alert,
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
import { reportApi, pirApi, extractErrorMessage } from '../services/api';
import type { Report, PIR } from '../types';
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
  const [error, setError] = useState<string | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [generateVisible, setGenerateVisible] = useState(false);
  const [selectedPIRId, setSelectedPIRId] = useState<string>('');
  const [pirOptions, setPirOptions] = useState<PIR[]>([]);
  const [pirLoading, setPirLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await reportApi.getReports({ page, page_size: 10 });
      setReports(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(extractErrorMessage(err));
      setReports([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page]);

  const fetchPIROptions = useCallback(async () => {
    setPirLoading(true);
    try {
      const result = await pirApi.getPIRs({ page: 1, page_size: 50 });
      setPirOptions(result.items);
    } catch (err) {
      message.warning('PIR列表加载失败');
      setPirOptions([]);
    } finally {
      setPirLoading(false);
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
    setDetailLoading(true);
    try {
      const detail = await reportApi.getReportDetail(report.id);
      setSelectedReport(detail);
    } catch (err) {
      message.warning('报告详情加载失败，显示基本信息');
      setSelectedReport(report);
    } finally {
      setDetailLoading(false);
    }
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
    } catch (err) {
      message.error(`生成失败: ${extractErrorMessage(err)}`);
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
      {error && (
        <Alert
          message="数据加载失败"
          description={error}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={fetchReports}>
              重试
            </Button>
          }
        />
      )}

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
              {reports.length > 0 ? (
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
                          background: selectedReport?.id === report.id ? '#f0f5ff' : undefined,
                        }}
                        onClick={() => handleViewDetail(report)}
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
              ) : (
                <Empty description="暂无报告" style={{ padding: 40 }} />
              )}
            </Spin>
          </Card>
        </Col>
        <Col span={16}>
          {detailLoading ? (
            <Card style={{ borderRadius: 8, minHeight: 400 }}>
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
                <Spin size="large" tip="加载报告详情..." />
              </div>
            </Card>
          ) : selectedReport ? (
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
                  {selectedReport.summary || '暂无摘要'}
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
          loading={pirLoading}
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
