import {
  Activity,
  AlertTriangle,
  Cpu,
  FlaskConical,
  Gauge,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

function pct(value, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "N/A";
  const normalized = number >= 0 && number <= 1 ? number * 100 : number;
  return `${normalized.toFixed(digits)}%`;
}

function humanize(name) {
  return String(name || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function actionSlug(action) {
  return String(action || "")
    .toLowerCase()
    .replace(/\s+/g, "-");
}

export default function SecurityIntelligence({
  result,
  modelInfo,
  robustness,
  robustnessLoading,
  robustnessError,
  onRunRobustness,
}) {
  const metrics = modelInfo || {};
  const hasResult = Boolean(result && !result.error);
  const attack = hasResult ? result.attack_type : null;
  const recommendation = hasResult ? result.recommendation : null;

  return (
    <section className="intel-section">
      <div className="section-head-3d intel-head">
        <div className="head-text">
          <div className="badge-mini">
            <ShieldCheck size={13} />
            <span>AI SECURITY INTELLIGENCE</span>
          </div>
          <h2>AI Security Intelligence</h2>
          <p>
            How PromptGuard reaches its decision, and what it recommends for this
            prompt.
          </p>
        </div>
      </div>

      <div className="intel-grid">
        <div className="intel-card">
          <div className="intel-card-head">
            <Cpu size={18} />
            <h3>Detection Engine</h3>
          </div>
          <p className="intel-strong">
            Logistic Regression{" "}
            <span className="intel-muted">(binary classifier)</span>
          </p>
          <ul className="intel-list">
            <li>TF-IDF word (1-2) + character_wb (3-5) features</li>
            <li>
              {metrics.feature_count
                ? `${Number(metrics.feature_count).toLocaleString()} features`
                : "Feature count unavailable"}
            </li>
            <li>Separate Safe / Malicious probability output</li>
          </ul>
        </div>

        <div className="intel-card">
          <div className="intel-card-head">
            <Sparkles size={18} />
            <h3>Explainability</h3>
          </div>
          <p className="intel-strong">
            LIME{" "}
            <span className="intel-muted">(token-contribution analysis)</span>
          </p>
          <p>
            LIME explains the classifier's output. It is not the classifier and
            does not prove intent or causation.
          </p>
        </div>

        <div className="intel-card">
          <div className="intel-card-head">
            <Gauge size={18} />
            <h3>Model Evaluation</h3>
          </div>
          <p className="intel-muted">
            Independent external holdout
            {metrics.testing_samples ? ` (${metrics.testing_samples} samples)` : ""}
          </p>
          <div className="intel-metric-row">
            <span>
              Accuracy <strong>{pct(metrics.accuracy)}</strong>
            </span>
            <span>
              Precision <strong>{pct(metrics.precision)}</strong>
            </span>
            <span>
              Recall <strong>{pct(metrics.recall)}</strong>
            </span>
            <span>
              Macro-F1 <strong>{pct(metrics.macro_f1)}</strong>
            </span>
          </div>
          <p className="intel-note">Reported honestly; not production-grade.</p>
        </div>
      </div>

      {hasResult && (
        <>
          <div className="intel-grid intel-grid-two">
            <div className="intel-card">
              <div className="intel-card-head">
                <ShieldAlert size={18} />
                <h3>Predicted Attack Category</h3>
              </div>
              {attack ? (
                <>
                  <div className="intel-badges">
                    <span
                      className={`intel-badge evidence-${attack.evidence_strength || "none"}`}
                    >
                      {attack.label || "Unknown / Uncertain"}
                    </span>
                    <span className="intel-badge ghost">Heuristic estimate</span>
                  </div>
                  <p>{attack.reason}</p>
                  {attack.applicable === false && (
                    <p className="intel-note">
                      No attack category is asserted for a Safe prediction.
                    </p>
                  )}
                  {Array.isArray(attack.evidence) && attack.evidence.length > 0 && (
                    <ul className="intel-evidence">
                      {attack.evidence.map((item, index) => (
                        <li key={index}>
                          <span>{item.signal}</span>
                          <code>{item.matched}</code>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="intel-note">
                    Rule-based heuristic, not a trained multi-class prediction.
                  </p>
                </>
              ) : (
                <p className="intel-muted">Attack category unavailable.</p>
              )}
            </div>

            <div
              className={`intel-card action-card action-${actionSlug(
                recommendation?.action
              )}`}
            >
              <div className="intel-card-head">
                <Activity size={18} />
                <h3>Recommended Defensive Action</h3>
              </div>
              {recommendation ? (
                <>
                  <div className={`action-pill action-${actionSlug(recommendation.action)}`}>
                    {recommendation.action}
                  </div>
                  <p>{recommendation.reason}</p>
                  <p className="intel-note">{recommendation.disclaimer}</p>
                  {recommendation.thresholds && (
                    <p className="intel-note">
                      Thresholds: block &ge; {pct(recommendation.thresholds.block, 0)},
                      review &ge; {pct(recommendation.thresholds.review, 0)}.
                    </p>
                  )}
                </>
              ) : (
                <p className="intel-muted">Recommendation unavailable.</p>
              )}
            </div>
          </div>

          <div className="intel-card robustness-card">
            <div className="robust-head">
              <div>
                <div className="intel-card-head">
                  <FlaskConical size={18} />
                  <h3>Robustness Test</h3>
                </div>
                <p className="intel-muted">
                  Apply local transformations and compare each prediction with the
                  original.
                </p>
              </div>
              <button
                className="btn-glass-secondary"
                onClick={onRunRobustness}
                disabled={robustnessLoading}
              >
                <RefreshCw size={15} />
                <span>{robustnessLoading ? "Testing..." : "Run Robustness Test"}</span>
              </button>
            </div>

            {robustnessError && (
              <div className="intel-error">
                <AlertTriangle size={15} /> {robustnessError}
              </div>
            )}

            {robustness && (
              <>
                <div className="robust-summary">
                  <div className="robust-stat">
                    <span>Consistency</span>
                    <strong>
                      {robustness.summary.consistency_score == null
                        ? "N/A"
                        : `${robustness.summary.consistency_score}%`}
                    </strong>
                  </div>
                  <div className="robust-stat">
                    <span>Evaluated</span>
                    <strong>
                      {robustness.summary.evaluated}/
                      {robustness.summary.total_transformations}
                    </strong>
                  </div>
                  <div className="robust-stat">
                    <span>Changed</span>
                    <strong>{robustness.summary.changed_predictions}</strong>
                  </div>
                  <div className="robust-stat">
                    <span>Failed</span>
                    <strong>{robustness.summary.failed}</strong>
                  </div>
                </div>

                <div className="robust-list">
                  {robustness.transformations.map((item, index) => (
                    <div className="robust-row" key={`${item.name}-${index}`}>
                      <div className="robust-name">
                        <strong>{humanize(item.name)}</strong>
                        <span className={`robust-status status-${item.status}`}>
                          {item.status}
                        </span>
                      </div>
                      {item.status === "ok" ? (
                        <>
                          <div className="robust-pred">{item.prediction}</div>
                          <div className="robust-prob">
                            {item.malicious_probability}% malicious
                          </div>
                          <div
                            className={`robust-changed ${
                              item.changed ? "is-changed" : "is-same"
                            }`}
                          >
                            {item.changed ? "Changed" : "Unchanged"}
                          </div>
                        </>
                      ) : (
                        <div className="robust-skip" title={item.reason || ""}>
                          {item.reason || "Not evaluated"}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <p className="intel-note">
                  {robustness.summary.consistency_formula}.
                  {Array.isArray(robustness.notes) && robustness.notes[0]
                    ? ` ${robustness.notes[0]}`
                    : ""}
                </p>
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}
