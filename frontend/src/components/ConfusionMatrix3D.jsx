export default function ConfusionMatrix3D({ matrix }) {
  if (!matrix || !matrix.values || !matrix.labels) return null;

  const { labels, values } = matrix;
  // values[0] is Actual Safe: [Safe as Safe (TN), Safe as Malicious (FP)]
  // values[1] is Actual Malicious: [Malicious as Safe (FN), Malicious as Malicious (TP)]

  const descriptions = [
    [
      { tag: "True Negative (TN)", desc: "Correctly classified Safe prompts" },
      { tag: "False Positive (FP)", desc: "Safe prompts flagged as Malicious" },
    ],
    [
      { tag: "False Negative (FN)", desc: "Malicious prompts missed as Safe" },
      { tag: "True Positive (TP)", desc: "Correctly blocked Injection prompts" },
    ],
  ];

  return (
    <div className="confusion-matrix-container">
      <div className="cm-header">
        <span className="cm-title">3D Confusion Matrix (Test Evaluation)</span>
        <span className="cm-subtitle">Predicted vs Actual Test Samples</span>
      </div>

      <div className="cm-grid-wrapper">
        <div className="cm-axis-y">
          <span>ACTUAL</span>
        </div>

        <div className="cm-main-content">
          <div className="cm-axis-x">
            <span>PREDICTED</span>
            <div className="cm-col-headers">
              {labels.map((lbl, idx) => (
                <span key={idx} className="cm-header-label">
                  {lbl}
                </span>
              ))}
            </div>
          </div>

          <div className="cm-cells-grid">
            {values.map((row, rowIdx) => (
              <div key={rowIdx} className="cm-row">
                <span className="cm-row-label">{labels[rowIdx]}</span>
                <div className="cm-row-cells">
                  {row.map((val, colIdx) => {
                    const isDiagonal = rowIdx === colIdx;
                    const isCorrect = isDiagonal && val > 0;
                    const isError = !isDiagonal && val > 0;
                    const meta = descriptions[rowIdx]?.[colIdx];

                    return (
                      <div
                        key={colIdx}
                        className={`cm-cell ${
                          isCorrect
                            ? rowIdx === 1
                              ? "cm-cell-tp"
                              : "cm-cell-tn"
                            : isError
                            ? "cm-cell-error"
                            : "cm-cell-zero"
                        }`}
                        title={`${meta?.tag}: ${meta?.desc}`}
                      >
                        <span className="cm-cell-value">{val}</span>
                        <span className="cm-cell-tag">{meta?.tag?.split(" ")[0]}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
