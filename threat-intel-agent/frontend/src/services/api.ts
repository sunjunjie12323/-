import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type {
  LoginResponse,
  DashboardStats,
  IntelligenceItem,
  IntelligenceDetail,
  IntelligenceStats,
  PaginatedResponse,
  BlackTalkTerm,
  BlackTalkDecodeResult,
  BlackTalkStats,
  GraphData,
  GraphEntity,
  GraphRelation,
  GraphStats,
  CommunityResult,
  PathResult,
  PIR,
  PIRTask,
  Report,
  TaskStatus,
  User,
} from '../types';
import { tokenStorage } from '../utils/tokenStorage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  validateStatus: (status) => status >= 200 && status < 300,
});

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const detail = (error.response.data as { detail?: string })?.detail;
      if (detail?.includes('已被撤销') || detail?.includes('无效令牌') || detail?.includes('expired')) {
        tokenStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

async function requestWithRetry<T>(fn: () => Promise<T>, retries = MAX_RETRIES): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    if (retries > 0 && error instanceof AxiosError && !error.response) {
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      return requestWithRetry(fn, retries - 1);
    }
    throw error;
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (data) {
      if (typeof data.detail === 'string') return data.detail;
      const errObj = data.error as Record<string, unknown> | undefined;
      if (errObj && typeof errObj.message === 'string') return errObj.message;
    }
    if (error.message) return error.message;
  }
  if (error instanceof Error) return error.message;
  return '未知错误';
}

export { getErrorMessage };

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', { username, password });
    tokenStorage.setToken(data.access_token);
    tokenStorage.setUser(data.user);
    return data;
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } finally {
      tokenStorage.clear();
    }
  },

  getMe: async (): Promise<User> => {
    const { data } = await apiClient.get<User>('/auth/me');
    return data;
  },

  register: async (username: string, password: string, role: string = 'viewer'): Promise<User> => {
    const { data } = await apiClient.post<User>('/auth/register', { username, password, role });
    return data;
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await apiClient.put('/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
};

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    return requestWithRetry(async () => {
      const { data } = await apiClient.get<DashboardStats>('/dashboard/stats');
      return data;
    });
  },

  getRecentIntelligence: async (limit: number = 10): Promise<PaginatedResponse<IntelligenceItem>> => {
    const { data } = await apiClient.get<PaginatedResponse<IntelligenceItem>>('/dashboard/recent', { params: { limit } });
    return data;
  },

  getThreatDistribution: async (): Promise<{ threat_levels: Record<string, number>; entity_types: Record<string, number> }> => {
    const { data } = await apiClient.get('/dashboard/threat-distribution');
    return data;
  },

  getAgentStatus: async (): Promise<{ agents: unknown; recent_executions: unknown[] }> => {
    const { data } = await apiClient.get('/dashboard/agent-status');
    return data;
  },
};

