import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Intelligence from './pages/Intelligence';
import GraphView from './pages/GraphView';
import PIRManager from './pages/PIRManager';
import BlackTalk from './pages/BlackTalk';
import Reports from './pages/Reports';

const App: React.FC = () => {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1890ff',
          borderRadius: 6,
          fontSize: 14,
          colorBgContainer: '#ffffff',
          colorBgLayout: '#f0f2f5',
        },
        components: {
          Layout: {
            siderBg: '#001529',
            headerBg: '#ffffff',
          },
          Menu: {
            darkItemBg: 'transparent',
            darkSubMenuItemBg: 'transparent',
            darkItemSelectedBg: '#1890ff',
            darkItemHoverBg: 'rgba(24, 144, 255, 0.15)',
          },
          Card: {
            borderRadiusLG: 8,
          },
          Table: {
            borderRadiusLG: 8,
          },
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/intelligence" element={<Intelligence />} />
            <Route path="/graph" element={<GraphView />} />
            <Route path="/pir" element={<PIRManager />} />
            <Route path="/blacktalk" element={<BlackTalk />} />
            <Route path="/reports" element={<Reports />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
