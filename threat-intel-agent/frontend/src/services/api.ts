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
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  ChangePasswordRequest,
  Task,
  TaskListResponse,
  ApiError,
} from '../types';

const TOKEN_KEY = 'threat_intel_token';
const USER_KEY = 'threat_intel_user';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

const processQueue = (error: unknown) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(undefined);
    }
  });
  failedQueue = [];
};

api.interceptors.request.use(
  (config) => {
    const token = getToken();
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
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => api(originalRequest));
      }
      originalRequest._retry = true;
      isRefreshing = true;
      clearAuth();
      processQueue(error);
      isRefreshing = false;
      window.location.href = '/login';
      return Promise.reject(error);
    }
    return Promise.reject(error);
  },
);

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function getStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

function setStoredUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiError | undefined;
    if (data?.error?.message) {
      return data.error.message;
    }
    if (error.message === 'Network Error') {
      return '网络连接失败，请检查网络或服务是否可用';
    }
    if (error.code === 'ECONNABORTED') {
      return '请求超时，请稍后重试';
    }
    return error.message || '请求失败';
  }
  if (error instanceof Error) {
    return error.message;
  }
  return '未知错误';
}

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const { data: resp } = await api.post('/auth/login', data);
    setToken(resp.access_token);
    setStoredUser(resp.user);
    return resp;
  },

  register: async (data: RegisterRequest): Promise<User> => {
    const { data: resp } = await api.post('/auth/register', data);
    return resp;
  },

  getMe: async (): Promise<User> => {
    const { data: resp } = await api.get('/auth/me');
    setStoredUser(resp);
    return resp;
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } catch {
      // ignore errors on logout
    } finally {
      clearAuth();
    }
  },

  changePassword: async (data: ChangePasswordRequest): Promise<void> => {
    await api.put('/auth/password', data);
  },

  listUsers: async (): Promise<User[]> => {
    const { data } = await api.get('/auth/users');
    return data;
  },
};

export const taskApi = {
  getTasks: async (params?: { status?: string; offset?: number; limit?: number }): Promise<TaskListResponse> => {
    const { data } = await api.get('/tasks', { params });
    return data;
  },

  getTask: async (taskId: string): Promise<Task> => {
    const { data } = await api.get(`/tasks/${taskId}`);
    return data;
  },

  cancelTask: async (taskId: string): Promise<void> => {
    await api.post(`/tasks/${taskId}/cancel`);
  },

  getTaskResult: async (taskId: string): Promise<{ task_id: string; type: string; result: unknown; completed_at: string | null }> => {
    const { data } = await api.get(`/tasks/${taskId}/result`);
    return data;
  },

  waitForCompletion: async (taskId: string, intervalMs = 2000, maxAttempts = 60): Promise<Task> => {
    for (let i = 0; i < maxAttempts; i++) {
      const task = await taskApi.getTask(taskId);
      if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
        return task;
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
    throw new Error('任务轮询超时');
  },
};

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

export { getToken, setToken, clearAuth, getStoredUser, setStoredUser, extractErrorMessage };
export default api;
