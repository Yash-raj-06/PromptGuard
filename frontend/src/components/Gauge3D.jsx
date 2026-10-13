export default function Gauge3D({
  value = 0, // 0 to 100
  size = 110,
  strokeWidth = 9,
  color = "#10b981",
  glowColor = "rgba(16, 185, 129, 0.35)",
  label = "",
  sublabel = "",
  gradientId = "gauge-grad-safe",
  isDanger = false,
}) {
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedValue = Math.min(100, Math.max(0, Number(value) || 0));
  const strokeDashoffset = circumference - (clampedValue / 100) * circumference;

  return (
    <div
      className="gauge-3d-wrapper"
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
      }}
    >
      <div
        style={{
          position: "relative",
          width: size,
          height: size,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Subtle ambient back glow */}
        <div
          style={{
            position: "absolute",
            width: size * 0.75,
            height: size * 0.75,
            borderRadius: "50%",
            background: glowColor,
            filter: "blur(16px)",
            opacity: 0.28,
            pointerEvents: "none",
          }}
        />

        <svg
          width={size}
          height={size}
          style={{
            transform: "rotate(-90deg)",
            filter: `drop-shadow(0 2px 6px ${glowColor})`,
          }}
        >
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={isDanger ? "#f43f5e" : "#0284c7"} />
              <stop offset="100%" stopColor={isDanger ? "#e11d48" : color} />
            </linearGradient>
          </defs>

          {/* Background track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(15, 23, 42, 0.08)"
            strokeWidth={strokeWidth}
          />

          {/* Active progress arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{
              transition: "stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)",
            }}
          />
        </svg>

        {/* Center percentage & label */}
        <div
          style={{
            position: "absolute",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-display)",
              fontSize: size > 90 ? "1.45rem" : "1.1rem",
              fontWeight: 800,
              color: "#0f172a",
              letterSpacing: "-0.03em",
            }}
          >
            {clampedValue.toFixed(1)}%
          </span>
          {sublabel && (
            <span
              style={{
                fontSize: "0.68rem",
                color: "var(--text-dim)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                fontWeight: 600,
                marginTop: "-2px",
              }}
            >
              {sublabel}
            </span>
          )}
        </div>
      </div>

      {label && (
        <span
          style={{
            marginTop: "8px",
            fontSize: "0.85rem",
            fontWeight: 700,
            color: "var(--text-main)",
            textAlign: "center",
          }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
