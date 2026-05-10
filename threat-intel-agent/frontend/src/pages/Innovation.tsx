import React, { useState } from 'react';
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
} from '@ant-design/icons';
import { api } from '../services/api';

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
  const [entityId, setEntityId] = useState('');
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<any>(null);

  const handlePredict = async () => {
    if (!entityId.trim()) {
      message.warning('请输入实体ID');
      return;
    }
    setLoading(true);
    try {
      const res = await api.attackPrediction.predict(entityId);
      setPrediction(res);
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
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            placeholder="输入实体ID..."
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

      {!loading && prediction && steps.length === 0 && (
        <Empty description="未发现攻击路径" />
      )}
    </Space>
  );
};

const ProvenanceTab: React.FC = () => {
  const [intelligenceId, setIntelligenceId] = useState('');
  const [loading, setLoading] = useState(false);
  const [verifyResult, setVerifyResult] = useState<any>(null);
  const [chainData, setChainData] = useState<any>(null);
  const [hallucinationLoading, setHallucinationLoading] = useState(false);
  const [hallucinationResult, setHallucinationResult] = useState<any>(null);

  const handleVerify = async () => {
    if (!intelligenceId.trim()) {
      message.warning('请输入情报ID');
      return;
    }
    setLoading(true);
    try {
      const [verifyRes, chainRes] = await Promise.all([
        api.provenance.verify(intelligenceId),
        api.provenance.chain(intelligenceId),
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
    if (!intelligenceId.trim()) {
      message.warning('请输入情报ID');
      return;
    }
    setHallucinationLoading(true);
    try {
      const res = await api.provenance.hallucinationCheck(intelligenceId);
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
        <Space>
          <Input
            value={intelligenceId}
            onChange={(e) => setIntelligenceId(e.target.value)}
            placeholder="输入情报ID..."
            style={{ width: 300 }}
          />
          <Button type="primary" icon={<LinkOutlined />} onClick={handleVerify} loading={loading}>
            验证溯源链
          </Button>
          <Button onClick={handleHallucinationCheck} loading={hallucinationLoading}>
            幻觉检测
          </Button>
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
  const [entityId, setEntityId] = useState('');
  const [fingerprintLoading, setFingerprintLoading] = useState(false);
  const [fingerprint, setFingerprint] = useState<any>(null);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [matches, setMatches] = useState<any[]>([]);

  const handleFingerprint = async () => {
    if (!entityId.trim()) {
      message.warning('请输入实体ID');
      return;
    }
    setFingerprintLoading(true);
    try {
      const res = await api.attribution.fingerprint(entityId);
      setFingerprint(res);
    } catch (err: any) {
      message.error(err?.message || '指纹计算失败');
    } finally {
      setFingerprintLoading(false);
    }
  };

  const handleFindSame = async () => {
    if (!entityId.trim()) {
      message.warning('请输入实体ID');
      return;
    }
    setMatchesLoading(true);
    try {
      const res = await api.attribution.findSame(entityId);
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
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            placeholder="输入实体ID..."
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

  const fetchDecayData = async () => {
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
  };

  React.useEffect(() => {
    fetchDecayData();
  }, []);

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
  ];

  return (
    <div>
      <Title level={3}>创新分析</Title>
      <Tabs items={tabItems} />
    </div>
  );
};

export default Innovation;
