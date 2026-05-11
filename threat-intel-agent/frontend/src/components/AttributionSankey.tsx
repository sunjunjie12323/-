import React from 'react';

interface AttributionMatch {
  source_platform: string;
  target_platform: string;
  similarity: number;
  evidence?: string[];
}

interface AttributionSankeyProps {
  matches: AttributionMatch[];
  entityName?: string;
}

const platformColors: Record<string, string> = {
  darkweb: '#722ed1',
  forum: '#1890ff',
  telegram: '#13c2c2',
  wechat: '#52c41a',
  social_media: '#fa8c16',
  paste_site: '#eb2f96',
  default: '#666',
};

const AttributionSankey: React.FC<AttributionSankeyProps> = ({ matches, entityName }) => {
  if (!matches || matches.length === 0) return null;

  const width = 600;
  const height = Math.max(300, matches.length * 60 + 80);
  const leftX = 120;
  const rightX = width - 120;

  const sources = [...new Set(matches.map(m => m.source_platform || 'unknown'))];
  const targets = [...new Set(matches.map(m => m.target_platform || 'unknown'))];

  const sourceY = (idx: number) => 40 + idx * (height - 80) / Math.max(sources.length, 1);
  const targetY = (idx: number) => 40 + idx * (height - 80) / Math.max(targets.length, 1);

  return (
    <div style={{ overflowX: 'auto', padding: '8px 0' }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {sources.map((src, idx) => (
          <g key={`src-${idx}`}>
            <rect x={10} y={sourceY(idx) - 12} width={leftX - 20} height={24} rx={4}
              fill={platformColors[src] || platformColors.default} opacity={0.15}
              stroke={platformColors[src] || platformColors.default} strokeWidth={1} />
            <text x={leftX - 15} y={sourceY(idx) + 4} textAnchor="end" fontSize={12} fontWeight="bold"
              fill={platformColors[src] || platformColors.default}>
              {src}
            </text>
          </g>
        ))}

        {targets.map((tgt, idx) => (
          <g key={`tgt-${idx}`}>
            <rect x={rightX + 10} y={targetY(idx) - 12} width={width - rightX - 20} height={24} rx={4}
              fill={platformColors[tgt] || platformColors.default} opacity={0.15}
              stroke={platformColors[tgt] || platformColors.default} strokeWidth={1} />
            <text x={rightX + 15} y={targetY(idx) + 4} textAnchor="start" fontSize={12} fontWeight="bold"
              fill={platformColors[tgt] || platformColors.default}>
              {tgt}
            </text>
          </g>
        ))}

        {matches.map((match, idx) => {
          const srcIdx = sources.indexOf(match.source_platform || 'unknown');
          const tgtIdx = targets.indexOf(match.target_platform || 'unknown');
          const sy = sourceY(srcIdx);
          const ty = targetY(tgtIdx);
          const midX = (leftX + rightX) / 2;
          const thickness = Math.max(2, match.similarity * 8);
          const color = platformColors[match.source_platform] || platformColors.default;

          return (
            <g key={`path-${idx}`}>
              <path
                d={`M ${leftX} ${sy} C ${midX} ${sy}, ${midX} ${ty}, ${rightX} ${ty}`}
                fill="none"
                stroke={color}
                strokeWidth={thickness}
                opacity={0.4 + match.similarity * 0.4}
              >
                <animate
                  attributeName="stroke-dashoffset"
                  from="200"
                  to="0"
                  dur="1s"
                  begin={`${idx * 0.2}s`}
                  fill="freeze"
                />
              </path>
              <text x={midX} y={(sy + ty) / 2 - 6} textAnchor="middle" fontSize={10} fill="#666">
                {(match.similarity * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}

        {entityName && (
          <text x={width / 2} y={16} textAnchor="middle" fontSize={13} fontWeight="bold" fill="#333">
            跨平台归因: {entityName}
          </text>
        )}
      </svg>
    </div>
  );
};

export default AttributionSankey;
