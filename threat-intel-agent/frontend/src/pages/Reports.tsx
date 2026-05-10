import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select, message,
  Empty, Spin, Typography, Popconfirm, Tooltip,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, EyeOutlined,
  FileTextOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { reportsApi, getErrorMessage } from '../services/api';
import type { Report, PaginatedResponse } from '../types';

const { Text, Paragraph } = Typography;

const REPORT_TYPE_CONFIG: Record<string, { color: string; label: string }> = {
  threat_summary: { color: 'red', label: '威胁摘要' },
  entity_analysis: { color: 'blue', label: '实体分析' },
  pir_fulfillment: { color: 'green', label: 'PIR完成报告' },
  trend_analysis: { color: 'purple', label: '趋势分析' },
};

const REPORT_STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  draft: { color: 'default', label: '草稿' },
  generating: { color: 'processing', label: '生成中' },
  completed: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '生成失败' },
};

const Reports: React.FC = () => {
  const [reports, setReports] = useState<PaginatedResponse<Report>>({ items: [], total: 0, offset: 0, limit: 20 });
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [form] = Form.useForm();

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      const result = await reportsApi.list({
        status: statusFilter,
        offset: (page - 1) * pageSize,
        limit: pageSize,
      });
      setReports(result);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page, pageSize]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const handleGenerate = async (values: { title: string; report_type?: string }) => {
    try {
      await reportsApi.generate({
        title: values.title,
        report_type: values.report_type || 'threat_summary',
      });
      message.success('报告生成任务已提交');
      setGenerateModalOpen(false);
      form.resetFields();
      fetchReports();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleDelete = async (reportId: string) => {
    try {
      await reportsApi.delete(reportId);
      message.success('删除成功');
      fetchReports();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleViewDetail = async (reportId: string) => {
    setDetailModalOpen(true);
    setDetailLoading(true);
    try {
      const report = await reportsApi.get(reportId);
      setSelectedReport(report);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setDetailLoading(false);
    }
  };

  const handleExport = async (reportId: string) => {
    try {
      const result = await reportsApi.export(reportId);
      const blob = new Blob([result.content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${result.title || 'report'}.md`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (err) {
      message.error(getErrorMessage(err));
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
      title: '类型',
      dataIndex: 'report_type',
      key: 'report_type',
      width: 120,
      render: (type: string) => {
        const config = REPORT_TYPE_CONFIG[type];
        return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{type}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config = REPORT_STATUS_CONFIG[status];
        return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{status}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (time: string | undefined) => time ? new Date(time).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: Report) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record.id)} />
          </Tooltip>
          {record.status === 'completed' && (
            <Tooltip title="导出">
              <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => handleExport(record.id)} />
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
              options={Object.entries(REPORT_STATUS_CONFIG).map(([value, config]) => ({ value, label: config.label }))}
              allowClear
              style={{ width: 130 }}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchReports}>刷新</Button>
          </Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setGenerateModalOpen(true)}>
            生成报告
          </Button>
        </Space>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={reports.items}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: <Empty description="暂无报告数据" /> }}
          pagination={{
            current: page,
            pageSize,
            total: reports.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
        />
      </Card>

      <Modal
        title="生成报告"
        open={generateModalOpen}
        onCancel={() => { setGenerateModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        okText="生成"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleGenerate}>
          <Form.Item name="title" label="报告标题" rules={[{ required: true, message: '请输入报告标题' }]}>
            <Input placeholder="输入报告标题" />
          </Form.Item>
          <Form.Item name="report_type" label="报告类型" initialValue="threat_summary">
            <Select options={Object.entries(REPORT_TYPE_CONFIG).map(([value, config]) => ({ value, label: config.label }))} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="报告详情"
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setSelectedReport(null); }}
        footer={selectedReport?.status === 'completed' ? (
          <Button icon={<DownloadOutlined />} type="primary" onClick={() => selectedReport && handleExport(selectedReport.id)}>
            导出
          </Button>
        ) : null}
        width={700}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : selectedReport ? (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Tag color={REPORT_TYPE_CONFIG[selectedReport.report_type]?.color}>
                  {REPORT_TYPE_CONFIG[selectedReport.report_type]?.label || selectedReport.report_type}
                </Tag>
                <Tag color={REPORT_STATUS_CONFIG[selectedReport.status]?.color}>
                  {REPORT_STATUS_CONFIG[selectedReport.status]?.label || selectedReport.status}
                </Tag>
              </Space>
            </div>

            <Paragraph><Text strong>标题: </Text>{selectedReport.title}</Paragraph>

            {selectedReport.content ? (
              <div>
                <Text strong>内容:</Text>
                <div style={{
                  marginTop: 8,
                  padding: 16,
                  background: '#f5f5f5',
                  borderRadius: 4,
                  maxHeight: 400,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                }}>
                  {selectedReport.content}
                </div>
              </div>
            ) : (
              <Empty description="报告内容尚未生成" style={{ marginTop: 20 }} />
            )}
          </div>
        ) : (
          <Empty description="未找到报告数据" />
        )}
      </Modal>
    </div>
  );
};

export default Reports;
