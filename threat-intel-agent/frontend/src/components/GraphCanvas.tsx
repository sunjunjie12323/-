import React, { useEffect, useRef } from 'react';
import { Empty, Spin } from 'antd';
import type { GraphData } from '../types';

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

interface GraphCanvasProps {
  data: GraphData | null;
  loading?: boolean;
  onNodeClick?: (nodeId: string, nodeType: string) => void;
}

const GraphCanvas: React.FC<GraphCanvasProps> = ({ data, loading, onNodeClick }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);

  useEffect(() => {
    if (!data || !containerRef.current) return;
    if (data.nodes.length === 0) return;

    const renderGraph = async () => {
      try {
        const G6 = (await import('@antv/g6')).default;

        if (graphRef.current) {
          graphRef.current.destroy();
        }

        const container = containerRef.current;
        if (!container) return;
        const width = container.offsetWidth;
        const height = container.offsetHeight || 500;

        const nodes = data.nodes.map((node) => ({
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
            style: { fill: '#333', fontSize: 10 },
            position: 'bottom' as const,
          },
          entityType: node.entity_type,
        }));

        const edges = data.edges.map((edge) => ({
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
            style: { fontSize: 8, fill: '#999' },
            autoRotate: true,
          },
        }));

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
          },
          defaultNode: { type: 'circle', size: 30 },
          defaultEdge: { type: 'line', style: { endArrow: true } },
        });

        graph.on('node:click', (evt: any) => {
          const model = evt.item?.getModel();
          if (model && onNodeClick) {
            onNodeClick(model.id, model.entityType);
          }
        });

        graph.data({ nodes, edges });
        graph.render();
        graphRef.current = graph;
      } catch (err) {
        console.error('G6 rendering failed:', err);
      }
    };

    renderGraph();

    return () => {
      if (graphRef.current) {
        try { graphRef.current.destroy(); } catch {}
        graphRef.current = null;
      }
    };
  }, [data, onNodeClick]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 500 }}>
        <Spin size="large" tip="加载图谱中..." />
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 500 }}>
        <Empty description="知识图谱为空，请先采集并分析情报以构建图谱" />
      </div>
    );
  }

  return <div ref={containerRef} style={{ width: '100%', height: 500 }} />;
};

export default GraphCanvas;
