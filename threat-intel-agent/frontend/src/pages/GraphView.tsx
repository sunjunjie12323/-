import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Card, Select, Button, Space, Input, message, Empty, Spin, Typography, Tag, List, Divider, Row, Col, Statistic, Modal, Badge, Table } from 'antd';
import {
  SearchOutlined, ReloadOutlined, ApartmentOutlined, ShareAltOutlined,
  TeamOutlined, NodeIndexOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { graphApi, getErrorMessage } from '../services/api';
import type { GraphData, GraphStats, CommunityResult, PathResult, GraphNode, GraphEdge } from '../types';
import { useDebounce } from '../utils/hooks';

const { Text, Paragraph } = Typography;

const ENTITY_TYPE_COLORS: Record<string, string> = {
  person: '#ff4d4f',
  organization: '#1890ff',
  location: '#52c41a',
  ip_address: '#722ed1',
  domain: '#fa8c16',
  phone: '#13c2c2',
  email: '#eb2f96',
  url: '#2f54eb',
  hash: '#a0d911',
  cryptocurrency: '#fadb14',
  keyword: '#bfbfbf',
  malware: '#cf1322',
};

const ENTITY_TYPE_LABELS: Record<string, string> = {
  person: '人物',
  organization: '组织',
  location: '地点',
  ip_address: 'IP地址',
  domain: '域名',
  phone: '电话',
  email: '邮箱',
  url: 'URL',
  hash: '哈希',
  cryptocurrency: '加密货币',
  keyword: '关键词',
  malware: '恶意软件',
};

const HIGH_RISK_TYPES = new Set(['malware', 'organization', 'person']);

function calculateCommunityRisk(members: Array<{ type: string; value: string }>): { level: string; color: string; label: string } {
  let highRiskCount = 0;
  for (const member of members) {
    if (HIGH_RISK_TYPES.has(member.type)) {
      highRiskCount++;
    }
  }
  const ratio = members.length > 0 ? highRiskCount / members.length : 0;
  if (ratio >= 0.5 || highRiskCount >= 3) {
    return { level: 'high', color: '#cf1322', label: '高危' };
  }
  if (ratio >= 0.2 || highRiskCount >= 1) {
    return { level: 'medium', color: '#fa8c16', label: '中危' };
  }
  return { level: 'low', color: '#52c41a', label: '低危' };
}

const GraphView: React.FC = () => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [entityTypeFilter, setEntityTypeFilter] = useState<string | undefined>();
  const [communities, setCommunities] = useState<CommunityResult | null>(null);
  const [pathResult, setPathResult] = useState<PathResult | null>(null);
  const [pathSource, setPathSource] = useState('');
  const [pathTarget, setPathTarget] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const graphInstanceRef = useRef<any>(null);

  const debouncedSearch = useDebounce(search, 300);

  const fetchGraphData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await graphApi.getData({
        entity_type: entityTypeFilter,
        search: debouncedSearch || undefined,
      });
      setGraphData(data);
    } catch (err) {
      message.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, entityTypeFilter]);

  const fetchStats = useCallback(async () => {
    try {
      const s = await graphApi.getStats();
      setStats(s);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchGraphData();
    fetchStats();
  }, [fetchGraphData, fetchStats]);

  useEffect(() => {
    if (!graphData || !containerRef.current) return;

    const renderGraph = async () => {
      try {
        const G6 = (await import('@antv/g6')).default;

        if (graphInstanceRef.current) {
          graphInstanceRef.current.destroy();
        }

        const container = containerRef.current;
        if (!container) return;
        const width = container.offsetWidth;
        const height = Math.max(500, container.offsetHeight);

        const nodes = (graphData.nodes || []).map((node) => ({
          id: node.id,
          label: node.label?.length > 12 ? node.label.substring(0, 12) + '...' : node.label,
          type: 'circle',
          size: 30,
          style: {
            fill: ENTITY_TYPE_COLORS[node.entity_type] || '#1890ff',
            stroke: '#fff',
            lineWidth: 2,
          },
          labelCfg: {
            style: {
              fill: '#333',
              fontSize: 10,
            },
            position: 'bottom' as const,
          },
          entityType: node.entity_type,
          originalLabel: node.label,
        }));

        const edges = (graphData.edges || []).map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.relation_type?.length > 8 ? edge.relation_type.substring(0, 8) + '...' : edge.relation_type,
          style: {
            stroke: '#bbb',
            lineWidth: 1,
            endArrow: true,
          },
          labelCfg: {
            style: {
              fontSize: 8,
              fill: '#999',
            },
            autoRotate: true,
          },
        }));

        if (nodes.length === 0) {
          if (graphInstanceRef.current) {
            graphInstanceRef.current.destroy();
            graphInstanceRef.current = null;
          }
          return;
        }

        const graph = new G6.Graph({
          container,
          width,
          height,
          modes: {
            default: ['drag-canvas', 'zoom-canvas', 'drag-node'],
          },
          layout: {
            type: 'force',
            preventOverlap: true,
            nodeSize: 40,
            linkDistance: 150,
            nodeStrength: -50,
          },
          defaultNode: {
            type: 'circle',
            size: 30,
          },
          defaultEdge: {
            type: 'line',
            style: {
              endArrow: true,
            },
          },
        });

        graph.on('node:click', (evt: any) => {
          const nodeModel = evt.item?.getModel();
          if (nodeModel) {
            setSelectedNode({
              id: nodeModel.id,
              label: nodeModel.originalLabel || nodeModel.label,
              entity_type: nodeModel.entityType || 'unknown',
              properties: {},
            });
          }
        });

        graph.data({ nodes, edges });
        graph.render();

        graphInstanceRef.current = graph;

        const handleResize = () => {
          if (graphInstanceRef.current && !graphInstanceRef.current.get('destroyed')) {
            const w = container.offsetWidth;
            graphInstanceRef.current.changeSize(w, height);
          }
        };
        window.addEventListener('resize', handleResize);

        return () => {
          window.removeEventListener('resize', handleResize);
        };
      } catch (err) {
        console.error('G6 rendering failed:', err);
      }
    };

    renderGraph();

    return () => {
      if (graphInstanceRef.current) {
        try {
          graphInstanceRef.current.destroy();
        } catch {}
        graphInstanceRef.current = null;
      }
    };
  }, [graphData]);

  const handleFindCommunities = async () => {
    try {
      const result = await graphApi.findCommunities();
      setCommunities(result);
      message.success(`发现 ${result.community_count} 个社区`);
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleFindPath = async () => {
    if (!pathSource || !pathTarget) {
      message.warning('请输入源实体ID和目标实体ID');
      return;
    }
    try {
      const result = await graphApi.findPath(pathSource, pathTarget);
      setPathResult(result);
      if (result.path_count > 0) {
        message.success(`找到 ${result.path_count} 条路径`);
      } else {
        message.info(result.message || '未找到连接路径');
      }
    } catch (err) {
      message.error(getErrorMessage(err));
    }
  };

  const handleDeleteEntity = (entityId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该实体吗？此操作不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          message.success('实体已删除');
          fetchGraphData();
          fetchStats();
        } catch (err) {
          message.error(getErrorMessage(err));
        }
      },
    });
  };

  const entityTypeOptions = Object.entries(ENTITY_TYPE_LABELS).map(([value, label]) => ({
    value,
    label,
  }));

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space wrap>
            <Input
              placeholder="搜索实体..."
              prefix={<SearchOutlined />}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: 200 }}
              allowClear
            />
            <Select
              placeholder="实体类型"
              value={entityTypeFilter}
              onChange={setEntityTypeFilter}
              options={entityTypeOptions}
              allowClear
              style={{ width: 130 }}
            />
            <Button icon={<ReloadOutlined />} onClick={() => { fetchGraphData(); fetchStats(); }}>刷新</Button>
          </Space>
          <Space>
            <Button icon={<TeamOutlined />} onClick={handleFindCommunities}>社区发现</Button>
          </Space>
        </Space>
      </Card>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Card><Statistic title="节点数" value={stats.node_count} prefix={<NodeIndexOutlined />} /></Card>
          </Col>
          <Col span={8}>
            <Card><Statistic title="边数" value={stats.edge_count} prefix={<ShareAltOutlined />} /></Card>
          </Col>
          <Col span={8}>
            <Card>
              <div>
                <Text strong>实体类型分布</Text>
                <div style={{ marginTop: 8 }}>
                  {Object.entries(stats.entity_types || {}).map(([type, count]) => (
                    <Tag key={type} color={ENTITY_TYPE_COLORS[type]} style={{ marginBottom: 4 }}>
                      {ENTITY_TYPE_LABELS[type] || type}: {count}
                    </Tag>
                  ))}
                </div>
              </div>
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={16}>
        <Col xs={24} lg={18}>
          <Card title="知识图谱" bodyStyle={{ padding: 0, height: 600 }}>
            {loading ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <Spin size="large" tip="加载图谱中..." />
              </div>
            ) : !graphData || graphData.nodes.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <Empty description="知识图谱为空，请先采集并分析情报以构建图谱" />
              </div>
            ) : (
              <div ref={containerRef} style={{ width: '100%', height: 600 }} />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={6}>
          {selectedNode && (
            <Card title="选中节点" style={{ marginBottom: 16 }} size="small" extra={
              <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteEntity(selectedNode.id)} />
            }>
              <p><Text strong>名称: </Text>{selectedNode.label}</p>
              <p>
                <Text strong>类型: </Text>
                <Tag color={ENTITY_TYPE_COLORS[selectedNode.entity_type]}>
                  {ENTITY_TYPE_LABELS[selectedNode.entity_type] || selectedNode.entity_type}
                </Tag>
              </p>
              <p><Text strong>ID: </Text><Text copyable style={{ fontSize: 11 }}>{selectedNode.id}</Text></p>
            </Card>
          )}

          <Card title="路径查找" size="small" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Input
                placeholder="源实体ID"
                value={pathSource}
                onChange={(e) => setPathSource(e.target.value)}
                size="small"
              />
              <Input
                placeholder="目标实体ID"
                value={pathTarget}
                onChange={(e) => setPathTarget(e.target.value)}
                size="small"
              />
              <Button type="primary" icon={<ApartmentOutlined />} onClick={handleFindPath} block size="small">
                查找路径
              </Button>
            </Space>
            {pathResult && (
              <div style={{ marginTop: 12 }}>
                <Text>路径数: {pathResult.path_count}</Text>
                {pathResult.message && <Text type="secondary" style={{ display: 'block' }}>{pathResult.message}</Text>}
              </div>
            )}
          </Card>

          {communities && communities.community_count > 0 && (
            <Card title={`社区 (${communities.community_count})`} size="small">
              <List
                size="small"
                dataSource={communities.communities}
                renderItem={(community, idx) => {
                  const risk = calculateCommunityRisk(community.members);
                  return (
                    <List.Item>
                      <Space>
                        <Badge color={risk.color} />
                        <Text>社区 {idx + 1}: {community.member_count} 成员</Text>
                        <Tag color={risk.color}>{risk.label}</Tag>
                      </Space>
                    </List.Item>
                  );
                }}
              />
            </Card>
          )}
        </Col>
      </Row>

      <Card title="图例" style={{ marginTop: 16 }} size="small">
        <Space wrap>
          {Object.entries(ENTITY_TYPE_LABELS).map(([type, label]) => (
            <Tag key={type} color={ENTITY_TYPE_COLORS[type]}>{label}</Tag>
          ))}
        </Space>
      </Card>
    </div>
  );
};

export default GraphView;
