import React from 'react';
import { Card, Statistic } from 'antd';
import type { StatisticProps } from 'antd';

interface StatCardProps {
  title: string;
  value: number | string;
  prefix?: React.ReactNode;
  suffix?: React.ReactNode;
  valueStyle?: React.CSSProperties;
  loading?: boolean;
  onClick?: () => void;
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  prefix,
  suffix,
  valueStyle,
  loading,
  onClick,
}) => {
  return (
    <Card
      hoverable={!!onClick}
      onClick={onClick}
      loading={loading}
      bodyStyle={{ padding: '20px 24px' }}
    >
      <Statistic
        title={title}
        value={value}
        prefix={prefix}
        suffix={suffix}
        valueStyle={valueStyle}
      />
    </Card>
  );
};

export default StatCard;
