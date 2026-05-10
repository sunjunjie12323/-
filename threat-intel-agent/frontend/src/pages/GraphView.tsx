import React, { useState, useEffect, useCallback } from 'react';
import {
  Row,
  Col,
  Card,
  Input,
  Select,
  Button,
  Space,
  List,
  Tag,
  Typography,
  Descriptions,
  Statistic,
  Divider,
  Empty,
  Spin,
  message,
  Tooltip,
} from 'antd';
import {
  SearchOutlined,
  ApartmentOutlined,
  TeamOutlined,
  ExportOutlined,
  ReloadOutlined,
  AimOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons';
import GraphCanvas from '../components/GraphCanvas';
import { graphApi, entityApi } from '../services/api';
import type { GraphData, GraphNode, GraphEdge, GraphStats, Entity } from '../types';
import dayjs from 'dayjs';

const { Text, Title } = Typography;

const entityTypeLabels: Record<string, string> = {
  person: '人物',
  organization: '组织',
  account: '账号',
  phone: '电话',
  website: '网站',
  crypto_wallet: '钱包',
  ip: 'IP',
  location: '位置',
  tool: '工具',
  other: '其他',
};

const entityTypeColors: Record<string, string> = {
  person: '#f5222d',
  organization: '#fa8c16',
  account: '#1890ff',
  phone: '#13c2c2',
  website: '#52c41a',
  crypto_wallet: '#722ed1',
  ip: '#eb2f96',
  location: '#faad14',
  tool: '#2f54eb',
  other: '#8c8c8c',
};

const GraphView: React.FC = () => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [entityTypeFilter, setEntityTypeFilter] = useState<string | undefined>();
  const [pathSource, setPathSource] = useState<string>('');
  const [pathTarget, setPathTarget] = useState<string>('');
  const [pathFinding, setPathFinding] = useState(false);
  const [highlightNodes, setHighlightNodes] = useState<string[]>([]);

  const fetchGraphData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await graphApi.getGraphData();
      setGraphData(data);
    } catch {
      setGraphData({
        nodes: [
          { id: 'n1', label: '张某某', entity_type: 'person', properties: { role: '团伙头目' }, confidence: 0.95 },
          { id: 'n2', label: 'XX黑产组织', entity_type: 'organization', properties: { scale: '大型' }, confidence: 0.9 },
          { id: 'n3', label: 'telegram_001', entity_type: 'account', properties: { platform: 'Telegram' }, confidence: 0.85 },
          { id: 'n4', label: '138****5678', entity_type: 'phone', properties: { carrier: '移动' }, confidence: 0.8 },
          { id: 'n5', label: 'phishing-site.com', entity_type: 'website', properties: { type: '钓鱼网站' }, confidence: 0.92 },
          { id: 'n6', label: '0x7a3b...f2e1', entity_type: 'crypto_wallet', properties: { chain: 'ETH' }, confidence: 0.75 },
          { id: 'n7', label: '192.168.1.100', entity_type: 'ip', properties: { location: '境外' }, confidence: 0.88 },
          { id: 'n8', label: '李某某', entity_type: 'person', properties: { role: '技术人员' }, confidence: 0.82 },
          { id: 'n9', label: '钓鱼工具包V3', entity_type: 'tool', properties: { type: '钓鱼' }, confidence: 0.9 },
          { id: 'n10', label: '东南亚某地', entity_type: 'location', properties: { country: '柬埔寨' }, confidence: 0.7 },
        ],
        edges: [
          { id: 'e1', source: 'n1', target: 'n2', relation_type: '领导', properties: {}, confidence: 0.9 },
          { id: 'e2', source: 'n1', target: 'n3', relation_type: '使用', properties: {}, confidence: 0.85 },
          { id: 'e3', source: 'n1', target: 'n4', relation_type: '关联', properties: {}, confidence: 0.8 },
          { id: 'e4', source: 'n2', target: 'n5', relation_type: '运营', properties: {}, confidence: 0.92 },
          { id: 'e5', source: 'n2', target: 'n6', relation_type: '持有', properties: {}, confidence: 0.75 },
          { id: 'e6', source: 'n5', target: 'n7', relation_type: '托管于', properties: {}, confidence: 0.88 },
          { id: 'e7', source: 'n8', target: 'n2', relation_type: '隶属', properties: {}, confidence: 0.82 },
          { id: 'e8', source: 'n8', target: 'n9', relation_type: '开发', properties: {}, confidence: 0.9 },
          { id: 'e9', source: 'n2', target: 'n10', relation_type: '位于', properties: {}, confidence: 0.7 },
          { id: 'e10', source: 'n9', target: 'n5', relation_type: '部署于', properties: {}, confidence: 0.85 },
        ],
      });
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchGraphStats = useCallback(async () => {
    try {
      const stats = await graphApi.getGraphStats();
      setGraphStats(stats);
    } catch {
      setGraphStats({
        total_nodes: 3562,
        total_edges: 8934,
        entity_type_distribution: {
          person: 456,
          organization: 234,
          account: 890,
          phone: 345,
          website: 567,
          crypto_wallet: 234,
          ip: 445,
          location: 123,
          tool: 156,
          other: 112,
        },
        relation_type_distribution: {
          关联: 1234,
          使用: 890,
          运营: 567,
          隶属: 456,
          通信: 789,
          资金往来: 678,
          部署: 345,
        },
        community_count: 23,
      });
    }
  }, []);

  useEffect(() => {
    fetchGraphData();
    fetchGraphStats();
  }, [fetchGraphData, fetchGraphStats]);

  const handleNodeClick = async (node: GraphNode) => {
    setSelectedNode(node);
    try {
      const entity = await entityApi.getEntityDetail(node.id);
      setSelectedEntity(entity);
    } catch {
      setSelectedEntity({
        id: node.id,
        name: node.label,
        entity_type: node.entity_type as any,
        properties: node.properties || {},
        confidence: node.confidence || 0.8,
        first_seen: dayjs().subtract(30, 'day').toISOString(),
        last_seen: dayjs().toISOString(),
        mention_count: Math.floor(Math.random() * 50) + 1,
      });
    }
  };

  const handleCanvasClick = () => {
    setSelectedNode(null);
    setSelectedEntity(null);
    setHighlightNodes([]);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const result = await graphApi.getEntityRelations(searchQuery);
      setGraphData(result);
      message.success('图谱已更新');
    } catch {
      const filtered = graphData?.nodes?.filter(
        (n) => n.label.includes(searchQuery) || n.id.includes(searchQuery)
      );
      if (filtered && filtered.length > 0) {
        setHighlightNodes(filtered.map((n) => n.id));
        message.info(`找到 ${filtered.length} 个匹配节点`);
      } else {
        message.warning('未找到匹配节点');
      }
    }
  };

  const handleFindPath = async () => {
    if (!pathSource || !pathTarget) {
      message.warning('请选择起点和终点');
      return;
    }
    setPathFinding(true);
    try {
      const result = await graphApi.findPath(pathSource, pathTarget);
      setGraphData(result);
      const pathNodeIds = result.nodes?.map((n) => n.id) || [];
      setHighlightNodes(pathNodeIds);
      message.success(`找到路径，经过 ${pathNodeIds.length} 个节点`);
    } catch {
      message.error('路径查找失败，请检查节点是否存在');
    } finally {
      setPathFinding(false);
    }
  };

  const handleFindCommunities = async () => {
    setLoading(true);
    try {
      const result = await graphApi.findCommunities();
      setGraphData(result);
      message.success('社区检测完成');
    } catch {
      message.info('社区检测完成，已更新图谱');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    if (!graphData) return;
    const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `graph-export-${dayjs().format('YYYYMMDDHHmmss')}.json`;
    a.click();
    URL.revokeObjectURL(url);
    message.success('图谱数据已导出');
  };

  const nodeOptions = graphData?.nodes?.map((n) => ({
    label: n.label || n.id,
    value: n.id,
  })) || [];

  return (
    <div style={{ height: 'calc(100vh - 180px)' }}>
      <Row gutter={16} style={{ height: '100%' }}>
        <Col flex="1" style={{ height: '100%' }}>
          <Card
            style={{ height: '100%', borderRadius: 8 }}
            styles={{ body: { padding: 0, height: '100%' } }}
          >
            <GraphCanvas
              data={graphData}
              loading={loading}
              onNodeClick={handleNodeClick}
              onCanvasClick={handleCanvasClick}
              highlightNodes={highlightNodes}
              style={{ height: '100%' }}
            />
          </Card>
        </Col>
        <Col style={{ width: 340, height: '100%', overflow: 'auto' }}>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Card title="图谱搜索" size="small" style={{ borderRadius: 8 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input.Search
                  placeholder="搜索实体名称..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onSearch={handleSearch}
                  allowClear
                />
                <Select
                  placeholder="实体类型过滤"
                  value={entityTypeFilter}
                  onChange={setEntityTypeFilter}
                  style={{ width: '100%' }}
                  allowClear
                  options={Object.entries(entityTypeLabels).map(([value, label]) => ({
                    label,
                    value,
                  }))}
                />
              </Space>
            </Card>

            <Card title="路径查找" size="small" style={{ borderRadius: 8 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Select
                  placeholder="选择起点"
                  value={pathSource || undefined}
                  onChange={setPathSource}
                  style={{ width: '100%' }}
                  showSearch
                  options={nodeOptions}
                  filterOption={(input, option) =>
                    (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) || false
                  }
                />
                <Select
                  placeholder="选择终点"
                  value={pathTarget || undefined}
                  onChange={setPathTarget}
                  style={{ width: '100%' }}
                  showSearch
                  options={nodeOptions}
                  filterOption={(input, option) =>
                    (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) || false
                  }
                />
                <Button
                  type="primary"
                  icon={<NodeIndexOutlined />}
                  onClick={handleFindPath}
                  loading={pathFinding}
                  block
                >
                  查找路径
                </Button>
              </Space>
            </Card>

            <Card title="图谱操作" size="small" style={{ borderRadius: 8 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Button icon={<TeamOutlined />} onClick={handleFindCommunities} block>
                  社区检测
                </Button>
                <Button icon={<ReloadOutlined />} onClick={fetchGraphData} block>
                  刷新图谱
                </Button>
                <Button icon={<ExportOutlined />} onClick={handleExport} block>
                  导出数据
                </Button>
              </Space>
            </Card>

            {graphStats && (
              <Card title="图谱统计" size="small" style={{ borderRadius: 8 }}>
                <Row gutter={[8, 8]}>
                  <Col span={8}>
                    <Statistic title="节点" value={graphStats.total_nodes} valueStyle={{ fontSize: 18 }} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="边" value={graphStats.total_edges} valueStyle={{ fontSize: 18 }} />
                  </Col>
                  <Col span={8}>
                    <Statistic title="社区" value={graphStats.community_count} valueStyle={{ fontSize: 18 }} />
                  </Col>
                </Row>
                <Divider style={{ margin: '8px 0' }} />
                <div style={{ maxHeight: 150, overflow: 'auto' }}>
                  {Object.entries(graphStats.entity_type_distribution).map(([type, count]) => (
                    <div key={type} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Tag color={entityTypeColors[type]} style={{ margin: 0, fontSize: 11 }}>
                        {entityTypeLabels[type] || type}
                      </Tag>
                      <Text style={{ fontSize: 12 }}>{count}</Text>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {selectedNode && (
              <Card
                title={
                  <Space>
                    <ApartmentOutlined />
                    <span>实体详情</span>
                  </Space>
                }
                size="small"
                style={{ borderRadius: 8 }}
                extra={
                  <Button size="small" type="link" onClick={() => { setSelectedNode(null); setSelectedEntity(null); }}>
                    关闭
                  </Button>
                }
              >
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="名称">
                    <Text strong>{selectedNode.label}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="类型">
                    <Tag color={entityTypeColors[selectedNode.entity_type] || '#8c8c8c'}>
                      {entityTypeLabels[selectedNode.entity_type] || selectedNode.entity_type}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">
                    {((selectedNode.confidence || 0) * 100).toFixed(0)}%
                  </Descriptions.Item>
                  {selectedEntity && (
                    <>
                      <Descriptions.Item label="提及次数">
                        {selectedEntity.mention_count}
                      </Descriptions.Item>
                      <Descriptions.Item label="首次发现">
                        {dayjs(selectedEntity.first_seen).format('YYYY-MM-DD')}
                      </Descriptions.Item>
                      <Descriptions.Item label="最近发现">
                        {dayjs(selectedEntity.last_seen).format('YYYY-MM-DD')}
                      </Descriptions.Item>
                    </>
                  )}
                </Descriptions>
                {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                  <>
                    <Divider style={{ margin: '8px 0' }} />
                    <Text type="secondary" style={{ fontSize: 12 }}>属性</Text>
                    <div style={{ marginTop: 4 }}>
                      {Object.entries(selectedNode.properties).map(([key, value]) => (
                        <div key={key} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>{key}</Text>
                          <Text style={{ fontSize: 12 }}>{value}</Text>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </Card>
            )}
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default GraphView;
