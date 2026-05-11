import React, { useState, useEffect, useCallback } from 'react';
import { Badge, Card, List, Tag, Button, Space, Typography, Statistic, Row, Col, message } from 'antd';
import { BellOutlined, CheckCircleOutlined, AlertOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { api } from '../services/api';

const { Text } = Typography;

const severityConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  critical: { color: 'red', icon: <ExclamationCircleOutlined /> },
  high: { color: 'orange', icon: <AlertOutlined /> },
  medium: { color: 'gold', icon: <BellOutlined /> },
  low: { color: 'blue', icon: <BellOutlined /> },
};

const AlertPanel: React.FC = () => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const [alertRes, statsRes] = await Promise.all([
        api.alerts.getActive(),
        api.alerts.getStats(),
      ]);
      setAlerts(alertRes.alerts || []);
      setStats(statsRes);
    } catch (err: any) {
      message.error(err?.message || '获取告警失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  const handleAcknowledge = async (alertId: string) => {
    try {
      await api.alerts.acknowledge(alertId);
      message.success('告警已确认');
      fetchAlerts();
    } catch (err: any) {
      message.error('确认失败');
    }
  };

  const handleTestTrigger = async () => {
    try {
      const res = await api.alerts.testTrigger();
      message.success(`触发 ${res.triggered_alerts} 条告警`);
      fetchAlerts();
    } catch (err: any) {
      message.error('测试触发失败');
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Row gutter={16}>
        <Col span={6}>
          <Card><Statistic title="活跃告警" value={stats?.active_alerts || 0} valueStyle={{ color: '#ff4d4f' }} prefix={<AlertOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="严重" value={stats?.by_severity?.critical || 0} valueStyle={{ color: '#cf1322' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="高危" value={stats?.by_severity?.high || 0} valueStyle={{ color: '#fa8c16' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已确认" value={stats?.acknowledged || 0} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} /></Card>
        </Col>
      </Row>

      <Card
        title={<Space><BellOutlined />实时告警</Space>}
        extra={<Space><Button type="primary" onClick={handleTestTrigger}>测试触发</Button><Button onClick={fetchAlerts} loading={loading}>刷新</Button></Space>}
      >
        <List
          dataSource={alerts}
          renderItem={(alert: any) => {
            const config = severityConfig[alert.severity] || severityConfig.medium;
            return (
              <List.Item
                actions={[
                  !alert.acknowledged && <Button size="small" type="primary" key="ack" onClick={() => handleAcknowledge(alert.alert_id)}>确认</Button>,
                ].filter(Boolean)}
              >
                <List.Item.Meta
                  avatar={config.icon}
                  title={
                    <Space>
                      <Tag color={config.color}>{alert.severity?.toUpperCase()}</Tag>
                      <Text strong>{alert.title}</Text>
                      {alert.acknowledged && <Tag color="green">已确认</Tag>}
                    </Space>
                  }
                  description={
                    <div>
                      <Text>{alert.description}</Text>
                      <br />
                      <Text type="secondary">{alert.timestamp?.substring(11, 19)} · {alert.entity_type} · {alert.entity_value?.substring(0, 30)}</Text>
                    </div>
                  }
                />
              </List.Item>
            );
          }}
          locale={{ emptyText: '暂无活跃告警' }}
        />
      </Card>
    </Space>
  );
};

export default AlertPanel;
