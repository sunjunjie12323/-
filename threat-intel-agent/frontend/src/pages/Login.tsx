import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Checkbox, message } from 'antd';
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { authApi, getErrorMessage } from '../services/api';

const { Title, Text } = Typography;

interface LoginProps {
  onLoginSuccess: () => void;
}

const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form] = Form.useForm();

  const handleLogin = async (values: { username: string; password: string; remember: boolean }) => {
    try {
      setLoading(true);
      setError(null);
      const result = await authApi.login(values.username, values.password);
      if (values.remember) {
        localStorage.setItem('tia_remember_user', values.username);
      } else {
        localStorage.removeItem('tia_remember_user');
      }
      message.success(`欢迎回来，${result.user.username}！`);
      onLoginSuccess();
    } catch (err) {
      const errMsg = getErrorMessage(err);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const rememberedUser = localStorage.getItem('tia_remember_user') || '';

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
    }}>
      <Card
        style={{
          width: 400,
          boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
          borderRadius: 8,
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <SafetyCertificateOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 12 }} />
          <Title level={3} style={{ marginBottom: 4 }}>黑灰产情报分析系统</Title>
          <Text type="secondary">Threat Intelligence Analysis Platform</Text>
        </div>

        {error && (
          <Alert
            message="登录失败"
            description={error}
            type="error"
            showIcon
            closable
            onClose={() => setError(null)}
            style={{ marginBottom: 16 }}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          onFinish={handleLogin}
          initialValues={{ remember: !!rememberedUser, username: rememberedUser }}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              size="large"
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              size="large"
              autoComplete="current-password"
            />
          </Form.Item>

          <Form.Item name="remember" valuePropName="checked">
            <Checkbox>记住用户名</Checkbox>
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            默认管理员: admin / admin123
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default Login;
