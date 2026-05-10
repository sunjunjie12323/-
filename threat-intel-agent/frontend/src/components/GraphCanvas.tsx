import React, { useEffect, useRef, useCallback } from 'react';
import G6, { Graph, INode, IEdge } from '@antv/g6';
import { Button, Space, Tooltip, Empty, Spin } from 'antd';
import {
  ZoomInOutlined,
  ZoomOutOutlined,
  FullscreenOutlined,
  CompressOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { GraphData, GraphNode, GraphEdge } from '../types';

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

interface GraphCanvasProps {
  data: GraphData | null;
  loading?: boolean;
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  onCanvasClick?: () => void;
  highlightNodes?: string[];
  style?: React.CSSProperties;
}

const GraphCanvas: React.FC<GraphCanvasProps> = ({
  data,
  loading = false,
  onNodeClick,
  onEdgeClick,
  onCanvasClick,
  highlightNodes,
  style,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  const initGraph = useCallback(() => {
    if (!containerRef.current) return;

    if (graphRef.current) {
      graphRef.current.destroy();
      graphRef.current = null;
    }

    const container = containerRef.current;
    const width = container.offsetWidth;
    const height = container.offsetHeight;

    const graph = new G6.Graph({
      container,
      width,
      height,
      fitView: true,
      fitViewPadding: [40, 40, 40, 40],
      animate: true,
      animateCfg: { duration: 200 },
      modes: {
        default: [
          'drag-canvas',
          'zoom-canvas',
          'drag-node',
          {
            type: 'tooltip',
            formatText(model: any) {
              const data = model as any;
              const entityType = data.entity_type || 'other';
              return `<div style="padding:8px 12px;font-size:12px;">
                <div style="font-weight:bold;margin-bottom:4px;">${data.label}</div>
                <div>类型: ${entityTypeLabels[entityType] || entityType}</div>
                <div>置信度: ${((data.confidence || 0) * 100).toFixed(0)}%</div>
              </div>`;
            },
            offset: 15,
          },
        ],
      },
      layout: {
        type: 'force',
        preventOverlap: true,
        nodeSize: 40,
        linkDistance: 180,
        nodeStrength: -300,
        edgeStrength: 0.1,
        collideStrength: 0.8,
        alphaDecay: 0.05,
      },
      defaultNode: {
        size: 36,
        style: {
          lineWidth: 2,
          stroke: '#fff',
          fill: '#1890ff',
        },
        labelCfg: {
          style: {
            fill: '#333',
            fontSize: 11,
            fontWeight: 500,
          },
          position: 'bottom',
          offset: 8,
        },
      },
      defaultEdge: {
        type: 'quadratic',
        style: {
          stroke: '#b8c3ce',
          lineWidth: 1.5,
          endArrow: {
            path: G6.Arrow.triangle(6, 8, 0),
            fill: '#b8c3ce',
          },
        },
        labelCfg: {
          style: {
            fill: '#8c8c8c',
            fontSize: 10,
            background: {
              fill: '#fff',
              padding: [2, 4, 2, 4],
              radius: 2,
            },
          },
          autoRotate: true,
        },
      },
      nodeStateStyles: {
        hover: {
          lineWidth: 3,
          shadowColor: '#1890ff',
          shadowBlur: 12,
        },
        selected: {
          lineWidth: 3,
          stroke: '#1890ff',
          shadowColor: '#1890ff',
          shadowBlur: 16,
        },
        highlight: {
          lineWidth: 3,
          stroke: '#faad14',
          shadowColor: '#faad14',
          shadowBlur: 12,
        },
      },
      edgeStateStyles: {
        hover: {
          stroke: '#1890ff',
          lineWidth: 2.5,
        },
        selected: {
          stroke: '#1890ff',
          lineWidth: 2.5,
        },
      },
    });

    graph.on('node:click', (evt: any) => {
      const nodeModel = evt.item?.getModel();
      if (nodeModel && onNodeClick) {
        onNodeClick(nodeModel as unknown as GraphNode);
      }
      graph.setItemState(evt.item, 'selected', true);
    });

    graph.on('edge:click', (evt: any) => {
      const edgeModel = evt.item?.getModel();
      if (edgeModel && onEdgeClick) {
        onEdgeClick(edgeModel as unknown as GraphEdge);
      }
    });

    graph.on('canvas:click', () => {
      const nodes = graph.getNodes();
      nodes.forEach((node: INode) => {
        graph.clearItemStates(node, ['selected']);
      });
      onCanvasClick?.();
    });

    graph.on('node:mouseenter', (evt: any) => {
      graph.setItemState(evt.item, 'hover', true);
    });

    graph.on('node:mouseleave', (evt: any) => {
      graph.setItemState(evt.item, 'hover', false);
    });

    graph.on('edge:mouseenter', (evt: any) => {
      graph.setItemState(evt.item, 'hover', true);
    });

    graph.on('edge:mouseleave', (evt: any) => {
      graph.setItemState(evt.item, 'hover', false);
    });

    graphRef.current = graph;
  }, [onNodeClick, onEdgeClick, onCanvasClick]);

  useEffect(() => {
    initGraph();
    return () => {
      if (graphRef.current) {
        graphRef.current.destroy();
        graphRef.current = null;
      }
    };
  }, [initGraph]);

  useEffect(() => {
    if (!graphRef.current || !data) return;

    const graph = graphRef.current;
    graph.clear();

    const nodes = (data.nodes || []).map((node) => {
      const entityType = node.entity_type || 'other';
      const color = entityTypeColors[entityType] || entityTypeColors.other;
      return {
        id: node.id,
        label: node.label || node.id,
        entity_type: entityType,
        confidence: node.confidence,
        properties: node.properties,
        type: 'circle',
        size: Math.max(30, Math.min(60, 30 + (node.properties ? Object.keys(node.properties).length * 3 : 0))),
        style: {
          fill: color,
          stroke: '#fff',
          lineWidth: 2,
        },
        labelCfg: {
          style: {
            fill: '#333',
            fontSize: 11,
          },
          position: 'bottom' as const,
          offset: 8,
        },
      };
    });

    const edges = (data.edges || []).map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.relation_type || '',
      relation_type: edge.relation_type,
      properties: edge.properties,
      confidence: edge.confidence,
      type: 'quadratic',
      style: {
        stroke: '#b8c3ce',
        lineWidth: 1.5,
        endArrow: {
          path: G6.Arrow.triangle(6, 8, 0),
          fill: '#b8c3ce',
        },
      },
    }));

    graph.data({ nodes, edges });
    graph.render();
    graph.fitView(40);
  }, [data]);

  useEffect(() => {
    if (!graphRef.current || !highlightNodes) return;
    const graph = graphRef.current;
    const allNodes = graph.getNodes();
    allNodes.forEach((node: INode) => {
      graph.clearItemStates(node, ['highlight']);
    });
    if (highlightNodes.length > 0) {
      highlightNodes.forEach((nodeId) => {
        const node = graph.findById(nodeId);
        if (node) {
          graph.setItemState(node, 'highlight', true);
        }
      });
    }
  }, [highlightNodes]);

  useEffect(() => {
    const handleResize = () => {
      if (!graphRef.current || !containerRef.current) return;
      const width = containerRef.current.offsetWidth;
      const height = containerRef.current.offsetHeight;
      graphRef.current.changeSize(width, height);
      graphRef.current.fitView(40);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleZoomIn = () => {
    if (graphRef.current) {
      const zoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(Math.min(zoom * 1.2, 5));
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      const zoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(Math.max(zoom / 1.2, 0.1));
    }
  };

  const handleFitView = () => {
    graphRef.current?.fitView(40);
  };

  const handleFullscreen = () => {
    if (containerRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        containerRef.current.requestFullscreen();
      }
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', ...style }}>
        <Spin size="large" tip="加载图谱数据中..." />
      </div>
    );
  }

  if (!data || (!data.nodes?.length && !data.edges?.length)) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', ...style }}>
        <Empty description="暂无图谱数据" />
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', ...style }}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', background: '#fafafa', borderRadius: 8 }}
      />
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          zIndex: 10,
        }}
      >
        <Space direction="vertical" size={4}>
          <Tooltip title="放大">
            <Button icon={<ZoomInOutlined />} size="small" onClick={handleZoomIn} />
          </Tooltip>
          <Tooltip title="缩小">
            <Button icon={<ZoomOutOutlined />} size="small" onClick={handleZoomOut} />
          </Tooltip>
          <Tooltip title="适应画布">
            <Button icon={<CompressOutlined />} size="small" onClick={handleFitView} />
          </Tooltip>
          <Tooltip title="全屏">
            <Button icon={<FullscreenOutlined />} size="small" onClick={handleFullscreen} />
          </Tooltip>
          <Tooltip title="刷新布局">
            <Button icon={<ReloadOutlined />} size="small" onClick={handleFitView} />
          </Tooltip>
        </Space>
      </div>
      <div
        style={{
          position: 'absolute',
          bottom: 12,
          left: 12,
          zIndex: 10,
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap',
        }}
      >
        {Object.entries(entityTypeColors).map(([type, color]) => (
          <div
            key={type}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              background: 'rgba(255,255,255,0.9)',
              padding: '2px 8px',
              borderRadius: 4,
            }}
          >
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: color,
              }}
            />
            {entityTypeLabels[type] || type}
          </div>
        ))}
      </div>
    </div>
  );
};

export default GraphCanvas;
