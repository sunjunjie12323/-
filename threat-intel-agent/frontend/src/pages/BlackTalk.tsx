import React, { useState, useEffect, useCallback } from 'react';
import {
  Row,
  Col,
  Card,
  Input,
  Select,
  Button,
  Space,
  Table,
  Tag,
  Typography,
  Modal,
  Form,
  Tabs,
  Progress,
  Statistic,
  Divider,
  message,
  Spin,
  Empty,
  Alert,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  TranslationOutlined,
  ReloadOutlined,
  BulbOutlined,
  RobotOutlined,
  BookOutlined,
} from '@ant-design/icons';
import { blackTalkApi, extractErrorMessage } from '../services/api';
import type { BlackTalkTerm, DecodeResult } from '../types';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const categoryLabels: Record<string, string> = {
  fraud: '诈骗',
  gambling: '赌博',
  money_laundering: '洗钱',
  phishing: '钓鱼',
  malware: '恶意软件',
  data_theft: '数据窃取',
  drug: '毒品',
  other: '其他',
};

const categoryColors: Record<string, string> = {
  fraud: '#f5222d',
  gambling: '#fa8c16',
  money_laundering: '#722ed1',
  phishing: '#1890ff',
  malware: '#eb2f96',
  data_theft: '#13c2c2',
  drug: '#52c41a',
  other: '#8c8c8c',
};