export const intelligenceApi = {
  list: async (params?: {
    source?: string;
    threat_level?: string;
    status?: string;
    search?: string;
    offset?: number;
    limit?: number;
  }): Promise<PaginatedResponse<IntelligenceItem>> => {
    const { data } = await apiClient.get<PaginatedResponse<IntelligenceItem>>('/intelligence', { params });
    return data;
  },

  get: async (id: string): Promise<IntelligenceDetail> => {
    const { data } = await apiClient.get<IntelligenceDetail>(`/intelligence/${id}`);
    return data;
  },

  create: async (intel: { source?: string; content: string; source_url?: string; metadata?: Record<string, unknown> }): Promise<IntelligenceItem> => {
    const { data } = await apiClient.post<IntelligenceItem>('/intelligence', intel);
    return data;
  },

  updateStatus: async (id: string, status: string): Promise<IntelligenceItem> => {
    const { data } = await apiClient.patch<IntelligenceItem>(`/intelligence/${id}/status`, { status });
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/intelligence/${id}`);
  },

  getStats: async (): Promise<IntelligenceStats> => {
    const { data } = await apiClient.get<IntelligenceStats>('/intelligence/stats');
    return data;
  },
};

export const blacktalkApi = {
  listTerms: async (params?: {
    category?: string;
    search?: string;
    offset?: number;
    limit?: number;
  }): Promise<PaginatedResponse<BlackTalkTerm>> => {
    const { data } = await apiClient.get<PaginatedResponse<BlackTalkTerm>>('/blacktalk/terms', { params });
    return data;
  },

  addTerm: async (term: string, meaning: string, context?: string, source?: string, category?: string): Promise<BlackTalkTerm> => {
    const { data } = await apiClient.post<BlackTalkTerm>('/blacktalk/terms', {
      term,
      meaning,
      context: context || '',
      source: source || 'manual',
      category: category || '',
    });
    return data;
  },

  decode: async (text: string): Promise<BlackTalkDecodeResult> => {
    const { data } = await apiClient.post<BlackTalkDecodeResult>('/blacktalk/decode', { text });
    return data;
  },

  search: async (q: string, n: number = 10): Promise<{ query: string; results: BlackTalkTerm[]; total: number }> => {
    const { data } = await apiClient.get('/blacktalk/search', { params: { q, n } });
    return data;
  },

  getStats: async (): Promise<BlackTalkStats> => {
    const { data } = await apiClient.get<BlackTalkStats>('/blacktalk/stats');
    return data;
  },
};

export const graphApi = {
  getData: async (params?: {
    entity_type?: string;
    search?: string;
    depth?: number;
  }): Promise<GraphData> => {
    const { data } = await apiClient.get<GraphData>('/graph/data', { params });
    return data;
  },

  getStats: async (): Promise<GraphStats> => {
    const { data } = await apiClient.get<GraphStats>('/graph/stats');
    return data;
  },

  listEntities: async (params?: {
    entity_type?: string;
    search?: string;
    offset?: number;
    limit?: number;
  }): Promise<PaginatedResponse<GraphEntity>> => {
    const { data } = await apiClient.get<PaginatedResponse<GraphEntity>>('/graph/entities', { params });
    return data;
  },

  getEntity: async (entityId: string): Promise<{ entity: GraphEntity; relations: GraphRelation[]; relation_count: number }> => {
    const { data } = await apiClient.get(`/graph/entities/${entityId}`);
    return data;
  },

  addEntity: async (type: string, value: string, context?: string, confidence?: number): Promise<{ id: string }> => {
    const { data } = await apiClient.post('/graph/entities', { type, value, context, confidence });
    return data;
  },

  addRelation: async (sourceEntityId: string, targetEntityId: string, type: string, confidence?: number, evidence?: string): Promise<{ id: string }> => {
    const { data } = await apiClient.post('/graph/relations', {
      source_entity_id: sourceEntityId,
      target_entity_id: targetEntityId,
      type,
      confidence,
      evidence,
    });
    return data;
  },

  findPath: async (sourceId: string, targetId: string, maxDepth: number = 5): Promise<PathResult> => {
    const { data } = await apiClient.post<PathResult>('/graph/path', {
      source_id: sourceId,
      target_id: targetId,
      max_depth: maxDepth,
    });
    return data;
  },

  findCommunities: async (algorithm: string = 'louvain', minSize: number = 2): Promise<CommunityResult> => {
    const { data } = await apiClient.post<CommunityResult>('/graph/communities', {
      algorithm,
      min_size: minSize,
    });
    return data;
  },

  getSubgraph: async (entityId: string, depth: number = 1): Promise<GraphData> => {
    const { data } = await apiClient.get<GraphData>(`/graph/subgraph/${entityId}`, { params: { depth } });
    return data;
  },
};

export const pirsApi = {
  list: async (params?: {
    status?: string;
    priority?: string;
    offset?: number;
    limit?: number;
  }): Promise<PaginatedResponse<PIR>> => {
    const { data } = await apiClient.get<PaginatedResponse<PIR>>('/pirs', { params });
    return data;
  },

  get: async (pirId: string): Promise<PIR> => {
    const { data } = await apiClient.get<PIR>(`/pirs/${pirId}`);
    return data;
  },

  create: async (pir: {
    title: string;
    description?: string;
    priority?: string;
    keywords?: string[];
    target_sources?: string[];
  }): Promise<PIR> => {
    const { data } = await apiClient.post<PIR>('/pirs', pir);
    return data;
  },

  update: async (pirId: string, updates: Partial<PIR>): Promise<PIR> => {
    const { data } = await apiClient.patch<PIR>(`/pirs/${pirId}`, updates);
    return data;
  },

  delete: async (pirId: string): Promise<void> => {
    await apiClient.delete(`/pirs/${pirId}`);
  },

  decompose: async (pirId: string): Promise<{ pir_id: string; tasks: PIRTask[]; task_count: number }> => {
    const { data } = await apiClient.post(`/pirs/${pirId}/decompose`);
    return data;
  },

  execute: async (pirId: string): Promise<{ task_id: string; pir_id: string; status: string }> => {
    const { data } = await apiClient.post(`/pirs/${pirId}/execute`);
    return data;
  },

  listTasks: async (pirId: string): Promise<PIRTask[]> => {
    const { data } = await apiClient.get(`/pirs/${pirId}/tasks`);
    return data;
  },
};

export const reportsApi = {
  list: async (params?: {
    report_type?: string;
    status?: string;
    offset?: number;
    limit?: number;
  }): Promise<PaginatedResponse<Report>> => {
    const { data } = await apiClient.get<PaginatedResponse<Report>>('/reports', { params });
    return data;
  },

  get: async (reportId: string): Promise<Report> => {
    const { data } = await apiClient.get<Report>(`/reports/${reportId}`);
    return data;
  },

  generate: async (params: {
    title: string;
    report_type?: string;
    pir_ids?: string[];
    intelligence_ids?: string[];
    context?: string;
  }): Promise<Report> => {
    const { data } = await apiClient.post<Report>('/reports/generate', params);
    return data;
  },

  update: async (reportId: string, updates: Partial<Report>): Promise<Report> => {
    const { data } = await apiClient.patch<Report>(`/reports/${reportId}`, updates);
    return data;
  },

  delete: async (reportId: string): Promise<void> => {
    await apiClient.delete(`/reports/${reportId}`);
  },

  export: async (reportId: string, format: string = 'markdown'): Promise<{ report_id: string; title: string; format: string; content: string }> => {
    const { data } = await apiClient.post(`/reports/${reportId}/export`, null, { params: { format } });
    return data;
  },
};

export const agentApi = {
  submitQuery: async (query: string, context?: Record<string, unknown>, maxIterations?: number): Promise<TaskStatus> => {
    const { data } = await apiClient.post<TaskStatus>('/agent/query', {
      query,
      context,
      max_iterations: maxIterations,
    });
    return data;
  },

  getStatus: async (): Promise<{ agents: unknown }> => {
    const { data } = await apiClient.get('/agent/status');
    return data;
  },

  getHistory: async (limit: number = 20): Promise<{ items: unknown[]; total: number }> => {
    const { data } = await apiClient.get('/agent/history', { params: { limit } });
    return data;
  },

  getExecution: async (executionId: string): Promise<Record<string, unknown>> => {
    const { data } = await apiClient.get(`/agent/execution/${executionId}`);
    return data;
  },

  getTaskStatus: async (taskId: string): Promise<TaskStatus> => {
    const { data } = await apiClient.get<TaskStatus>(`/agent/task/${taskId}`);
    return data;
  },

  triggerCollection: async (): Promise<TaskStatus> => {
    const { data } = await apiClient.post<TaskStatus>('/agent/collect');
    return data;
  },

  triggerAnalysis: async (): Promise<TaskStatus> => {
    const { data } = await apiClient.post<TaskStatus>('/agent/analyze');
    return data;
  },
};

export const api = {
  zeroDay: {
    detect: async (text: string) => {
      const { data } = await apiClient.post('/zero-day/detect', { text });
      return data;
    },
    trackDrift: async (term: string) => {
      const { data } = await apiClient.get(`/zero-day/drift/${encodeURIComponent(term)}`);
      return data;
    },
    trackMigration: async (term: string) => {
      const { data } = await apiClient.get(`/zero-day/migration/${encodeURIComponent(term)}`);
      return data;
    },
  },
  attackPrediction: {
    predict: async (entityId: string, depth: number = 3) => {
      const { data } = await apiClient.post('/attack-prediction/predict', { entity_id: entityId, depth });
      return data;
    },
    simulate: async (entityId: string, steps: number = 5) => {
      const { data } = await apiClient.post('/attack-prediction/simulate', { entity_id: entityId, steps });
      return data;
    },
    earlyWarning: async (entityId: string) => {
      const { data } = await apiClient.post('/attack-prediction/early-warning', { entity_id: entityId });
      return data;
    },
  },
  provenance: {
    record: async (params: any) => {
      const { data } = await apiClient.post('/provenance/record', params);
      return data;
    },
    verify: async (intelligenceId: string) => {
      const { data } = await apiClient.get(`/provenance/verify/${intelligenceId}`);
      return data;
    },
    evolution: async (intelligenceId: string) => {
      const { data } = await apiClient.get(`/provenance/evolution/${intelligenceId}`);
      return data;
    },
    hallucinationCheck: async (intelligenceId: string) => {
      const { data } = await apiClient.post(`/provenance/hallucination-check/${intelligenceId}`);
      return data;
    },
    chain: async (intelligenceId: string) => {
      const { data } = await apiClient.get(`/provenance/chain/${intelligenceId}`);
      return data;
    },
  },
  attribution: {
    fingerprint: async (entityId: string) => {
      const { data } = await apiClient.post(`/attribution/fingerprint/${entityId}`);
      return data;
    },
    findSame: async (entityId: string, threshold: number = 0.7) => {
      const { data } = await apiClient.post(`/attribution/find-same/${entityId}?threshold=${threshold}`);
      return data;
    },
    report: async (entityId: string) => {
      const { data } = await apiClient.get(`/attribution/report/${entityId}`);
      return data;
    },
  },
  decay: {
    getIntelligence: async (intelligenceId: string) => {
      const { data } = await apiClient.get(`/decay/intelligence/${intelligenceId}`);
      return data;
    },
    getCurve: async (intelligenceId: string) => {
      const { data } = await apiClient.get(`/decay/curve/${intelligenceId}`);
      return data;
    },
    batch: async () => {
      const { data } = await apiClient.get('/decay/batch');
      return data;
    },
    recommendations: async () => {
      const { data } = await apiClient.get('/decay/recommendations');
      return data;
    },
  },
  organism: {
    spawn: async (intelligenceId: string, species: string, initialData: Record<string, unknown> = {}) => {
      const { data } = await apiClient.post('/organism/spawn', {
        intelligence_id: intelligenceId,
        species,
        initial_data: initialData,
      });
      return data;
    },
    evolve: async (organismId: string, newData: Record<string, unknown> = {}, trigger: string = 'manual') => {
      const { data } = await apiClient.post('/organism/evolve', {
        organism_id: organismId,
        new_data: newData,
        trigger,
      });
      return data;
    },
    checkVitality: async (organismId: string) => {
      const { data } = await apiClient.get(`/organism/vitality/${encodeURIComponent(organismId)}`);
      return data;
    },
    getTimeline: async (organismId: string) => {
      const { data } = await apiClient.get(`/organism/timeline/${encodeURIComponent(organismId)}`);
      return data;
    },
    getOffspring: async (organismId: string, depth: number = 3) => {
      const { data } = await apiClient.get(`/organism/offspring/${encodeURIComponent(organismId)}?depth=${depth}`);
      return data;
    },
    registerPrediction: async (entityId: string, predictedSteps: Record<string, unknown>[], validationWindowHours: number = 168) => {
      const { data } = await apiClient.post('/organism/prediction/register', {
        entity_id: entityId,
        predicted_steps: predictedSteps,
        validation_window_hours: validationWindowHours,
      });
      return data;
    },
    validatePredictions: async () => {
      const { data } = await apiClient.post('/organism/prediction/validate');
      return data;
    },
    getPredictionAccuracy: async (entityId?: string) => {
      const { data } = await apiClient.get('/organism/prediction/accuracy', {
        params: entityId ? { entity_id: entityId } : {},
      });
      return data;
    },
    calibrateModel: async () => {
      const { data } = await apiClient.post('/organism/prediction/calibrate');
      return data;
    },
    archiveOrganism: async (organismId: string, cause: string = 'expired') => {
      const { data } = await apiClient.post(`/organism/gene/archive/${encodeURIComponent(organismId)}?cause=${cause}`);
      return data;
    },
    findGeneMatches: async (newIntelligenceData: Record<string, unknown>) => {
      const { data } = await apiClient.post('/organism/gene/match', {
        new_intelligence_data: newIntelligenceData,
      });
      return data;
    },
    inheritGenes: async (newOrganismId: string, parentGeneIds: string[]) => {
      const { data } = await apiClient.post('/organism/gene/inherit', {
        new_organism_id: newOrganismId,
        parent_gene_ids: parentGeneIds,
      });
      return data;
    },
    getGenealogy: async (organismId: string) => {
      const { data } = await apiClient.get(`/organism/genealogy/${encodeURIComponent(organismId)}`);
      return data;
    },
    runLifecycleCheck: async () => {
      const { data } = await apiClient.post('/organism/lifecycle-check');
      return data;
    },
    listOrganisms: async (species?: string, aliveOnly: boolean = true) => {
      const { data } = await apiClient.get('/organism/organisms', {
        params: { species, alive_only: aliveOnly },
      });
      return data;
    },
    listGenes: async () => {
      const { data } = await apiClient.get('/organism/genes');
      return data;
    },
  },
};

export default apiClient;
