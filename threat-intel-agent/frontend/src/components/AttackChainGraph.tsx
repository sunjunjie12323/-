import React from 'react';

interface PredictionStep {
  step: number;
  technique_name: string;
  probability: number;
  risk_level: string;
  reasoning: string;
}

interface AttackChainGraphProps {
  predictions: PredictionStep[];
  entityName?: string;
}

const riskColors: Record<string, { bg: string; border: string; text: string }> = {
  critical: { bg: '#fff1f0', border: '#ff4d4f', text: '#cf1322' },
  high: { bg: '#fff7e6', border: '#fa8c16', text: '#d46b08' },
  medium: { bg: '#fffbe6', border: '#fadb14', text: '#d4b106' },
  low: { bg: '#f6ffed', border: '#52c41a', text: '#389e0d' },
};

const AttackChainGraph: React.FC<AttackChainGraphProps> = ({ predictions, entityName }) => {
  if (!predictions || predictions.length === 0) return null;

  const nodeWidth = 280;
  const nodeHeight = 80;
  const gapY = 40;
  const svgWidth = nodeWidth + 80;
  const svgHeight = predictions.length * (nodeHeight + gapY) + 40;

  return (
    <div style={{ overflowX: 'auto', padding: '8px 0' }}>
      <svg width={svgWidth} height={svgHeight} viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
        {predictions.map((pred, idx) => {
          const y = idx * (nodeHeight + gapY) + 20;
          const x = 40;
          const colors = riskColors[pred.risk_level] || riskColors.medium;

          return (
            <g key={idx}>
              {idx > 0 && (
                <line
                  x1={x + nodeWidth / 2}
                  y1={y - gapY + nodeHeight}
                  x2={x + nodeWidth / 2}
                  y2={y}
                  stroke="#999"
                  strokeWidth={2}
                  markerEnd="url(#arrowhead)"
                >
                  <animate
                    attributeName="stroke-dashoffset"
                    from="20"
                    to="0"
                    dur="1s"
                    repeatCount="1"
                  />
                </line>
              )}
              <rect
                x={x}
                y={y}
                width={nodeWidth}
                height={nodeHeight}
                rx={8}
                fill={colors.bg}
                stroke={colors.border}
                strokeWidth={2}
              >
                <animate
                  attributeName="opacity"
                  from="0"
                  to="1"
                  dur="0.4s"
                  begin={`${idx * 0.15}s`}
                  fill="freeze"
                />
              </rect>
              <circle cx={x + 20} cy={y + 20} r={12} fill={colors.border}>
                <animate
                  attributeName="opacity"
                  from="0"
                  to="1"
                  dur="0.4s"
                  begin={`${idx * 0.15}s`}
                  fill="freeze"
                />
              </circle>
              <text x={x + 20} y={y + 24} textAnchor="middle" fill="white" fontSize={12} fontWeight="bold">
                {pred.step}
              </text>
              <text
                x={x + 40}
                y={y + 24}
                fill={colors.text}
                fontSize={13}
                fontWeight="bold"
              >
                {pred.technique_name?.length > 16 ? pred.technique_name.slice(0, 16) + '...' : pred.technique_name}
              </text>
              <rect x={x + 12} y={y + 40} width={nodeWidth - 24} height={8} rx={4} fill="#f0f0f0" />
              <rect x={x + 12} y={y + 40} width={(nodeWidth - 24) * pred.probability} height={8} rx={4} fill={colors.border}>
                <animate
                  attributeName="width"
                  from="0"
                  to={(nodeWidth - 24) * pred.probability}
                  dur="0.6s"
                  begin={`${idx * 0.15 + 0.2}s`}
                  fill="freeze"
                />
              </rect>
              <text x={x + nodeWidth - 12} y={y + 56} textAnchor="end" fill="#666" fontSize={11}>
                {(pred.probability * 100).toFixed(1)}%
              </text>
              <text x={x + 12} y={y + 68} fill={colors.text} fontSize={10}>
                {pred.risk_level?.toUpperCase()}
              </text>
              <title>{`${pred.technique_name}\n概率: ${(pred.probability * 100).toFixed(1)}%\n风险: ${pred.risk_level}\n推理: ${pred.reasoning}`}</title>
            </g>
          );
        })}
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#999" />
          </marker>
        </defs>
      </svg>
    </div>
  );
};

export default AttackChainGraph;
