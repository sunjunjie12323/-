import React from 'react';
import { Card, Tag, Space, Typography, Tooltip, Badge, Dropdown } from 'antd';
import {
  ClockCircleOutlined,
  GlobalOutlined,
  MessageOutlined,
  TeamOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ApartmentOutlined,
  MoreOutlined,
} from '@ant-design/icons';
import type { IntelligenceItem } from '../types';
import { THREAT_LEVEL_CONFIG } from '../utils/constants';
import { formatTime } from '../utils/constants';

const { Text, Paragraph } = Typography;

const sourceTypeIcons: Record<string, React.ReactNode> = {
  telegram: <MessageOutlined />,
  dark_web: <GlobalOutlined />,
  forum: <TeamOutlined />,
  social_media: <GlobalOutlined />,
  other: <GlobalOutlined />,
};

const sourceTypeLabels: Record<string, string> = {
  telegram: 'Telegram',
  dark_web: '暗网',
  forum: '论坛',
  social_media: '社交媒体',
  other: '其他',
};

interface IntelCardProps {
  intel: IntelligenceItem;
  onViewDetail?: (intel: IntelligenceItem) => void;
  onAnalyze?: (intel: IntelligenceItem) => void;
  onAddToGraph?: (intel: IntelligenceItem) => void;
}

const IntelCard: React.FC<IntelCardProps> = ({ intel, onViewDetail, onAnalyze, onAddToGraph }) => {
  const threatConfig = THREAT_LEVEL_CONFIG[intel.threat_level || ''] || THREAT_LEVEL_CONFIG.info;

  const dropdownItems = [
    {
      key: 'analyze',
      icon: <ExperimentOutlined />,
      label: '深度分析',
      onClick: () => onAnalyze?.(intel),
    },
    {
      key: 'graph',
      icon: <ApartmentOutlined />,
      label: '加入图谱',
      onClick: () => onAddToGraph?.(intel),
    },
    {
      key: 'detail',
      icon: <EyeOutlined />,
      label: '查看详情',
      onClick: () => onViewDetail?.(intel),
    },
  ];

  const sourceType = intel.source || 'other';

  return (
    <Card
      hoverable
      style={{
        marginBottom: 12,
        borderLeft: `4px solid ${threatConfig.color}`,
        borderRadius: 6,
      }}
      styles={{ body: { padding: '16px 20px' } }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Space size="small" style={{ marginBottom: 8 }}>
            <Badge
              color={threatConfig.color}
              text={<Text style={{ color: threatConfig.color, fontWeight: 600, fontSize: 13 }}>{threatConfig.label}</Text>}
            />
            <Tag
              icon={sourceTypeIcons[sourceType]}
              color="default"
              style={{ margin: 0, fontSize: 12 }}
            >
              {sourceTypeLabels[sourceType] || sourceType}
            </Tag>
            <Tag color={intel.status === 'analyzed' ? 'green' : intel.status === 'cleaned' ? 'blue' : 'default'} style={{ margin: 0, fontSize: 12 }}>
              {intel.status === 'analyzed' ? '已分析' : intel.status === 'cleaned' ? '已清洗' : '原始'}
            </Tag>
          </Space>
          <Paragraph
            strong
            ellipsis={{ rows: 1 }}
            style={{ marginBottom: 6, fontSize: 15 }}
          >
            {intel.content?.substring(0, 80) || '未命名'}
          </Paragraph>
          <Paragraph
            type="secondary"
            ellipsis={{ rows: 2 }}
            style={{ marginBottom: 8, fontSize: 13 }}
          >
            {intel.content}
          </Paragraph>
          <Space size={4} wrap>
            {intel.entities_count > 0 && (
              <Tag style={{ fontSize: 11, margin: 0 }} color="processing">
                {intel.entities_count} 个实体
              </Tag>
            )}
            {intel.blacktalk_count > 0 && (
              <Tag style={{ fontSize: 11, margin: 0 }} color="orange">
                {intel.blacktalk_count} 个黑话
              </Tag>
            )}
          </Space>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, marginLeft: 16 }}>
          <Dropdown menu={{ items: dropdownItems }} trigger={['click']}>
            <MoreOutlined style={{ cursor: 'pointer', fontSize: 18, color: '#999' }} />
          </Dropdown>
          {intel.collected_at && (
            <Tooltip title={formatTime(intel.collected_at)}>
              <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                <ClockCircleOutlined style={{ marginRight: 4 }} />
                {formatTime(intel.collected_at)}
              </Text>
            </Tooltip>
          )}
        </div>
      </div>
    </Card>
  );
};

export default IntelCard;
