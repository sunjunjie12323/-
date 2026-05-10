import React, { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout as AntLayout, Menu, Typography, Badge, Space, Tooltip, Breadcrumb, theme } from 'antd';
import {
  DashboardOutlined,
  SearchOutlined,
  ApartmentOutlined,
  AimOutlined,
  MessageOutlined,
  FileTextOutlined,
  RobotOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  WifiOutlined,
  AlertOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { agentApi } from '../services/api';
import type { AgentStatus } from '../types';
import dayjs from 'dayjs';

const { Header, Sider, Content, Footer } = AntLayout;
const { Text } = Typography;

const menuItems: MenuProps['items'] = [
  {
    key: '/',
    icon: <DashboardOutlined />,
    label: '态势总览',
  },
  {
    key: '/intelligence',
    icon: <SearchOutlined />,
    label: '情报管理',
  },
  {
    key: '/graph',
    icon: <ApartmentOutlined />,
    label: '知识图谱',
  },
  {
    key: '/pir',
    icon: <AimOutlined />,
    label: '情报需求',
  },
  {
    key: '/blacktalk',
    icon: <MessageOutlined />,
    label: '黑话词典',
  },
  {
    key: '/reports',
    icon: <FileTextOutlined />,
    label: '分析报告',
  },
];

const breadcrumbMap: Record<string, string> = {
  '/': '态势总览',
  '/intelligence': '情报管理',
  '/graph': '知识图谱',
  '/pir': '情报需求',
  '/blacktalk': '黑话词典',
  '/reports': '分析报告',
};

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const statuses = await agentApi.getAgentStatus();
        setAgentStatuses(statuses);
      } catch {
        setAgentStatuses([
          { name: '收集Agent', status: 'idle', execution_count: 0 },
          { name: '清洗Agent', status: 'idle', execution_count: 0 },
          { name: '分析Agent', status: 'idle', execution_count: 0 },
          { name: '图谱Agent', status: 'idle', execution_count: 0 },
        ]);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const onMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key);
  };

  const pathSnippets = location.pathname.split('/').filter((i) => i);
  const breadcrumbItems = [
    { title: '黑灰产情报分析' },
    ...pathSnippets.map((_, index) => {
      const url = `/${pathSnippets.slice(0, index + 1).join('/')}`;
      return { title: breadcrumbMap[url] || url };
    }),
  ];

  const runningAgents = agentStatuses.filter((a) => a.status === 'running').length;

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          background: 'linear-gradient(180deg, #001529 0%, #002140 100%)',
          boxShadow: '2px 0 8px rgba(0,0,0,0.3)',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? '0' : '0 20px',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <RobotOutlined style={{ fontSize: 28, color: '#1890ff' }} />
          {!collapsed && (
            <Text
              strong
              style={{
                color: '#fff',
                marginLeft: 12,
                fontSize: 16,
                whiteSpace: 'nowrap',
                letterSpacing: 1,
              }}
            >
              情报分析Agent
            </Text>
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={onMenuClick}
          style={{
            borderRight: 0,
            background: 'transparent',
            marginTop: 8,
          }}
        />
      </Sider>
      <AntLayout style={{ marginLeft: collapsed ? 80 : 220, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            padding: '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <Space size="middle">
            {React.createElement(collapsed ? MenuUnfoldOutlined : MenuFoldOutlined, {
              style: { fontSize: 18, cursor: 'pointer' },
              onClick: () => setCollapsed(!collapsed),
            })}
            <Breadcrumb items={breadcrumbItems} />
          </Space>
          <Space size="middle">
            <Tooltip title={`${runningAgents} 个Agent运行中`}>
              <Badge status={runningAgents > 0 ? 'processing' : 'default'} />
              <WifiOutlined style={{ color: runningAgents > 0 ? '#52c41a' : '#999' }} />
            </Tooltip>
            <Tooltip title="威胁告警">
              <Badge count={0} size="small">
                <AlertOutlined style={{ fontSize: 18 }} />
              </Badge>
            </Tooltip>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {dayjs().format('YYYY-MM-DD HH:mm')}
            </Text>
          </Space>
        </Header>
        <Content
          style={{
            margin: 16,
            padding: 20,
            background: token.colorBgContainer,
            borderRadius: 8,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
        <Footer style={{ textAlign: 'center', padding: '8px 0', background: 'transparent' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            黑灰产情报分析Agent v1.0.0 · 安全态势感知平台
          </Text>
        </Footer>
      </AntLayout>
    </AntLayout>
  );
};

export default AppLayout;
