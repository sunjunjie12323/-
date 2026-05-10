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
import type { Intelligence } from '../types';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

const { Text, Paragraph } = Typography;

const threatLevelConfig: Record<string, { color: string; label: string }> = {
  critical: { color: '#ff4d4f', label: '严重' },
  high: { color: '#ff7a45', label: '高危' },
  medium: { color: '#faad14', label: '中危' },
  low: { color: '#52c41a', label: '低危' },
  info: { color: '#1890ff', label: '信息' },
};

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
  intel: Intelligence;
  onViewDetail?: (intel: Intelligence) => void;
  onAnalyze?: (intel: Intelligence) => void;
  onAddToGraph?: (intel: Intelligence) => void;
}

const IntelCard: React.FC<IntelCardProps> = ({ intel, onViewDetail, onAnalyze, onAddToGraph }) => {
  const threatConfig = threatLevelConfig[intel.threat_level] || threatLevelConfig.info;

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
              icon={sourceTypeIcons[intel.source_type]}
              color="default"
              style={{ margin: 0, fontSize: 12 }}
            >
              {sourceTypeLabels[intel.source_type] || intel.source_type}
            </Tag>
            {intel.is_processed && (
              <Tag color="green" style={{ margin: 0, fontSize: 12 }}>
                已处理
              </Tag>
            )}
          </Space>
          <Paragraph
            strong
            ellipsis={{ rows: 1 }}
            style={{ marginBottom: 6, fontSize: 15 }}
          >
            {intel.title}
          </Paragraph>
          <Paragraph
            type="secondary"
            ellipsis={{ rows: 2 }}
            style={{ marginBottom: 8, fontSize: 13 }}
          >
            {intel.decoded_content || intel.content}
          </Paragraph>
          <Space size={4} wrap>
            {intel.entities?.slice(0, 4).map((entity) => (
              <Tag
                key={entity.id}
                style={{ fontSize: 11, margin: 0 }}
                color="processing"
              >
                {entity.name}
              </Tag>
            ))}
            {intel.entities?.length > 4 && (
              <Tag style={{ fontSize: 11, margin: 0 }}>
                +{intel.entities.length - 4}
              </Tag>
            )}
          </Space>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, marginLeft: 16 }}>
          <Dropdown menu={{ items: dropdownItems }} trigger={['click']}>
            <MoreOutlined style={{ cursor: 'pointer', fontSize: 18, color: '#999' }} />
          </Dropdown>
          <Tooltip title={dayjs(intel.collected_at).format('YYYY-MM-DD HH:mm:ss')}>
            <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
              <ClockCircleOutlined style={{ marginRight: 4 }} />
              {dayjs(intel.collected_at).fromNow()}
            </Text>
          </Tooltip>
        </div>
      </div>
    </Card>
  );
};

export default IntelCard;
