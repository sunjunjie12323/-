export interface Intelligence {
  id: string;
  title: string;
  content: string;
  source: string;
  source_type: 'telegram' | 'dark_web' | 'forum' | 'social_media' | 'other';
  threat_level: 'critical' | 'high' | 'medium' | 'low' | 'info';
  collected_at: string;
  processed_at?: string;
  entities: Entity[];
  tags: string[];
  raw_content?: string;
  decoded_content?: string;
  is_processed: boolean;
}

export interface Entity {
  id: string;
  name: string;
  entity_type: 'person' | 'organization' | 'account' | 'phone' | 'website' | 'crypto_wallet' | 'ip' | 'location' | 'tool' | 'other';
  properties: Record<string, string>;
  confidence: number;
  first_seen: string;
  last_seen: string;
  mention_count: number;
}

export interface Relation {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  properties: Record<string, string>;
  confidence: number;
  evidence: string[];
  created_at: string;
}

export interface PIR {
  id: string;
  title: string;
  description: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status: 'draft' | 'active' | 'executing' | 'completed' | 'archived';
  created_at: string;
  updated_at: string;
  tasks: PIRTask[];
  fulfillment_score: number;
  generated_reports: string[];
  keywords: string[];
  target_entities: string[];
}

export interface PIRTask {
  id: string;
  pir_id: string;
  task_type: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: string;
  created_at: string;
  completed_at?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphNode {
  id: string;
  label: string;
  entity_type: string;
  properties: Record<string, string>;
  confidence: number;
  community?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  properties: Record<string, string>;
  confidence: number;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  entity_type_distribution: Record<string, number>;
  relation_type_distribution: Record<string, number>;
  community_count: number;
}

export interface BlackTalkTerm {
  id: string;
  term: string;
  meaning: string;
  category: string;
  confidence: number;
  is_auto_learned: boolean;
  source: string;
  created_at: string;
  usage_count: number;
  related_terms: string[];
}

export interface DecodeResult {
  original_text: string;
  decoded_text: string;
  found_terms: Array<{
    term: string;
    meaning: string;
    position: [number, number];
  }>;
}

export interface Report {
  id: string;
  title: string;
  pir_id: string;
  status: 'generating' | 'completed' | 'failed';
  created_at: string;
  sections: ReportSection[];
  evidence_chain: EvidenceItem[];
  summary: string;
}

export interface ReportSection {
  title: string;
  content: string;
  type: 'overview' | 'analysis' | 'evidence' | 'recommendation' | 'appendix';
}

export interface EvidenceItem {
  id: string;
  description: string;
  source: string;
  confidence: number;
  related_entities: string[];
  timestamp: string;
}

export interface AgentStatus {
  name: string;
  status: 'idle' | 'running' | 'error';
  current_task?: string;
  last_execution?: string;
  execution_count: number;
}

export interface ExecutionRecord {
  id: string;
  query: string;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  result_summary?: string;
  agent_name: string;
}

export interface DashboardStats {
  total_intelligence: number;
  active_pirs: number;
  threat_alerts: number;
  graph_nodes: number;
  threat_level_distribution: Record<string, number>;
  source_type_distribution: Record<string, number>;
  recent_intelligence: Intelligence[];
  agent_statuses: AgentStatus[];
  recent_executions: ExecutionRecord[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SearchParams {
  query?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  filters?: Record<string, string | string[]>;
}
