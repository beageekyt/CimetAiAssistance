import type { Metrics } from "../types";

interface Props {
  metrics: Metrics | null;
}

export function MetricsBar({ metrics }: Props) {
  if (!metrics) return <div className="metrics-bar">Loading metrics…</div>;

  const minutesSaved = Math.round(metrics.time_saved_seconds / 60);

  return (
    <div className="metrics-bar">
      <div className="metric">
        <span className="metric-value">{metrics.total_calls}</span>
        <span className="metric-label">Calls</span>
      </div>
      <div className="metric">
        <span className="metric-value">{metrics.completed}</span>
        <span className="metric-label">Completed</span>
      </div>
      <div className="metric">
        <span className="metric-value">{metrics.escalated}</span>
        <span className="metric-label">Escalated</span>
      </div>
      <div className="metric">
        <span className="metric-value">{metrics.declined}</span>
        <span className="metric-label">Declined</span>
      </div>
      <div className="metric">
        <span className="metric-value">{metrics.blocked}</span>
        <span className="metric-label">DNC blocked</span>
      </div>
      <div className="metric">
        <span className="metric-value">{minutesSaved}m</span>
        <span className="metric-label">Time saved (est.)</span>
      </div>
      <div className="metric-note" title={metrics.baseline_assumption.note}>
        assumed baseline: {metrics.baseline_assumption.seconds_per_field}s/field + {metrics.baseline_assumption.overhead_seconds}s overhead
      </div>
    </div>
  );
}
