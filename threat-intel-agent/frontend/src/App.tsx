import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Intelligence from './pages/Intelligence';
import GraphView from './pages/GraphView';
import PIRManager from './pages/PIRManager';
import BlackTalk from './pages/BlackTalk';
import Reports from './pages/Reports';
import Login from './pages/Login';
import AgentPage from './pages/Agent';

const getToken = (): string | null => localStorage.getItem('access_token');

const AuthGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = getToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <Layout>{children}</Layout>;
};

const LoginGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = getToken();
  if (token) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1890ff',
          borderRadius: 6,
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              <LoginGuard>
                <Login onLoginSuccess={() => window.location.href = '/'} />
              </LoginGuard>
            }
          />
          <Route
            path="/"
            element={
              <AuthGuard>
                <Dashboard />
              </AuthGuard>
            }
          />
          <Route
            path="/intelligence"
            element={
              <AuthGuard>
                <Intelligence />
              </AuthGuard>
            }
          />
          <Route
            path="/graph"
            element={
              <AuthGuard>
                <GraphView />
              </AuthGuard>
            }
          />
          <Route
            path="/pirs"
            element={
              <AuthGuard>
                <PIRManager />
              </AuthGuard>
            }
          />
          <Route
            path="/blacktalk"
            element={
              <AuthGuard>
                <BlackTalk />
              </AuthGuard>
            }
          />
          <Route
            path="/reports"
            element={
              <AuthGuard>
                <Reports />
              </AuthGuard>
            }
          />
          <Route
            path="/agent"
            element={
              <AuthGuard>
                <AgentPage />
              </AuthGuard>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
