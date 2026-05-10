import React, { useState, useEffect } from 'react';
import { Layout as AntLayout, Menu, Avatar, Dropdown, Badge, Tag, Space, Typography } from 'antd';
import {
  DashboardOutlined,
  SearchOutlined,
  ApartmentOutlined,
  AimOutlined,
  MessageOutlined,
  FileTextOutlined,
  UserOutlined,
  LogoutOutlined,
  WifiOutlined,
  DisconnectOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { authApi, taskApi, getStoredUser, getToken } from '../services/api';
import type { User, Task } from '../types';

const { Header, Sider, Content } = AntLayout;
const { Text } = Typography;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/intelligence', icon: <SearchOutlined />, label: '情报中心' },
  { key: '/graph', icon: <ApartmentOutlined />, label: '关系图谱' },
  { key: '/pir', icon: <AimOutlined />, label: 'PIR管理' },
  { key: '/blacktalk', icon: <MessageOutlined />, label: '黑话解码' },
  { key: '/reports', icon: <FileTextOutlined />, label: '分析报告' },
];

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [connected, setConnected] = useState(true);
  const [runningTasks, setRunningTasks] = useState(0);

  useEffect(() => {
    const user = getStoredUser();
    setCurrentUser(user);
    setConnected(!!getToken());
  }, []);

  useEffect(() => {
    const checkTasks = async () => {
      try {
        const result = await taskApi.getTasks({ status: 'running', limit: 1 });
        setRunningTasks(result.total);
        setConnected(true);
      } catch {
        setConnected(false);
      }
    };
    checkTasks();
    const interval = setInterval(checkTasks, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = async () => {
    await authApi.logout();
    navigate('/login', { replace: true });
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: `${currentUser?.username || '用户'} (${currentUser?.role === 'admin' ? '管理员' : currentUser?.role === 'analyst' ? '分析师' : '观察者'})`,
      disabled: true,
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        <div
          style={{
            height: 48,
            margin: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(255,255,255,0.1)',
            borderRadius: 6,
          }}
        >
          <Text
            strong
            style={{
              color: '#fff',
              fontSize: collapsed ? 14 : 16,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
            }}
          >
            {collapsed ? '黑灰' : '黑灰产情报分析'}
          </Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout style={{ marginLeft: collapsed ? 80 : 200, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
            position: 'sticky',
            top: 0,
            zIndex: 9,
          }}
        >
          <Space size="large">
            <Space size="small">
              {connected ? (
                <Tag icon={<WifiOutlined />} color="success" style={{ margin: 0 }}>
                  已连接
                </Tag>
              ) : (
                <Tag icon={<DisconnectOutlined />} color="error" style={{ margin: 0 }}>
                  未连接
                </Tag>
              )}
            </Space>
            {runningTasks > 0 && (
              <Badge count={runningTasks} size="small" offset={[2, 0]}>
                <Tag icon={<SyncOutlined spin />} color="processing" style={{ margin: 0 }}>
                  执行中
                </Tag>
              </Badge>
            )}
          </Space>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar
                size="small"
                icon={<UserOutlined />}
                style={{ backgroundColor: currentUser?.role === 'admin' ? '#f5222d' : currentUser?.role === 'analyst' ? '#1890ff' : '#52c41a' }}
              />
              <Text style={{ fontSize: 13 }}>{currentUser?.username || '未登录'}</Text>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16, padding: 20, background: '#f5f5f5', minHeight: 'auto', borderRadius: 8 }}>
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
};

export default Layout;
