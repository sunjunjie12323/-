import React, { useState, useCallback } from 'react';
import {
  Card,
  Tabs,
  Tag,
  Table,
  Button,
  Input,
  Progress,
  Timeline,
  Descriptions,
  Alert,
  Spin,
  Empty,
  Statistic,
  Row,
  Col,
  Space,
  Typography,
  Steps,
  message,
} from 'antd';
import {
  SearchOutlined,
  ThunderboltOutlined,
  LinkOutlined,
  ForkOutlined,
  FieldTimeOutlined,
  HeartOutlined,
} from '@ant-design/icons';
import { api } from '../services/api';
import AttackChainGraph from '../components/AttackChainGraph';
import AttributionSankey from '../components/AttributionSankey';

const { Title, Text } = Typography;
const { TextArea } = Input;

const ZeroDayTab: React.FC = () => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [driftTerm, setDriftTerm] = useState('');
  const [driftLoading, setDriftLoading] = useState(false);
  const [driftData, setDriftData] = useState<any>(null);

  const handleDetect = async () => {
    if (!text.trim()) {
      message.warning('请输入待检测文本');
      return;
    }
    setLoading(true);
    try {
      const res = await api.zeroDay.detect(text);
      setResults(res.detections || res.results || []);
    } catch (err: any) {
      message.error(err?.message || '零日检测失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDrift = async () => {
    if (!driftTerm.trim()) {
      message.warning('请输入追踪术语');
      return;
    }
    setDriftLoading(true);
    try {
      const res = await api.zeroDay.trackDrift(driftTerm);
      setDriftData(res);
    } catch (err: any) {
      message.error(err?.message || '语义漂移追踪失败');
    } finally {
      setDriftLoading(false);
    }
  };

  const categoryColors: Record<string, string> = {
    drug: 'purple',
    fraud: 'orange',
    gambling: 'red',
    weapon: 'volcano',
    other: 'default',
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="零日黑话检测">
        <TextArea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="输入可疑文本，检测零日黑话..."
        />
        <Button
          type="primary"
          icon={<SearchOutlined />}
          onClick={handleDetect}
          loading={loading}
          style={{ marginTop: 12 }}
        >
          检测零日黑话
        </Button>
      </Card>

      {loading && <Spin tip="检测中..." />}

      {!loading && results.length > 0 && (
        <Row gutter={[16, 16]}>
          {results.map((item: any, idx: number) => (
            <Col span={12} key={idx}>
              <Card size="small">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space>
                    <Text strong style={{ fontSize: 16 }}>{item.term || item.word}</Text>
                    <Tag color="red">NEW</Tag>
                    <Tag color={categoryColors[item.category] || 'default'}>{item.category || '未知'}</Tag>
                  </Space>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="正常含义">{item.normal_meaning || item.normalMeaning || '-'}</Descriptions.Item>
                    <Descriptions.Item label="犯罪含义">{item.criminal_meaning || item.criminalMeaning || '-'}</Descriptions.Item>
                  </Descriptions>
                  <div>
                    <Text type="secondary">置信度</Text>
                    <Progress
                      percent={Math.round((item.confidence || 0) * 100)}
                      status="active"
                      style={{ marginTop: 4 }}
                    />
                  </div>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {!loading && results.length === 0 && text && (
        <Empty description="未检测到零日黑话" />
      )}

      <Card title="语义漂移追踪">
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={driftTerm}
            onChange={(e) => setDriftTerm(e.target.value)}
            placeholder="输入术语追踪语义漂移..."
          />
          <Button type="primary" onClick={handleDrift} loading={driftLoading}>
            追踪漂移
          </Button>
        </Space.Compact>
        {driftLoading && <Spin style={{ marginTop: 16 }} />}
        {driftData && !driftLoading && (
          <Timeline style={{ marginTop: 16 }}>
            {(driftData.drifts || driftData.timeline || []).map((d: any, idx: number) => (
              <Timeline.Item key={idx} color={idx === 0 ? 'green' : 'blue'}>
                <Text strong>{d.period || d.time || `阶段 ${idx + 1}`}</Text>
                <br />
                <Text>含义: {d.meaning || d.new_meaning || '-'}</Text>
                <br />
                <Text type="secondary">变化: {d.change || d.description || '-'}</Text>
              </Timeline.Item>
            ))}
          </Timeline>
        )}
      </Card>
    </Space>
  );
};

const AttackPredictionTab: React.FC = () => {
  const [entityName, setEntityName] = useState('');
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<any>(null);

  const handlePredict = async () => {
    if (!entityName.trim()) {
      message.warning('请输入实体名称');
      return;
    }
    setLoading(true);
    try {
      const res = await api.attackPrediction.predictByName(entityName);
      setPrediction(res.predictions || res);
    } catch (err: any) {
      message.error(err?.message || '攻击预测失败');
    } finally {
      setLoading(false);
    }
  };

  const riskColors: Record<string, string> = {
    critical: 'red',
    high: 'orange',
    medium: 'gold',
    low: 'green',
  };

  const stepColors: Record<string, string> = {
    critical: '#ff4d4f',
    high: '#fa8c16',
    medium: '#fadb14',
    low: '#52c41a',
  };

  const steps = prediction?.steps || prediction?.predictions || prediction?.path || [];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="攻击链预测">
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={entityName}
            onChange={(e) => setEntityName(e.target.value)}
            placeholder="输入实体名称（如IP地址、域名等）..."
          />
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={handlePredict} loading={loading}>
            预测攻击路径
          </Button>
        </Space.Compact>
      </Card>

      {loading && <Spin tip="预测中..." />}

      {!loading && prediction && steps.length > 0 && (
        <Card title="预测攻击路径">
          <Steps
            direction="vertical"
            current={-1}
            items={steps.map((step: any, idx: number) => ({
              title: (
                <Space>
                  <Text strong>步骤 {idx + 1}: {step.action || step.name || step.description}</Text>
                  <Tag color={riskColors[step.risk_level || step.risk || 'medium']}>
                    {(step.risk_level || step.risk || 'medium').toUpperCase()}
                  </Tag>
                </Space>
              ),
              description: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text>概率: {typeof step.probability === 'number' ? `${(step.probability * 100).toFixed(1)}%` : step.probability}</Text>
                  <Text>时间窗口: {step.time_window || step.timeWindow || '-'}</Text>
                  <Text type="secondary">推理: {step.reasoning || step.reason || '-'}</Text>
                </Space>
              ),
              status: 'wait' as const,
            }))}
          />
        </Card>
      )}

      {prediction && steps.length > 0 && (
        <Card title="攻击链可视化">
          <AttackChainGraph
            predictions={steps.map((step: any, idx: number) => ({
              step: idx + 1,
              technique_name: step.action || step.name || step.description || step.technique_name || '',
              probability: typeof step.probability === 'number' ? step.probability : 0.5,
              risk_level: step.risk_level || step.risk || 'medium',
              reasoning: step.reasoning || step.reason || '',
            }))}
            entityName={entityName}
          />
        </Card>
      )}

      {!loading && prediction && steps.length === 0 && (
        <Empty description="未发现攻击路径" />
      )}
    </Space>
  );
};

const ProvenanceTab: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [verifyResult, setVerifyResult] = useState<any>(null);
  const [chainData, setChainData] = useState<any>(null);
  const [hallucinationLoading, setHallucinationLoading] = useState(false);
  const [hallucinationResult, setHallucinationResult] = useState<any>(null);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [resolvedIntelligenceId, setResolvedIntelligenceId] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      message.warning('请输入搜索内容');
      return;
    }
    setSearchLoading(true);
    try {
      const res = await api.provenance.searchByContent(searchQuery);
      setSearchResults(res.results || []);
      if (res.results && res.results.length > 0) {
        const firstId = res.results[0].intelligence_id;
        setResolvedIntelligenceId(firstId);
      }
    } catch (err: any) {
      message.error(err?.message || '搜索失败');
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleVerify = async () => {
    const intelId = resolvedIntelligenceId;
    if (!intelId) {
      message.warning('请先搜索选择情报');
      return;
    }
    setLoading(true);
    try {
      const [verifyRes, chainRes] = await Promise.all([
        api.provenance.verify(intelId),
        api.provenance.chain(intelId),
      ]);
      setVerifyResult(verifyRes);
      setChainData(chainRes);
    } catch (err: any) {
      message.error(err?.message || '溯源验证失败');
    } finally {
      setLoading(false);
    }
  };

  const handleHallucinationCheck = async () => {
    const intelId = resolvedIntelligenceId;
    if (!intelId) {
      message.warning('请先搜索选择情报');
      return;
    }
    setHallucinationLoading(true);
    try {
      const res = await api.provenance.hallucinationCheck(intelId);
      setHallucinationResult(res);
    } catch (err: any) {
      message.error(err?.message || '幻觉检测失败');
    } finally {
      setHallucinationLoading(false);
    }
  };

  const stageColors: Record<string, string> = {
    collected: 'blue',
    cleaned: 'cyan',
    analyzed: 'green',
    reported: 'gold',
  };

  const chain = chainData?.chain || chainData?.stages || [];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="情报溯源链验证">
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="输入情报内容/描述关键词搜索..."
              onPressEnter={handleSearch}
            />
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch} loading={searchLoading}>
              搜索
            </Button>
          </Space.Compact>
          {searchResults.length > 0 && (
            <div>
              <Text type="secondary">搜索结果（点击选择）：</Text>
              <div style={{ marginTop: 8 }}>
                {searchResults.map((r: any, idx: number) => (
                  <Card
                    key={idx}
                    size="small"
                    style={{
                      marginBottom: 8,
                      cursor: 'pointer',
                      border: resolvedIntelligenceId === r.intelligence_id ? '2px solid #1890ff' : undefined,
                    }}
                    onClick={() => setResolvedIntelligenceId(r.intelligence_id)}
                  >
                    <Space direction="vertical" size={0}>
                      <Space>
                        <Tag color="blue">{r.stage}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>{r.intelligence_id.substring(0, 16)}...</Text>
                      </Space>
                      <Text ellipsis style={{ maxWidth: 500 }}>{r.snippet}</Text>
                    </Space>
                  </Card>
                ))}
              </div>
            </div>
          )}
          {resolvedIntelligenceId && (
            <Space>
              <Text>已选择: <Text code>{resolvedIntelligenceId.substring(0, 16)}...</Text></Text>
              <Button type="primary" icon={<LinkOutlined />} onClick={handleVerify} loading={loading}>
                验证溯源链
              </Button>
              <Button onClick={handleHallucinationCheck} loading={hallucinationLoading}>
                幻觉检测
              </Button>
            </Space>
          )}
        </Space>
      </Card>

      {loading && <Spin tip="验证中..." />}

      {!loading && verifyResult && (
        <Alert
          type={verifyResult.valid || verifyResult.is_valid ? 'success' : 'error'}
          message={verifyResult.valid || verifyResult.is_valid ? '溯源链验证通过' : '溯源链验证失败'}
          description={verifyResult.message || verifyResult.reason || ''}
          showIcon
        />
      )}

      {!loading && chain.length > 0 && (
        <Card title="溯源链">
          <Timeline>
            {chain.map((stage: any, idx: number) => (
              <Timeline.Item key={idx} color={stageColors[stage.stage || stage.type] || 'blue'}>
                <Space direction="vertical">
                  <Space>
                    <Tag color={stageColors[stage.stage || stage.type] || 'blue'}>
                      {stage.stage || stage.type || `阶段 ${idx + 1}`}
                    </Tag>
                    <Text type="secondary">{stage.timestamp || stage.time || '-'}</Text>
                  </Space>
                  <Text>操作类型: {stage.operator_type || stage.operatorType || '-'}</Text>
                  <Text>置信度变化: {stage.confidence_change || stage.confidenceChange || stage.confidence || '-'}</Text>
                </Space>
              </Timeline.Item>
            ))}
          </Timeline>
        </Card>
      )}

      {hallucinationResult && (
        <Card title="幻觉检测结果">
          <Descriptions column={1}>
            <Descriptions.Item label="幻觉分数">
              <Progress
                percent={Math.round((hallucinationResult.hallucination_score || hallucinationResult.score || 0) * 100)}
                status={
                  (hallucinationResult.hallucination_score || hallucinationResult.score || 0) > 0.5
                    ? 'exception'
                    : 'success'
                }
              />
            </Descriptions.Item>
            <Descriptions.Item label="风险等级">
              <Tag color={(hallucinationResult.hallucination_score || hallucinationResult.score || 0) > 0.5 ? 'red' : 'green'}>
                {(hallucinationResult.hallucination_score || hallucinationResult.score || 0) > 0.5 ? '高风险' : '低风险'}
              </Tag>
            </Descriptions.Item>
            {hallucinationResult.details && (
              <Descriptions.Item label="详情">{hallucinationResult.details}</Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      )}
    </Space>
  );
};

const AttributionTab: React.FC = () => {
  const [entityName, setEntityName] = useState('');
  const [fingerprintLoading, setFingerprintLoading] = useState(false);
  const [fingerprint, setFingerprint] = useState<any>(null);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [matches, setMatches] = useState<any[]>([]);

  const handleFingerprint = async () => {
    if (!entityName.trim()) {
      message.warning('请输入实体名称');
      return;
    }
    setFingerprintLoading(true);
    try {
      const searchRes = await api.attackPrediction.predictByName(entityName).catch(() => null);
      const entityId = searchRes?.entity_id;
      if (!entityId) {
        message.error('未找到该实体，请检查名称');
        setFingerprintLoading(false);
        return;
      }
      const res = await api.attribution.fingerprint(entityId);
      setFingerprint(res);
    } catch (err: any) {
      message.error(err?.message || '指纹计算失败');
    } finally {
      setFingerprintLoading(false);
    }
  };

  const handleFindSame = async () => {
    if (!entityName.trim()) {
      message.warning('请输入实体名称');
      return;
    }
    setMatchesLoading(true);
    try {
      const res = await api.attribution.findSameByName(entityName);
      setMatches(res.matches || res.results || []);
    } catch (err: any) {
      message.error(err?.message || '同源查找失败');
    } finally {
      setMatchesLoading(false);
    }
  };

  const hours = Array.from({ length: 24 }, (_, i) => i);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="跨平台归因分析">
        <Space>
          <Input
            value={entityName}
            onChange={(e) => setEntityName(e.target.value)}
            placeholder="输入实体名称（如IP地址、域名等）..."
            style={{ width: 300 }}
          />
          <Button type="primary" icon={<ForkOutlined />} onClick={handleFingerprint} loading={fingerprintLoading}>
            计算行为指纹
          </Button>
          <Button onClick={handleFindSame} loading={matchesLoading}>
            查找同源实体
          </Button>
        </Space>
      </Card>

      {fingerprintLoading && <Spin tip="计算指纹中..." />}

      {fingerprint && !fingerprintLoading && (
        <Card title="行为指纹">
          <Descriptions column={2}>
            <Descriptions.Item label="语言特征">
              <Space wrap>
                {(fingerprint.linguistic_features || fingerprint.linguisticFeatures || []).map((f: any, idx: number) => (
                  <Tag key={idx} color="blue">{typeof f === 'string' ? f : f.name || f.feature || JSON.stringify(f)}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="活跃时段">
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 50 }}>
                {hours.map((h) => {
                  const activeHours = fingerprint.active_hours || fingerprint.activeHours || {};
                  const val = activeHours[h] || activeHours[String(h).padStart(2, '0')] || 0;
                  return (
                    <div
                      key={h}
                      style={{
                        width: 8,
                        height: Math.max(4, val * 40),
                        backgroundColor: val > 0.5 ? '#1890ff' : val > 0 ? '#69c0ff' : '#f0f0f0',
                        borderRadius: 2,
                      }}
                      title={`${h}:00 - 活跃度: ${val}`}
                    />
                  );
                })}
              </div>
            </Descriptions.Item>
            <Descriptions.Item label="操作类型" span={2}>
              <Space wrap>
                {(fingerprint.operation_types || fingerprint.operationTypes || []).map((t: any, idx: number) => (
                  <Tag key={idx} color="orange">{typeof t === 'string' ? t : t.name || t.type || JSON.stringify(t)}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {matchesLoading && <Spin tip="查找同源实体中..." />}

      {!matchesLoading && matches.length > 0 && (
        <Card title="归因桑基图">
          <AttributionSankey
            matches={matches.map((match: any) => ({
              source_platform: match.source_platform || match.sourcePlatform || 'unknown',
              target_platform: match.target_platform || match.targetPlatform || 'unknown',
              similarity: match.overall_similarity || match.similarity || 0,
              evidence: match.evidence ? (Array.isArray(match.evidence) ? match.evidence : [match.evidence]) : undefined,
            }))}
            entityName={entityName}
          />
        </Card>
      )}

      {!matchesLoading && matches.length > 0 && (
        <Row gutter={[16, 16]}>
          {matches.map((match: any, idx: number) => (
            <Col span={12} key={idx}>
              <Card size="small" title={
                <Space>
                  <Text>{match.source_platform || match.sourcePlatform || '来源'}</Text>
                  <Text>→</Text>
                  <Text>{match.target_platform || match.targetPlatform || '目标'}</Text>
                </Space>
              }>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="语言相似度">
                      <Progress percent={Math.round((match.linguistic_similarity || match.linguisticSimilarity || 0) * 100)} size="small" />
                    </Descriptions.Item>
                    <Descriptions.Item label="时间相似度">
                      <Progress percent={Math.round((match.temporal_similarity || match.temporalSimilarity || 0) * 100)} size="small" />
                    </Descriptions.Item>
                    <Descriptions.Item label="行为相似度">
                      <Progress percent={Math.round((match.behavioral_similarity || match.behavioralSimilarity || 0) * 100)} size="small" />
                    </Descriptions.Item>
                    <Descriptions.Item label="网络相似度">
                      <Progress percent={Math.round((match.network_similarity || match.networkSimilarity || 0) * 100)} size="small" />
                    </Descriptions.Item>
                  </Descriptions>
                  <div>
                    <Text type="secondary">总体相似度</Text>
                    <Progress
                      percent={Math.round((match.overall_similarity || match.similarity || 0) * 100)}
                      status="active"
                    />
                  </div>
                  {match.evidence && (
                    <div>
                      <Text type="secondary">证据:</Text>
                      <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                        {(Array.isArray(match.evidence) ? match.evidence : [match.evidence]).map((e: any, i: number) => (
                          <li key={i}><Text>{typeof e === 'string' ? e : JSON.stringify(e)}</Text></li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {!matchesLoading && matches.length === 0 && fingerprint && (
        <Empty description="未发现同源实体" />
      )}
    </Space>
  );
};

const DecayTab: React.FC = () => {
  const [batchData, setBatchData] = useState<any>(null);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchDecayData = useCallback(async () => {
    setLoading(true);
    try {
      const [batchRes, recRes] = await Promise.all([
        api.decay.batch(),
        api.decay.recommendations(),
      ]);
      setBatchData(batchRes);
      setRecommendations(recRes.recommendations || recRes.items || []);
    } catch (err: any) {
      message.error(err?.message || '获取衰减数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchDecayData();
  }, [fetchDecayData]);

  const statusColors: Record<string, string> = {
    fresh: 'green',
    active: 'blue',
    stale: 'orange',
    expired: 'red',
  };

  const statusLabels: Record<string, string> = {
    fresh: '新鲜',
    active: '有效',
    stale: '陈旧',
    expired: '过期',
  };

  const items = batchData?.items || batchData?.intelligence || [];

  const columns = [
    {
      title: '情报ID',
      dataIndex: 'id',
      key: 'id',
      ellipsis: true,
      width: 200,
    },
    {
      title: '当前置信度',
      dataIndex: 'current_confidence',
      key: 'current_confidence',
      width: 150,
      render: (val: number) => <Progress percent={Math.round((val || 0) * 100)} size="small" />,
    },
    {
      title: '半衰期',
      dataIndex: 'half_life',
      key: 'half_life',
      width: 120,
      render: (val: any) => val ? `${val}h` : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (val: string) => (
        <Tag color={statusColors[val] || 'default'}>{statusLabels[val] || val || '-'}</Tag>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="新鲜"
              value={batchData?.fresh || batchData?.fresh_count || 0}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="有效"
              value={batchData?.active || batchData?.active_count || 0}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="陈旧"
              value={batchData?.stale || batchData?.stale_count || 0}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="过期"
              value={batchData?.expired || batchData?.expired_count || 0}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="情报时效状态" extra={<Button onClick={fetchDecayData} loading={loading}>刷新</Button>}>
        {loading ? (
          <Spin />
        ) : (
          <Table
            dataSource={items}
            columns={columns}
            rowKey={(record: any) => record.id || record.intelligence_id}
            pagination={{ pageSize: 10 }}
            size="small"
          />
        )}
      </Card>

      {recommendations.length > 0 && (
        <Card title="刷新建议">
          {recommendations.map((rec: any, idx: number) => (
            <Alert
              key={idx}
              type="warning"
              message={rec.intelligence_id || rec.id || `情报 ${idx + 1}`}
              description={rec.reason || rec.message || rec.description || '建议重新采集'}
              showIcon
              style={{ marginBottom: 8 }}
            />
          ))}
        </Card>
      )}
    </Space>
  );
};

const OrganismTab: React.FC = () => {
  const [organisms, setOrganisms] = useState<any[]>([]);
  const [genes, setGenes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [spawnVisible, setSpawnVisible] = useState(false);
  const [spawnId, setSpawnId] = useState('');
  const [spawnSpecies, setSpawnSpecies] = useState('ip');
  const [spawnValue, setSpawnValue] = useState('');
  const [selectedOrg, setSelectedOrg] = useState<any>(null);
  const [vitality, setVitality] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [genealogy, setGenealogy] = useState<any>(null);
  const [lifecycleResult, setLifecycleResult] = useState<any>(null);
  const [accuracy, setAccuracy] = useState<any>(null);

  const fetchOrganisms = useCallback(async () => {
    setLoading(true);
    try {
      const [orgRes, geneRes] = await Promise.all([
        api.organism.listOrganisms(undefined, false),
        api.organism.listGenes(),
      ]);
      setOrganisms(orgRes.organisms || []);
      setGenes(geneRes.genes || []);
    } catch (err: any) {
      message.error(err?.message || '获取生命体数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchOrganisms();
  }, [fetchOrganisms]);

  const handleSpawn = async () => {
    if (!spawnId.trim() || !spawnValue.trim()) {
      message.warning('请填写情报ID和值');
      return;
    }
    try {
      await api.organism.spawn(spawnId, spawnSpecies, {
        value: spawnValue,
        threat_type: 'unknown',
        confidence: 0.7,
      });
      message.success('生命体诞生成功！');
      setSpawnVisible(false);
      setSpawnId('');
      setSpawnValue('');
      fetchOrganisms();
    } catch (err: any) {
      message.error(err?.message || '诞生失败');
    }
  };

  const handleSelectOrganism = async (org: any) => {
    setSelectedOrg(org);
    try {
      const [vRes, tRes, gRes] = await Promise.all([
        api.organism.checkVitality(org.intelligence_id),
        api.organism.getTimeline(org.intelligence_id),
        api.organism.getGenealogy(org.intelligence_id),
      ]);
      setVitality(vRes);
      setTimeline(tRes.events || []);
      setGenealogy(gRes);
    } catch (err: any) {
      message.error(err?.message || '获取详情失败');
    }
  };

  const handleEvolve = async () => {
    if (!selectedOrg) return;
    try {
      const evolved = await api.organism.evolve(
        selectedOrg.intelligence_id,
        { confidence: Math.min(1, (selectedOrg.current_state?.confidence || 0.5) + 0.1), confirmed: true },
        'manual_evidence'
      );
      message.success(`进化成功！活力值: ${evolved.vitality?.toFixed(4)}`);
      handleSelectOrganism(evolved);
      fetchOrganisms();
    } catch (err: any) {
      message.error(err?.message || '进化失败');
    }
  };

  const handleArchive = async () => {
    if (!selectedOrg) return;
    try {
      const gene = await api.organism.archiveOrganism(selectedOrg.intelligence_id, 'manual_archive');
      message.success(`已归档，基因 ${gene.gene_id?.substring(0, 12)}... 已保存`);
      setSelectedOrg(null);
      setVitality(null);
      fetchOrganisms();
    } catch (err: any) {
      message.error(err?.message || '归档失败');
    }
  };

  const handleLifecycleCheck = async () => {
    try {
      const res = await api.organism.runLifecycleCheck();
      setLifecycleResult(res);
      message.success('生命周期检查完成');
      fetchOrganisms();
    } catch (err: any) {
      message.error(err?.message || '生命周期检查失败');
    }
  };

  const handleFetchAccuracy = async () => {
    try {
      const res = await api.organism.getPredictionAccuracy();
      setAccuracy(res);
    } catch (err: any) {
      message.error(err?.message || '获取准确率失败');
    }
  };

  const speciesLabels: Record<string, string> = {
    ip: 'IP地址', phone: '手机号', bankcard: '银行卡', domain: '域名',
    ttp: '攻击手法', organization: '组织', slang: '黑话', campaign: '攻击活动',
  };

  const speciesColors: Record<string, string> = {
    ip: 'blue', phone: 'green', bankcard: 'gold', domain: 'cyan',
    ttp: 'red', organization: 'purple', slang: 'orange', campaign: 'magenta',
  };

  const eventColors: Record<string, string> = {
    born: 'green', mutated: 'blue', died: 'red', reborn: 'gold',
  };

  const actionLabels: Record<string, string> = {
    no_action_needed: '无需操作',
    monitor_normally: '正常监控',
    schedule_refresh: '计划刷新',
    urgent_refresh_needed: '急需刷新',
    archive_and_preserve_genes: '归档保存基因',
    organism_not_found: '未找到',
  };

  const orgColumns = [
    {
      title: '情报ID',
      dataIndex: 'intelligence_id',
      key: 'intelligence_id',
      ellipsis: true,
      width: 180,
      render: (val: string) => (
        <a onClick={() => handleSelectOrganism(organisms.find(o => o.intelligence_id === val)!)}>
          {val}
        </a>
      ),
    },
    {
      title: '物种',
      dataIndex: 'species',
      key: 'species',
      width: 100,
      render: (val: string) => <Tag color={speciesColors[val] || 'default'}>{speciesLabels[val] || val}</Tag>,
    },
    {
      title: '活力值',
      dataIndex: 'vitality',
      key: 'vitality',
      width: 120,
      render: (val: number) => (
        <Progress
          percent={Math.round((val || 0) * 100)}
          size="small"
          status={(val || 0) < 0.2 ? 'exception' : (val || 0) < 0.5 ? 'active' : 'success'}
        />
      ),
    },
    {
      title: '世代',
      dataIndex: 'generation',
      key: 'generation',
      width: 70,
    },
    {
      title: '存活',
      dataIndex: 'is_alive',
      key: 'is_alive',
      width: 70,
      render: (val: boolean) => <Tag color={val ? 'green' : 'red'}>{val ? '存活' : '死亡'}</Tag>,
    },
    {
      title: '变异次数',
      dataIndex: 'mutations',
      key: 'mutations',
      width: 80,
      render: (val: any[]) => val?.length || 0,
    },
    {
      title: '年龄(h)',
      dataIndex: 'current_age_hours',
      key: 'current_age_hours',
      width: 90,
      render: (val: number) => val?.toFixed(2) || '0',
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="存活生命体" value={organisms.filter(o => o.is_alive).length} valueStyle={{ color: '#52c41a' }} prefix={<HeartOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已死亡" value={organisms.filter(o => !o.is_alive).length} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="保存基因" value={genes.length} valueStyle={{ color: '#722ed1' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总生命体" value={organisms.length} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
      </Row>

      <Card
        title="情报生命体列表"
        extra={
          <Space>
            <Button type="primary" onClick={() => setSpawnVisible(true)}>诞生新生命体</Button>
            <Button onClick={handleLifecycleCheck}>生命周期检查</Button>
            <Button onClick={fetchOrganisms} loading={loading}>刷新</Button>
          </Space>
        }
      >
        <Table
          dataSource={organisms}
          columns={orgColumns}
          rowKey="intelligence_id"
          pagination={{ pageSize: 10 }}
          size="small"
          loading={loading}
          onRow={(record) => ({ onClick: () => handleSelectOrganism(record), style: { cursor: 'pointer' } })}
        />
      </Card>

      {spawnVisible && (
        <Card title="诞生新情报生命体">
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Row gutter={16}>
              <Col span={8}>
                <Text>情报ID</Text>
                <Input value={spawnId} onChange={(e) => setSpawnId(e.target.value)} placeholder="如: org-ip-1.2.3.4" />
              </Col>
              <Col span={8}>
                <Text>物种</Text>
                <select
                  value={spawnSpecies}
                  onChange={(e) => setSpawnSpecies(e.target.value)}
                  style={{ width: '100%', height: 32, padding: '4px 11px', borderRadius: 6, border: '1px solid #d9d9d9' }}
                >
                  {Object.entries(speciesLabels).map(([key, label]) => (
                    <option key={key} value={key}>{label} ({key})</option>
                  ))}
                </select>
              </Col>
              <Col span={8}>
                <Text>值</Text>
                <Input value={spawnValue} onChange={(e) => setSpawnValue(e.target.value)} placeholder="如: 192.168.1.1" />
              </Col>
            </Row>
            <Space>
              <Button type="primary" onClick={handleSpawn}>诞生</Button>
              <Button onClick={() => setSpawnVisible(false)}>取消</Button>
            </Space>
          </Space>
        </Card>
      )}

      {selectedOrg && (
        <Row gutter={16}>
          <Col span={12}>
            <Card
              title={`生命体: ${selectedOrg.intelligence_id}`}
              extra={
                <Space>
                  <Button type="primary" size="small" onClick={handleEvolve}>进化</Button>
                  {selectedOrg.is_alive && (
                    <Button danger size="small" onClick={handleArchive}>归档</Button>
                  )}
                </Space>
              }
            >
              {vitality && (
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="活力值">
                    <Progress
                      percent={Math.round((vitality.vitality || 0) * 100)}
                      status={(vitality.vitality || 0) < 0.2 ? 'exception' : 'success'}
                    />
                  </Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={vitality.is_alive ? 'green' : 'red'}>{vitality.is_alive ? '存活' : '死亡'}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="新鲜度">
                    <Progress percent={Math.round((vitality.freshness || 0) * 100)} size="small" />
                  </Descriptions.Item>
                  <Descriptions.Item label="活跃度">
                    <Progress percent={Math.round((vitality.activity || 0) * 100)} size="small" />
                  </Descriptions.Item>
                  <Descriptions.Item label="相关度">
                    <Progress percent={Math.round((vitality.relevance || 0) * 100)} size="small" />
                  </Descriptions.Item>
                  <Descriptions.Item label="建议操作">
                    <Tag color={vitality.recommended_action === 'no_action_needed' ? 'green' : vitality.recommended_action === 'archive_and_preserve_genes' ? 'red' : 'orange'}>
                      {actionLabels[vitality.recommended_action] || vitality.recommended_action}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="世代">{vitality.generation}</Descriptions.Item>
                  <Descriptions.Item label="半衰期">{vitality.half_life_hours}h</Descriptions.Item>
                </Descriptions>
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card title="进化时间线">
              <Timeline
                items={timeline.map((ev: any, idx: number) => ({
                  color: eventColors[ev.event_type] || 'blue',
                  children: (
                    <Space direction="vertical" size={0}>
                      <Space>
                        <Tag color={eventColors[ev.event_type]}>{ev.event_type}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>{ev.timestamp?.substring(11, 19)}</Text>
                      </Space>
                      <Text>{ev.description}</Text>
                      {ev.trigger && <Text type="secondary" style={{ fontSize: 12 }}>触发: {ev.trigger}</Text>}
                    </Space>
                  ),
                }))}
              />
              {timeline.length === 0 && <Empty description="暂无进化记录" />}
            </Card>
          </Col>
        </Row>
      )}

      {selectedOrg && genealogy && (
        <Card title="基因族谱">
          <Descriptions column={3} size="small">
            <Descriptions.Item label="当前世代">{genealogy.current_generation}</Descriptions.Item>
            <Descriptions.Item label="祖先数量">{genealogy.total_ancestors}</Descriptions.Item>
            <Descriptions.Item label="继承模式">
              <Space wrap>
                {(genealogy.inherited_patterns || []).map((p: string, idx: number) => (
                  <Tag key={idx} color="purple">{p}</Tag>
                ))}
                {(genealogy.inherited_patterns || []).length === 0 && <Text type="secondary">无</Text>}
              </Space>
            </Descriptions.Item>
          </Descriptions>
          {(genealogy.ancestors || []).length > 0 && (
            <Table
              dataSource={genealogy.ancestors}
              columns={[
                { title: '祖先ID', dataIndex: 'id', key: 'id', ellipsis: true },
                { title: '世代', dataIndex: 'generation', key: 'generation', width: 70 },
                { title: '物种', dataIndex: 'species', key: 'species', width: 100, render: (v: string) => <Tag color={speciesColors[v]}>{speciesLabels[v] || v}</Tag> },
                { title: '关键变异', dataIndex: 'key_pattern', key: 'key_pattern', ellipsis: true },
                { title: '死亡时间', dataIndex: 'died_at', key: 'died_at', width: 180, render: (v: string) => v || '-' },
              ]}
              rowKey="id"
              pagination={false}
              size="small"
              style={{ marginTop: 12 }}
            />
          )}
        </Card>
      )}

      {lifecycleResult && (
        <Card title="生命周期检查结果">
          <Row gutter={16}>
            <Col span={4}><Statistic title="检查数" value={lifecycleResult.checked} /></Col>
            <Col span={4}><Statistic title="变异数" value={lifecycleResult.mutated} valueStyle={{ color: '#1890ff' }} /></Col>
            <Col span={4}><Statistic title="死亡数" value={lifecycleResult.died} valueStyle={{ color: '#ff4d4f' }} /></Col>
            <Col span={4}><Statistic title="重生数" value={lifecycleResult.reborn} valueStyle={{ color: '#52c41a' }} /></Col>
            <Col span={4}><Statistic title="预测验证" value={lifecycleResult.predictions_validated} valueStyle={{ color: '#722ed1' }} /></Col>
          </Row>
        </Card>
      )}

      <Card title="预测自验证闭环" extra={<Button size="small" onClick={handleFetchAccuracy}>获取准确率</Button>}>
        {accuracy ? (
          <Descriptions column={3} size="small">
            <Descriptions.Item label="总预测数">{accuracy.total_predictions}</Descriptions.Item>
            <Descriptions.Item label="正确预测">{accuracy.correct_predictions}</Descriptions.Item>
            <Descriptions.Item label="准确率">
              <Progress percent={Math.round((accuracy.accuracy || 0) * 100)} size="small" />
            </Descriptions.Item>
            <Descriptions.Item label="Brier分数">{accuracy.brier_score?.toFixed(4) || '-'}</Descriptions.Item>
            <Descriptions.Item label="校准数据" span={2}>
              <Space wrap>
                {Object.entries(accuracy.calibration_data || {}).map(([bucket, info]: [string, any]) => (
                  <Tag key={bucket}>{bucket}: 实际{(info.actual_rate * 100).toFixed(0)}% (样本{info.sample_size})</Tag>
                ))}
              </Space>
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Empty description="暂无预测验证数据，请先注册预测并验证" />
        )}
      </Card>

      {genes.length > 0 && (
        <Card title="基因库">
          <Table
            dataSource={genes}
            columns={[
              { title: '基因ID', dataIndex: 'gene_id', key: 'gene_id', ellipsis: true, width: 200 },
              { title: '物种', dataIndex: 'species', key: 'species', width: 100, render: (v: string) => <Tag color={speciesColors[v]}>{speciesLabels[v] || v}</Tag> },
              { title: '模式', dataIndex: 'patterns', key: 'patterns', render: (v: string[]) => <Space wrap>{(v || []).map((p, i) => <Tag key={i} color="purple">{p}</Tag>)}</Space> },
              { title: '关联', dataIndex: 'associations', key: 'associations', render: (v: string[]) => <Text>{(v || []).length} 个</Text> },
              { title: '寿命(h)', dataIndex: 'total_lifetime_hours', key: 'total_lifetime_hours', width: 90, render: (v: number) => v?.toFixed(1) || '0' },
              { title: '死因', dataIndex: 'cause_of_death', key: 'cause_of_death', width: 100 },
            ]}
            rowKey="gene_id"
            pagination={{ pageSize: 5 }}
            size="small"
          />
        </Card>
      )}
    </Space>
  );
};

const Innovation: React.FC = () => {
  const tabItems = [
    {
      key: 'zero-day',
      label: (
        <span>
          <SearchOutlined />
          黑话零日检测
        </span>
      ),
      children: <ZeroDayTab />,
    },
    {
      key: 'attack-prediction',
      label: (
        <span>
          <ThunderboltOutlined />
          攻击链预测
        </span>
      ),
      children: <AttackPredictionTab />,
    },
    {
      key: 'provenance',
      label: (
        <span>
          <LinkOutlined />
          情报溯源链
        </span>
      ),
      children: <ProvenanceTab />,
    },
    {
      key: 'attribution',
      label: (
        <span>
          <ForkOutlined />
          跨平台归因
        </span>
      ),
      children: <AttributionTab />,
    },
    {
      key: 'decay',
      label: (
        <span>
          <FieldTimeOutlined />
          时效衰减
        </span>
      ),
      children: <DecayTab />,
    },
    {
      key: 'organism',
      label: (
        <span>
          <HeartOutlined />
          情报生命体
        </span>
      ),
      children: <OrganismTab />,
    },
  ];

  return (
    <div>
      <Title level={3}>创新分析</Title>
      <Tabs items={tabItems} />
    </div>
  );
};

export default Innovation;
