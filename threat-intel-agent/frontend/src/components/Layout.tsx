import React, { useState, useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown, Typography, Tag, Space, theme } from 'antd';
import {
  DashboardOutlined,
  DatabaseOutlined,
  NodeIndexOutlined,
  TranslationOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  RobotOutlined,
  LogoutOutlined,
  UserOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { authApi } from '../services/api';
import type { User } from '../types';
import { tokenStorage } from '../utils/tokenStorage';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

interface LayoutProps {
  children: React.ReactNode;
}

const ALL_MENU_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘', roles: ['admin', 'analyst', 'viewer'] },
  { key: '/intelligence', icon: <DatabaseOutlined />, label: '情报管理', roles: ['admin', 'analyst', 'viewer'] },
  { key: '/graph', icon: <NodeIndexOutlined />, label: '知识图谱', roles: ['admin', 'analyst', 'viewer'] },
  { key: '/blacktalk', icon: <TranslationOutlined />, label: '黑话解码', roles: ['admin', 'analyst', 'viewer'] },
  { key: '/pirs', icon: <FileSearchOutlined />, label: 'PIR管理', roles: ['admin', 'analyst'] },
  { key: '/reports', icon: <FileTextOutlined />, label: '报告中心', roles: ['admin', 'analyst', 'viewer'] },
  { key: '/agent', icon: <RobotOutlined />, label: 'Agent', roles: ['admin', 'analyst'] },
];

const AppLayout: React.FC<LayoutProps> = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { token: themeToken } = theme.useToken();

  useEffect(() => {
    const stored = tokenStorage.getUser<User>();
    if (stored) {
      setUser(stored);
    }
  }, []);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore logout errors
    }
    setUser(null);
    navigate('/login');
  };

  const userRole = user?.role || 'viewer';

  const menuItems = ALL_MENU_ITEMS.filter((item) => item.roles.includes(userRole));

  const roleLabels: Record<string, { color: string; label: string }> = {
    admin: { color: 'red', label: '管理员' },
    analyst: { color: 'blue', label: '分析师' },
    viewer: { color: 'green', label: '观察者' },
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: user?.username || '用户',
      disabled: true,
    },
    {
      key: 'role',
      icon: <SettingOutlined />,
      label: (
        <span>
          角色: {user?.role ? <Tag color={roleLabels[user.role]?.color}>{roleLabels[user.role]?.label || user.role}</Tag> : '-'}
        </span>
      ),
      disabled: true,
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ];

  const handleMenuClick = (info: { key: string }) => {
    navigate(info.key);
  };

  const handleUserMenuClick = (info: { key: string }) => {
    if (info.key === 'logout') {
      handleLogout();
    }
  };

  const selectedKey = ALL_MENU_ITEMS.find((item) => {
    if (item.key === '/') return location.pathname === '/';
    return location.pathname.startsWith(item.key);
  })?.key || '/';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 16px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}>
          <RobotOutlined style={{ fontSize: 24, color: '#1890ff' }} />
          {!collapsed && (
            <Text strong style={{ color: '#fff', marginLeft: 8, whiteSpace: 'nowrap', fontSize: 14 }}>
              情报分析系统
            </Text>
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'margin-left 0.2s' }}>
        <Header style={{
          padding: '0 24px',
          background: themeToken.colorBgContainer,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          position: 'sticky',
          top: 0,
          zIndex: 1,
        }}>
          <Dropdown
            menu={{ items: userMenuItems, onClick: handleUserMenuClick }}
            placement="bottomRight"
          >
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />
              <Text>{user?.username || '未登录'}</Text>
              {user?.role && (
                <Tag color={roleLabels[user.role]?.color} style={{ marginLeft: 4 }}>
                  {roleLabels[user.role]?.label || user.role}
                </Tag>
              )}
            </Space>
          </Dropdown>
        </Header>
        <Content style={{
          margin: 24,
          padding: 24,
          background: themeToken.colorBgContainer,
          borderRadius: themeToken.borderRadiusLG,
          minHeight: 280,
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
