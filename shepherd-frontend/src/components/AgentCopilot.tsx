import { useEffect, useMemo, useState } from 'react';
import { AGENT_URL, askAgent, getAgentAlerts, getAgentHealth, runAgentMonitorOnce, type AgentAlert, type AgentChatResponse, type AgentHealth } from '../lib/agentClient';

const QUICK_QUESTIONS = [
  'Booth nào sẽ tắc trong 2 phút tới?',
  'Booth nào đông nhất?',
  'Tóm tắt 10 phút qua',
  'Nên gửi staff đi đâu?',
];

const RISK_LABEL: Record<string, string> = {
  high: 'HIGH',
  medium: 'MED',
  low: 'LOW',
};

export default function AgentCopilot() {
  const [health, setHealth] = useState<AgentHealth | null>(null);
  const [question, setQuestion] = useState(QUICK_QUESTIONS[0]);
  const [response, setResponse] = useState<AgentChatResponse | null>(null);
  const [alerts, setAlerts] = useState<AgentAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');

  const refreshAlerts = async () => {
    const items = await getAgentAlerts('open');
    setAlerts(items);
  };

  useEffect(() => {
    getAgentHealth()
      .then((value) => {
        setHealth(value);
        setError('');
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    refreshAlerts().catch(() => { /* agent alert polling retries below */ });
    const timer = window.setInterval(() => {
      refreshAlerts().catch(() => { /* keep UI usable if agent is temporarily down */ });
    }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const latestMetrics = useMemo(() => {
    const raw = response?.metadata?.latestMetrics ?? {};
    return Object.entries(raw).map(([zoneId, value]) => ({ zoneId, value: value as any }));
  }, [response]);

  const submit = async (nextQuestion = question) => {
    const trimmed = nextQuestion.trim();
    if (!trimmed || loading) return;
    setQuestion(trimmed);
    setLoading(true);
    setError('');
    try {
      setResponse(await askAgent(trimmed));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  };

  const runMonitor = async () => {
    if (checking) return;
    setChecking(true);
    setError('');
    try {
      await runAgentMonitorOnce();
      await refreshAlerts();
      setHealth(await getAgentHealth());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="agent-page">
      <section className="agent-hero">
        <div>
          <span className="rail__label">AGENTIC AI</span>
          <h1>Operations Copilot</h1>
          <p>
            Ask natural language questions. The local agent reads venue metrics, predicts congestion, and recommends staff action.
          </p>
        </div>
        <div className={`agent-status ${health?.ok ? 'agent-status--on' : ''}`}>
          <span className="online__dot" />
          <div>
            <strong>{health?.ok ? 'Agent online' : 'Agent offline'}</strong>
            <small>{health ? `${health.service} · ${health.zones} zones · ${health.openAgentAlerts ?? alerts.length} alerts` : AGENT_URL}</small>
          </div>
        </div>
      </section>

      <section className="agent-card agent-autonomous" aria-labelledby="agent-alerts-label">
        <div className="agent-autonomous__head">
          <div>
            <span id="agent-alerts-label" className="rail__label">AUTONOMOUS MONITOR</span>
            <p className="muted small">Runs in the agent service and creates proactive alerts from live metrics.</p>
          </div>
          <button className="btn" disabled={checking} onClick={() => void runMonitor()}>
            {checking ? 'Checking...' : 'Run check now'}
          </button>
        </div>
        {alerts.length === 0 ? (
          <p className="agent-alert-empty">No open agent alerts yet. Start live tracking or run a check.</p>
        ) : (
          <div className="agent-alerts">
            {alerts.map((alert) => (
              <article key={alert.alertId} className="agent-alert">
                <div className="agent-alert__top">
                  <strong>{alert.zoneName}</strong>
                  <span>{alert.severity.toUpperCase()}</span>
                </div>
                <p>{alert.reason}</p>
                <small>ETA {alert.etaSeconds === null ? 'n/a' : `${alert.etaSeconds}s`} · {alert.recommendation}</small>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="agent-card" aria-labelledby="agent-question-label">
        <label id="agent-question-label" className="rail__label" htmlFor="agent-question">Ask dispatcher question</label>
        <textarea
          id="agent-question"
          className="agent-input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') void submit();
          }}
          rows={3}
        />
        <div className="agent-actions">
          <button className="btn btn--primary" disabled={loading || !question.trim()} onClick={() => void submit()}>
            {loading ? 'Thinking...' : 'Ask Agent'}
          </button>
          <span className="muted small">Ctrl+Enter to send · local URL: {AGENT_URL}</span>
        </div>
        <div className="agent-quick">
          {QUICK_QUESTIONS.map((item) => (
            <button key={item} className="btn" onClick={() => void submit(item)} disabled={loading}>{item}</button>
          ))}
        </div>
      </section>

      {error && <div className="agent-error" role="alert">{error}</div>}

      {response && (
        <div className="agent-grid">
          <section className="agent-card agent-card--answer">
            <span className="rail__label">ANSWER</span>
            <p className="agent-answer">{response.answer}</p>
            <div className="agent-tools">
              {response.usedTools.map((tool) => <span key={tool}>{tool}</span>)}
            </div>
          </section>

          <section className="agent-card">
            <span className="rail__label">PREDICTIONS</span>
            <div className="agent-predictions">
              {response.predictions.length === 0 && <p className="muted small">No prediction returned for this question.</p>}
              {response.predictions.map((prediction) => (
                <article key={prediction.zoneId} className={`agent-prediction agent-prediction--${prediction.risk}`}>
                  <div className="agent-prediction__top">
                    <strong>{prediction.zoneName}</strong>
                    <span>{RISK_LABEL[prediction.risk] ?? prediction.risk}</span>
                  </div>
                  <p>{prediction.reason}</p>
                  <small>ETA {prediction.etaSeconds === null ? 'n/a' : `${prediction.etaSeconds}s`} · {prediction.recommendation}</small>
                </article>
              ))}
            </div>
          </section>

          <section className="agent-card agent-card--wide">
            <span className="rail__label">LATEST METRICS MEMORY</span>
            <div className="agent-metrics">
              {latestMetrics.map(({ zoneId, value }) => (
                <div key={zoneId} className="agent-metric">
                  <strong>{zoneId}</strong>
                  <span>{value.personCount ?? 0} people</span>
                  <span>{value.waitSec ?? 0}s wait</span>
                  <span>{value.status ?? 'normal'}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
