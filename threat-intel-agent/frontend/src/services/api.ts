import axios from 'axios';
import type {
  Intelligence,
  Entity,
  PIR,
  GraphData,
  GraphStats,
  BlackTalkTerm,
  DecodeResult,
  Report,
  AgentStatus,
  ExecutionRecord,
  DashboardStats,
  PaginatedResponse,
  SearchParams,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export const intelligenceApi = {
  getIntelligences: async (params?: SearchParams): Promise<PaginatedResponse<Intelligence>> => {
    const { data } = await api.get('/intelligence', { params });
    return data;
  },
  getIntelDetail: async (id: string): Promise<Intelligence> => {
    const { data } = await api.get(`/intelligence/${id}`);
    return data;
  },
  createIntel: async (intel: Partial<Intelligence>): Promise<Intelligence> => {
    const { data } = await api.post('/intelligence', intel);
    return data;
  },
  searchIntel: async (params: SearchParams): Promise<PaginatedResponse<Intelligence>> => {
    const { data } = await api.post('/intelligence/search', params);
    return data;
  },
  batchAnalyze: async (ids: string[]): Promise<void> => {
    await api.post('/intelligence/batch-analyze', { ids });
  },
  batchClean: async (ids: string[]): Promise<void> => {
    await api.post('/intelligence/batch-clean', { ids });
  },
};

export const entityApi = {
  getEntities: async (params?: SearchParams): Promise<PaginatedResponse<Entity>> => {
    const { data } = await api.get('/entities', { params });
    return data;
  },
  getEntityDetail: async (id: string): Promise<Entity> => {
    const { data } = await api.get(`/entities/${id}`);
    return data;
  },
  searchEntities: async (params: SearchParams): Promise<PaginatedResponse<Entity>> => {
    const { data } = await api.post('/entities/search', params);
    return data;
  },
};

export const pirApi = {
  getPIRs: async (params?: SearchParams): Promise<PaginatedResponse<PIR>> => {
    const { data } = await api.get('/pirs', { params });
    return data;
  },
  createPIR: async (pir: Partial<PIR>): Promise<PIR> => {
    const { data } = await api.post('/pirs', pir);
    return data;
  },
  getPIRDetail: async (id: string): Promise<PIR> => {
    const { data } = await api.get(`/pirs/${id}`);
    return data;
  },
  updatePIR: async (id: string, pir: Partial<PIR>): Promise<PIR> => {
    const { data } = await api.put(`/pirs/${id}`, pir);
    return data;
  },
  decomposePIR: async (id: string): Promise<PIR> => {
    const { data } = await api.post(`/pirs/${id}/decompose`);
    return data;
  },
  executePIR: async (id: string): Promise<ExecutionRecord> => {
    const { data } = await api.post(`/pirs/${id}/execute`);
    return data;
  },
};

export const graphApi = {
  getGraphData: async (params?: { entity_id?: string; depth?: number }): Promise<GraphData> => {
    const { data } = await api.get('/graph', { params });
    return data;
  },
  getEntityRelations: async (entityId: string): Promise<GraphData> => {
    const { data } = await api.get(`/graph/entity/${entityId}`);
    return data;
  },
  findPath: async (sourceId: string, targetId: string): Promise<GraphData> => {
    const { data } = await api.get('/graph/path', { params: { source: sourceId, target: targetId } });
    return data;
  },
  findCommunities: async (): Promise<GraphData> => {
    const { data } = await api.post('/graph/communities');
    return data;
  },
  getGraphStats: async (): Promise<GraphStats> => {
    const { data } = await api.get('/graph/stats');
    return data;
  },
};

export const blackTalkApi = {
  getBlackTalkTerms: async (params?: SearchParams): Promise<PaginatedResponse<BlackTalkTerm>> => {
    const { data } = await api.get('/blacktalk', { params });
    return data;
  },
  searchBlackTalk: async (query: string): Promise<BlackTalkTerm[]> => {
    const { data } = await api.get('/blacktalk/search', { params: { query } });
    return data;
  },
  addBlackTalkTerm: async (term: Partial<BlackTalkTerm>): Promise<BlackTalkTerm> => {
    const { data } = await api.post('/blacktalk', term);
    return data;
  },
  decodeText: async (text: string): Promise<DecodeResult> => {
    const { data } = await api.post('/blacktalk/decode', { text });
    return data;
  },
};

export const reportApi = {
  getReports: async (params?: SearchParams): Promise<PaginatedResponse<Report>> => {
    const { data } = await api.get('/reports', { params });
    return data;
  },
  getReportDetail: async (id: string): Promise<Report> => {
    const { data } = await api.get(`/reports/${id}`);
    return data;
  },
  generateReport: async (pirId: string): Promise<Report> => {
    const { data } = await api.post('/reports/generate', { pir_id: pirId });
    return data;
  },
};

export const agentApi = {
  executeQuery: async (query: string): Promise<ExecutionRecord> => {
    const { data } = await api.post('/agent/execute', { query });
    return data;
  },
  getAgentStatus: async (): Promise<AgentStatus[]> => {
    const { data } = await api.get('/agent/status');
    return data;
  },
  getExecutionHistory: async (params?: SearchParams): Promise<PaginatedResponse<ExecutionRecord>> => {
    const { data } = await api.get('/agent/history', { params });
    return data;
  },
};

export const dashboardApi = {
  getDashboardStats: async (): Promise<DashboardStats> => {
    const { data } = await api.get('/dashboard/stats');
    return data;
  },
};

export default api;
