import React, { useState, useEffect, useCallback } from 'react';
import {
  Input,
  Select,
  DatePicker,
  Button,
  Space,
  Row,
  Col,
  Card,
  Modal,
  Form,
  message,
  Spin,
  Empty,
  Pagination,
  Tag,
  Typography,
  Descriptions,
  Divider,
  Checkbox,
  Alert,
  Skeleton,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  ExperimentOutlined,
  ClearOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import IntelCard from '../components/IntelCard';
import { intelligenceApi, extractErrorMessage } from '../services/api';
import type { Intelligence } from '../types';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;
const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const sourceTypeOptions = [
  { label: 'Telegram', value: 'telegram' },
  { label: '暗网', value: 'dark_web' },
  { label: '论坛', value: 'forum' },
  { label: '社交媒体', value: 'social_media' },
  { label: '其他', value: 'other' },
];

const threatLevelOptions = [
  { label: '严重', value: 'critical' },
  { label: '高危', value: 'high' },
  { label: '中危', value: 'medium' },
  { label: '低危', value: 'low' },
  { label: '信息', value: 'info' },
];

const sourceTypeLabels: Record<string, string> = {
  telegram: 'Telegram',
  dark_web: '暗网',
  forum: '论坛',
  social_media: '社交媒体',
  other: '其他',
};

const threatLevelLabels: Record<string, string> = {
  critical: '严重',
  high: '高危',
  medium: '中危',
  low: '低危',
  info: '信息',
};

const IntelligencePage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [intelligences, setIntelligences] = useState<Intelligence[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<string | undefined>();
  const [threatFilter, setThreatFilter] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [selectedIntel, setSelectedIntel] = useState<Intelligence | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [collectVisible, setCollectVisible] = useState(false);
  const [collectLoading, setCollectLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [collectForm] = Form.useForm();

  const fetchIntelligences = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await intelligenceApi.getIntelligences({
        query: searchQuery || undefined,
        page,
        page_size: pageSize,
        filters: {
          ...(sourceFilter ? { source_type: sourceFilter } : {}),
          ...(threatFilter ? { threat_level: threatFilter } : {}),
        },
      });
      setIntelligences(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(extractErrorMessage(err));
      setIntelligences([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, sourceFilter, threatFilter, page, pageSize]);

  useEffect(() => {
    fetchIntelligences();
  }, [fetchIntelligences]);

  const handleSearch = () => {
    setPage(1);
    fetchIntelligences();
  };

  const handleViewDetail = async (intel: Intelligence) => {
    setDetailLoading(true);
    setDetailVisible(true);
    try {
      const detail = await intelligenceApi.getIntelDetail(intel.id);
      setSelectedIntel(detail);
    } catch (err) {
      message.warning('详情加载失败，显示基本信息');
      setSelectedIntel(intel);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleAnalyze = async (intel: Intelligence) => {
    try {
      await intelligenceApi.batchAnalyze([intel.id]);
      message.success('已提交分析任务');
    } catch (err) {
      message.error(`提交失败: ${extractErrorMessage(err)}`);
    }
  };

  const handleAddToGraph = (intel: Intelligence) => {
    message.info(`已将情报 ${intel.title} 加入图谱分析队列`);
  };

  const handleCollect = async (values: Record<string, unknown>) => {
    setCollectLoading(true);
    try {
      await intelligenceApi.createIntel(values as Partial<Intelligence>);
      message.success('情报采集任务已创建');
      setCollectVisible(false);
      collectForm.resetFields();
      fetchIntelligences();
    } catch (err) {
      message.error(`创建失败: ${extractErrorMessage(err)}`);
    } finally {
      setCollectLoading(false);
    }
  };

  const handleBatchAnalyze = async () => {
    if (selectedIds.length === 0) {
      message.warning('请先选择要分析的情报');
      return;
    }
    try {
      await intelligenceApi.batchAnalyze(selectedIds);
      message.success(`已提交 ${selectedIds.length} 条情报的分析任务`);
      setSelectedIds([]);
    } catch (err) {
      message.error(`批量分析失败: ${extractErrorMessage(err)}`);
    }
  };

  const handleBatchClean = async () => {
    if (selectedIds.length === 0) {
      message.warning('请先选择要清洗的情报');
      return;
    }
    try {
      await intelligenceApi.batchClean(selectedIds);
      message.success(`已提交 ${selectedIds.length} 条情报的清洗任务`);
      setSelectedIds([]);
    } catch (err) {
      message.error(`批量清洗失败: ${extractErrorMessage(err)}`);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  return (
    <div>
      <Card style={{ borderRadius: 8, marginBottom: 16 }} styles={{ body: { padding: '16px 20px' } }}>
        <Row gutter={[12, 12]} align="middle">
          <Col flex="auto">
            <Space wrap size="middle">
              <Input.Search
                placeholder="搜索情报内容、标题、标签..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onSearch={handleSearch}
                style={{ width: 320 }}
                allowClear
                enterButton={<SearchOutlined />}
              />
              <Select
                placeholder="来源类型"
                value={sourceFilter}
                onChange={setSourceFilter}
                options={sourceTypeOptions}
                allowClear
                style={{ width: 140 }}
              />
              <Select
                placeholder="威胁等级"
                value={threatFilter}
                onChange={setThreatFilter}
                options={threatLevelOptions}
                allowClear
                style={{ width: 120 }}
              />
              <RangePicker
                value={dateRange}
                onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
                style={{ width: 260 }}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              {selectedIds.length > 0 && (
                <>
                  <Button icon={<ExperimentOutlined />} onClick={handleBatchAnalyze}>
                    批量分析 ({selectedIds.length})
                  </Button>
                  <Button icon={<ClearOutlined />} onClick={handleBatchClean}>
                    批量清洗
                  </Button>
                </>
              )}
              <Button icon={<ReloadOutlined />} onClick={fetchIntelligences}>
                刷新
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setCollectVisible(true)}>
                采集情报
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {error && (
        <Alert
          message="数据加载失败"
          description={error}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={fetchIntelligences}>
              重试
            </Button>
          }
        />
      )}

      {loading && intelligences.length === 0 ? (
        <div style={{ padding: '20px 0' }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} style={{ marginBottom: 12, borderRadius: 6 }}>
              <Skeleton active paragraph={{ rows: 2 }} />
            </Card>
          ))}
        </div>
      ) : intelligences.length > 0 ? (
        <Spin spinning={loading}>
          {intelligences.map((intel) => (
            <div key={intel.id} style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: 4, top: 20, zIndex: 1 }}>
                <Checkbox
                  checked={selectedIds.includes(intel.id)}
                  onChange={() => toggleSelect(intel.id)}
                />
              </div>
              <div style={{ marginLeft: 24 }}>
                <IntelCard
                  intel={intel}
                  onViewDetail={handleViewDetail}
                  onAnalyze={handleAnalyze}
                  onAddToGraph={handleAddToGraph}
                />
              </div>
            </div>
          ))}
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              showSizeChanger
              showQuickJumper
              showTotal={(t) => `共 ${t} 条情报`}
              onChange={(p, ps) => {
                setPage(p);
                setPageSize(ps);
              }}
            />
          </div>
        </Spin>
      ) : (
        <Empty description={error ? '数据加载失败' : '暂无情报数据'} />
      )}

      <Modal
        title="情报详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        width={720}
        footer={[
          <Button key="close" onClick={() => setDetailVisible(false)}>
            关闭
          </Button>,
          <Button key="analyze" type="primary" icon={<ExperimentOutlined />} onClick={() => { if (selectedIntel) handleAnalyze(selectedIntel); }} disabled={!selectedIntel}>
            深度分析
          </Button>,
        ]}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" tip="加载详情..." />
          </div>
        ) : selectedIntel ? (
          <div>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="标题" span={2}>
                <Text strong>{selectedIntel.title}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                {sourceTypeLabels[selectedIntel.source_type] || selectedIntel.source_type}
              </Descriptions.Item>
              <Descriptions.Item label="威胁等级">
                <Tag color={
                  selectedIntel.threat_level === 'critical' ? 'red' :
                  selectedIntel.threat_level === 'high' ? 'orange' :
                  selectedIntel.threat_level === 'medium' ? 'gold' :
                  selectedIntel.threat_level === 'low' ? 'green' : 'blue'
                }>
                  {threatLevelLabels[selectedIntel.threat_level] || selectedIntel.threat_level}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="采集时间">
                {dayjs(selectedIntel.collected_at).format('YYYY-MM-DD HH:mm:ss')}
              </Descriptions.Item>
              <Descriptions.Item label="处理状态">
                {selectedIntel.is_processed ? <Tag color="green">已处理</Tag> : <Tag color="orange">待处理</Tag>}
              </Descriptions.Item>
            </Descriptions>
            <Divider orientation="left">原始内容</Divider>
            <Paragraph style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, fontSize: 13 }}>
              {selectedIntel.content}
            </Paragraph>
            {selectedIntel.decoded_content && (
              <>
                <Divider orientation="left">解码内容</Divider>
                <Paragraph style={{ background: '#e6f7ff', padding: 12, borderRadius: 4, fontSize: 13, borderLeft: '3px solid #1890ff' }}>
                  {selectedIntel.decoded_content}
                </Paragraph>
              </>
            )}
            {selectedIntel.entities?.length > 0 && (
              <>
                <Divider orientation="left">关联实体</Divider>
                <Space wrap>
                  {selectedIntel.entities.map((entity) => (
                    <Tag key={entity.id} color="processing">
                      {entity.name} ({entity.entity_type})
                    </Tag>
                  ))}
                </Space>
              </>
            )}
          </div>
        ) : null}
      </Modal>

      <Modal
        title="采集新情报"
        open={collectVisible}
        onCancel={() => setCollectVisible(false)}
        onOk={() => collectForm.submit()}
        confirmLoading={collectLoading}
        width={600}
      >
        <Form form={collectForm} layout="vertical" onFinish={handleCollect}>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入情报标题' }]}>
            <Input placeholder="输入情报标题" />
          </Form.Item>
          <Form.Item name="source" label="来源" rules={[{ required: true, message: '请输入情报来源' }]}>
            <Input placeholder="输入情报来源" />
          </Form.Item>
          <Form.Item name="source_type" label="来源类型" rules={[{ required: true, message: '请选择来源类型' }]}>
            <Select options={sourceTypeOptions} placeholder="选择来源类型" />
          </Form.Item>
          <Form.Item name="threat_level" label="威胁等级" initialValue="medium">
            <Select options={threatLevelOptions} />
          </Form.Item>
          <Form.Item name="content" label="情报内容" rules={[{ required: true, message: '请输入情报内容' }]}>
            <TextArea rows={6} placeholder="输入情报内容，支持粘贴原始黑话文本" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default IntelligencePage;
