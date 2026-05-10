import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Tag, Input, Button, Space, Modal, Form, message,
  Empty, Spin, Typography, Tabs, List, Statistic, Row, Col, Alert,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, ReloadOutlined, TranslationOutlined,
  BookOutlined, BarChartOutlined,
} from '@ant-design/icons';
import { blacktalkApi, getErrorMessage } from '../services/api';
import type { BlackTalkTerm, BlackTalkDecodeResult, BlackTalkStats, PaginatedResponse } from '../types';

const { Text, Paragraph, Title } = Typography;

const BlackTalk: React.FC = () => {
  const [terms, setTerms] = useState<PaginatedResponse<BlackTalkTerm>>({ items: [], total: 0, offset: 0, limit: 20 });
  const [stats, setStats] = useState<BlackTalkStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [decodeInput, setDecodeInput] = useState('');
  const [decodeResult, setDecodeResult] = useState<BlackTalkDecodeResult | null>(null);
  const [decoding, setDecoding] = useState(false);
  const [activeTab, setActiveTab] = useState('dictionary');
  const [form] = Form.useForm();

  const fetchTerms = useCallback(async () => {
    try {
      setLoading(true);
      const result = await blacktalkApi.listTerms({
        search: search || undefined,
        offset: (page - 1) * pageSize,
        limit: pageSize,
      });
      setTerms(result);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [search, page, pageSize]);

  const fetchStats = useCallback(async () => {
    try {
      const s = await blacktalkApi.getStats();
      setStats(s);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchTerms();
  }, [fetchTerms]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleAddTerm = async (values: { term: string; meaning: string; context?: string; source?: string }) => {
    try {
      await blacktalkApi.addTerm(values.term, values.meaning, values.context, values.source);
      message.success('术语添加成功');
      setAddModalOpen(false);
      form.resetFields();
      fetchTerms();
      fetchStats();
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleDecode = async () => {
    if (!decodeInput.trim()) {
      message.warning('请输入需要解码的文本');
      return;
    }
    try {
      setDecoding(true);
      const result = await blacktalkApi.decode(decodeInput);
      setDecodeResult(result);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setDecoding(false);
    }
  };

  const columns = [
    {
      title: '术语',
      dataIndex: 'term',
      key: 'term',
      width: 150,
      render: (term: string) => <Text strong>{term}</Text>,
    },
    {
      title: '含义',
      dataIndex: 'meaning',
      key: 'meaning',
      ellipsis: true,
    },
    {
      title: '上下文',
      dataIndex: 'context',
      key: 'context',
      width: 200,
      ellipsis: true,
      render: (ctx: string | undefined) => ctx || <Text type="secondary">-</Text>,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (source: string | undefined) => source ? <Tag>{source}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (cat: string | undefined) => cat ? <Tag color="blue">{cat}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 100,
      render: (conf: number | undefined) => {
        if (conf === undefined || conf === null) return <Text type="secondary">-</Text>;
        const color = conf >= 0.8 ? 'green' : conf >= 0.5 ? 'orange' : 'red';
        return <Tag color={color}>{(conf * 100).toFixed(0)}%</Tag>;
      },
    },
  ];

  const tabItems = [
    {
      key: 'dictionary',
      label: (
        <span>
          <BookOutlined /> 术语词典
        </span>
      ),
      children: (
        <div>
          <Card style={{ marginBottom: 16 }}>
            <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
              <Space wrap>
                <Input
                  placeholder="搜索术语..."
                  prefix={<SearchOutlined />}
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                  style={{ width: 250 }}
                  allowClear
                />
                <Button icon={<ReloadOutlined />} onClick={fetchTerms}>刷新</Button>
              </Space>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddModalOpen(true)}>
                添加术语
              </Button>
            </Space>
          </Card>

          {stats && (
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={8}>
                <Card><Statistic title="术语总数" value={stats.total_terms} /></Card>
              </Col>
              <Col span={8}>
                <Card><Statistic title="分类数" value={Object.keys(stats.categories || {}).length} /></Card>
              </Col>
              <Col span={8}>
                <Card><Statistic title="平均置信度" value={stats.average_confidence} precision={2} suffix="%" /></Card>
              </Col>
            </Row>
          )}

          <Card>
            <Table
              columns={columns}
              dataSource={terms.items}
              rowKey="id"
              loading={loading}
              locale={{ emptyText: <Empty description="暂无黑话术语" /> }}
              pagination={{
                current: page,
                pageSize,
                total: terms.total,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条`,
                onChange: (p, ps) => { setPage(p); setPageSize(ps); },
              }}
            />
          </Card>
        </div>
      ),
    },
    {
      key: 'decode',
      label: (
        <span>
          <TranslationOutlined /> 解码工具
        </span>
      ),
      children: (
        <div>
          <Card title="黑话解码" style={{ marginBottom: 16 }}>
            <Input.TextArea
              rows={4}
              placeholder="输入包含黑话的文本..."
              value={decodeInput}
              onChange={(e) => setDecodeInput(e.target.value)}
              style={{ marginBottom: 12 }}
            />
            <Button
              type="primary"
              icon={<TranslationOutlined />}
              onClick={handleDecode}
              loading={decoding}
              disabled={!decodeInput.trim()}
            >
              解码
            </Button>
          </Card>

          {decodeResult && (
            <Card title="解码结果">
              {decodeResult.terms_found > 0 ? (
                <div>
                  <Alert
                    message={`发现 ${decodeResult.terms_found} 个黑话术语`}
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>原始文本: </Text>
                    <Paragraph>{decodeResult.original_text}</Paragraph>
                  </div>
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>解码文本: </Text>
                    <Paragraph>{decodeResult.decoded_text}</Paragraph>
                  </div>
                  {decodeResult.found_terms && decodeResult.found_terms.length > 0 && (
                    <div>
                      <Text strong>识别的术语:</Text>
                      <List
                        size="small"
                        dataSource={decodeResult.found_terms}
                        renderItem={(term) => (
                          <List.Item>
                            <Text strong>{term.term}</Text>
                            <Text type="secondary" style={{ marginLeft: 8 }}>→ {term.meaning}</Text>
                          </List.Item>
                        )}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <Empty description="未发现已知黑话术语" />
              )}
            </Card>
          )}
        </div>
      ),
    },
    {
      key: 'stats',
      label: (
        <span>
          <BarChartOutlined /> 统计
        </span>
      ),
      children: (
        <div>
          {stats ? (
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Card title="分类分布">
                  {Object.keys(stats.categories || {}).length === 0 ? (
                    <Empty description="暂无分类数据" />
                  ) : (
                    <List
                      size="small"
                      dataSource={Object.entries(stats.categories)}
                      renderItem={([cat, count]) => (
                        <List.Item>
                          <Text>{cat}</Text>
                          <Tag color="blue">{count}</Tag>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
              </Col>
              <Col span={12}>
                <Card title="来源分布">
                  {Object.keys(stats.sources || {}).length === 0 ? (
                    <Empty description="暂无来源数据" />
                  ) : (
                    <List
                      size="small"
                      dataSource={Object.entries(stats.sources)}
                      renderItem={([source, count]) => (
                        <List.Item>
                          <Text>{source}</Text>
                          <Tag color="green">{count}</Tag>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
              </Col>
            </Row>
          ) : (
            <Empty description="暂无统计数据" />
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />

      <Modal
        title="添加黑话术语"
        open={addModalOpen}
        onCancel={() => { setAddModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        okText="添加"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleAddTerm}>
          <Form.Item name="term" label="术语" rules={[{ required: true, message: '请输入术语' }]}>
            <Input placeholder="输入黑话术语" />
          </Form.Item>
          <Form.Item name="meaning" label="含义" rules={[{ required: true, message: '请输入含义' }]}>
            <Input placeholder="输入术语含义" />
          </Form.Item>
          <Form.Item name="context" label="上下文">
            <Input placeholder="可选，使用场景" />
          </Form.Item>
          <Form.Item name="source" label="来源">
            <Input placeholder="可选，术语来源" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default BlackTalk;