const BlackTalk: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [terms, setTerms] = useState<BlackTalkTerm[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [addVisible, setAddVisible] = useState(false);
  const [addLoading, setAddLoading] = useState(false);
  const [decodeText, setDecodeText] = useState('');
  const [decodeResult, setDecodeResult] = useState<DecodeResult | null>(null);
  const [decoding, setDecoding] = useState(false);
  const [addForm] = Form.useForm();
  const [activeTab, setActiveTab] = useState('dictionary');

  const fetchTerms = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await blackTalkApi.getBlackTalkTerms({
        query: searchQuery || undefined,
        page,
        page_size: pageSize,
        filters: categoryFilter ? { category: categoryFilter } : undefined,
      });
      setTerms(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(extractErrorMessage(err));
      setTerms([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, categoryFilter, page, pageSize]);

  useEffect(() => {
    fetchTerms();
  }, [fetchTerms]);

  const handleSearch = () => {
    setPage(1);
    fetchTerms();
  };

  const handleAddTerm = async (values: Record<string, unknown>) => {
    setAddLoading(true);
    try {
      await blackTalkApi.addBlackTalkTerm(values as Partial<BlackTalkTerm>);
      message.success('术语添加成功');
    } catch (err) {
      message.error(`添加失败: ${extractErrorMessage(err)}`);
    }
    setAddLoading(false);
    setAddVisible(false);
    addForm.resetFields();
    fetchTerms();
  };

  const handleDecode = async () => {
    if (!decodeText.trim()) {
      message.warning('请输入要解码的文本');
      return;
    }
    setDecoding(true);
    try {
      const result = await blackTalkApi.decodeText(decodeText);
      setDecodeResult(result);
    } catch (err) {
      message.error(`解码失败: ${extractErrorMessage(err)}`);
    } finally {
      setDecoding(false);
    }
  };

  const columns = [
    {
      title: '术语',
      dataIndex: 'term',
      key: 'term',
      width: 100,
      render: (term: string, record: BlackTalkTerm) => (
        <Space>
          <Text strong style={{ fontSize: 14 }}>{term}</Text>
          {record.is_auto_learned && (
            <RobotOutlined style={{ color: '#1890ff', fontSize: 12 }} />
          )}
        </Space>
      ),
    },
    {
      title: '释义',
      dataIndex: 'meaning',
      key: 'meaning',
      ellipsis: true,
      render: (meaning: string) => (
        <Text style={{ fontSize: 13 }}>{meaning}</Text>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (category: string) => (
        <Tag color={categoryColors[category] || 'default'}>
          {categoryLabels[category] || category}
        </Tag>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (confidence: number) => (
        <Progress
          percent={Math.round(confidence * 100)}
          size="small"
          strokeColor={confidence > 0.8 ? '#52c41a' : confidence > 0.5 ? '#faad14' : '#ff4d4f'}
        />
      ),
    },
    {
      title: '使用频次',
      dataIndex: 'usage_count',
      key: 'usage_count',
      width: 90,
      sorter: (a: BlackTalkTerm, b: BlackTalkTerm) => a.usage_count - b.usage_count,
      render: (count: number) => <Text style={{ fontSize: 12 }}>{count}</Text>,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 90,
      render: (source: string, record: BlackTalkTerm) => (
        <Tag color={record.is_auto_learned ? 'blue' : 'default'} style={{ fontSize: 11 }}>
          {source}
        </Tag>
      ),
    },
  ];

  const categoryCountMap = terms.reduce<Record<string, number>>((acc, term) => {
    acc[term.category] = (acc[term.category] || 0) + 1;
    return acc;
  }, {});

  const autoLearnedCount = terms.filter((t) => t.is_auto_learned).length;
  const avgConfidence = terms.length > 0
    ? terms.reduce((sum, t) => sum + t.confidence, 0) / terms.length
    : 0;

  return (
    <div>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'dictionary',
            label: (
              <Space>
                <BookOutlined />
                术语词典
              </Space>
            ),
            children: (
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
                      <Button size="small" onClick={fetchTerms}>
                        重试
                      </Button>
                    }
                  />
                )}

                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                  <Col span={6}>
                    <Card size="small" style={{ borderRadius: 8 }}>
                      <Statistic title="术语总量" value={total} prefix={<BookOutlined />} valueStyle={{ color: '#1890ff' }} />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" style={{ borderRadius: 8 }}>
                      <Statistic title="自动学习" value={autoLearnedCount} prefix={<RobotOutlined />} valueStyle={{ color: '#722ed1' }} />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" style={{ borderRadius: 8 }}>
                      <Statistic title="分类数" value={Object.keys(categoryCountMap).length} prefix={<BulbOutlined />} valueStyle={{ color: '#fa8c16' }} />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" style={{ borderRadius: 8 }}>
                      <Statistic
                        title="平均置信度"
                        value={Math.round(avgConfidence * 100)}
                        suffix="%"
                        prefix={<TranslationOutlined />}
                        valueStyle={{ color: '#52c41a' }}
                      />
                    </Card>
                  </Col>
                </Row>

                <Card style={{ borderRadius: 8, marginBottom: 16 }} styles={{ body: { padding: '12px 20px' } }}>
                  <Space wrap size="middle">
                    <Input.Search
                      placeholder="搜索黑话术语..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onSearch={handleSearch}
                      style={{ width: 300 }}
                      allowClear
                      enterButton={<SearchOutlined />}
                    />
                    <Select
                      placeholder="分类过滤"
                      value={categoryFilter}
                      onChange={(val) => { setCategoryFilter(val); setPage(1); }}
                      options={Object.entries(categoryLabels).map(([value, label]) => ({
                        label,
                        value,
                      }))}
                      allowClear
                      style={{ width: 140 }}
                    />
                    <Button icon={<ReloadOutlined />} onClick={fetchTerms}>刷新</Button>
                    <Button icon={<PlusOutlined />} onClick={() => setAddVisible(true)}>添加术语</Button>
                    <Button
                      type="primary"
                      icon={<TranslationOutlined />}
                      onClick={() => setActiveTab('decode')}
                    >
                      解码工具
                    </Button>
                  </Space>
                </Card>

                <Table
                  columns={columns}
                  dataSource={terms}
                  rowKey="id"
                  loading={loading}
                  locale={{ emptyText: error ? <Empty description="数据加载失败" /> : <Empty description="暂无术语数据" /> }}
                  pagination={{
                    current: page,
                    pageSize,
                    total,
                    showSizeChanger: true,
                    showTotal: (t) => `共 ${t} 个术语`,
                    onChange: (p, ps) => {
                      setPage(p);
                      setPageSize(ps);
                    },
                  }}
                />
              </div>
            ),
          },
          {
            key: 'decode',
            label: (
              <Space>
                <TranslationOutlined />
                解码工具
              </Space>
            ),
            children: (
              <Row gutter={24}>
                <Col span={12}>
                  <Card title="输入黑话文本" style={{ borderRadius: 8 }}>
                    <TextArea
                      rows={10}
                      value={decodeText}
                      onChange={(e) => setDecodeText(e.target.value)}
                      placeholder="在此粘贴包含黑话的文本，例如：&#10;今天跑分通道已经开了，料子质量不错，水房那边可以洗白，菠菜下分也正常。"
                      style={{ fontSize: 14 }}
                    />
                    <div style={{ marginTop: 12, textAlign: 'right' }}>
                      <Button
                        type="primary"
                        icon={<TranslationOutlined />}
                        onClick={handleDecode}
                        loading={decoding}
                      >
                        解码
                      </Button>
                    </div>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="解码结果" style={{ borderRadius: 8 }}>
                    {decodeResult ? (
                      <div>
                        <div style={{ marginBottom: 16 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>解码后文本</Text>
                          <Paragraph style={{ background: '#f6ffed', padding: 16, borderRadius: 6, borderLeft: '3px solid #52c41a', marginTop: 8, fontSize: 14 }}>
                            {decodeResult.decoded_text}
                          </Paragraph>
                        </div>
                        <Divider />
                        <Text type="secondary" style={{ fontSize: 12 }}>识别到的黑话</Text>
                        <div style={{ marginTop: 8 }}>
                          {decodeResult.found_terms.length > 0 ? (
                            decodeResult.found_terms.map((item, i) => (
                              <div
                                key={i}
                                style={{
                                  background: '#fafafa',
                                  padding: '8px 12px',
                                  borderRadius: 6,
                                  marginBottom: 8,
                                  borderLeft: '3px solid #1890ff',
                                }}
                              >
                                <Space>
                                  <Tag color="red">{item.term}</Tag>
                                  <Text style={{ fontSize: 13 }}>{item.meaning}</Text>
                                </Space>
                              </div>
                            ))
                          ) : (
                            <Empty description="未识别到黑话术语" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                          )}
                        </div>
                      </div>
                    ) : (
                      <Empty description="请输入文本并点击解码" style={{ marginTop: 60 }} />
                    )}
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: 'stats',
            label: (
              <Space>
                <BulbOutlined />
                统计分析
              </Space>
            ),
            children: (
              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Card title="分类分布" style={{ borderRadius: 8 }}>
                    {Object.keys(categoryCountMap).length > 0 ? (
                      Object.entries(categoryCountMap).map(([category, count]) => (
                        <div key={category} style={{ marginBottom: 12 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <Tag color={categoryColors[category]}>{categoryLabels[category] || category}</Tag>
                            <Text type="secondary">{count}</Text>
                          </div>
                          <Progress
                            percent={terms.length > 0 ? Math.round((count / terms.length) * 100) : 0}
                            showInfo={false}
                            strokeColor={categoryColors[category]}
                            size="small"
                          />
                        </div>
                      ))
                    ) : (
                      <Empty description="暂无统计数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="置信度分布" style={{ borderRadius: 8 }}>
                    {terms.length > 0 ? (
                      <>
                        {[
                          { label: '高置信度 (>80%)', count: terms.filter((t) => t.confidence > 0.8).length, color: '#52c41a' },
                          { label: '中置信度 (50-80%)', count: terms.filter((t) => t.confidence > 0.5 && t.confidence <= 0.8).length, color: '#faad14' },
                          { label: '低置信度 (<50%)', count: terms.filter((t) => t.confidence <= 0.5).length, color: '#ff4d4f' },
                        ].map((item) => (
                          <div key={item.label} style={{ marginBottom: 12 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                              <Text style={{ fontSize: 13 }}>{item.label}</Text>
                              <Text type="secondary">{item.count}</Text>
                            </div>
                            <Progress
                              percent={terms.length > 0 ? Math.round((item.count / terms.length) * 100) : 0}
                              showInfo={false}
                              strokeColor={item.color}
                              size="small"
                            />
                          </div>
                        ))}
                        <Divider />
                        <Row gutter={16}>
                          <Col span={12}>
                            <Statistic title="人工录入" value={terms.filter((t) => !t.is_auto_learned).length} valueStyle={{ fontSize: 20 }} />
                          </Col>
                          <Col span={12}>
                            <Statistic title="自动学习" value={autoLearnedCount} valueStyle={{ fontSize: 20, color: '#1890ff' }} />
                          </Col>
                        </Row>
                      </>
                    ) : (
                      <Empty description="暂无统计数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>
                </Col>
              </Row>
            ),
          },
        ]}
      />

      <Modal
        title="添加黑话术语"
        open={addVisible}
        onCancel={() => setAddVisible(false)}
        onOk={() => addForm.submit()}
        confirmLoading={addLoading}
        width={560}
      >
        <Form form={addForm} layout="vertical" onFinish={handleAddTerm}>
          <Form.Item name="term" label="术语" rules={[{ required: true, message: '请输入黑话术语' }]}>
            <Input placeholder="输入黑话术语" />
          </Form.Item>
          <Form.Item name="meaning" label="释义" rules={[{ required: true, message: '请输入术语释义' }]}>
            <TextArea rows={3} placeholder="输入术语的详细释义" />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true, message: '请选择分类' }]}>
            <Select
              options={Object.entries(categoryLabels).map(([value, label]) => ({
                label,
                value,
              }))}
              placeholder="选择分类"
            />
          </Form.Item>
          <Form.Item name="related_terms" label="相关术语">
            <Select mode="tags" placeholder="输入相关术语后回车" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default BlackTalk;
