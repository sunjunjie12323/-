import React from 'react';
import { Card, Statistic } from 'antd';
import type { StatisticProps } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
} from '@ant-design/icons';

interface StatCardProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  color?: string;
  trend?: 'up' | 'down';
  trendValue?: string;
  suffix?: string;
  loading?: boolean;
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  color = '#1890ff',
  trend,
  trendValue,
  suffix,
  loading = false,
}) => {
  const trendConfig: StatisticProps['valueStyle'] = trend === 'up'
    ? { color: '#cf1322' }
    : trend === 'down'
    ? { color: '#3f8600' }
    : undefined;

  return (
    <Card
      loading={loading}
      style={{ borderRadius: 8, overflow: 'hidden' }}
      styles={{ body: { padding: '20px 24px' } }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ color: '#8c8c8c', fontSize: 14, marginBottom: 8 }}>{title}</div>
          <Statistic
            value={value}
            suffix={suffix}
            valueStyle={{ fontWeight: 700, fontSize: 28, color }}
          />
          {trend && trendValue && (
            <div style={{ marginTop: 8, fontSize: 12 }}>
              {trend === 'up' ? (
                <span style={{ color: '#cf1322' }}>
                  <ArrowUpOutlined /> {trendValue}
                </span>
              ) : (
                <span style={{ color: '#3f8600' }}>
                  <ArrowDownOutlined /> {trendValue}
                </span>
              )}
              <span style={{ color: '#8c8c8c', marginLeft: 4 }}>较昨日</span>
            </div>
          )}
        </div>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 12,
            background: `${color}15`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 26,
            color,
          }}
        >
          {icon}
        </div>
      </div>
    </Card>
  );
};

export default StatCard;
