import { useState, useRef } from "react";

export default function TiltCard({
  children,
  className = "",
  style = {},
  maxTilt = 6,
  glowColor = "rgba(59, 130, 246, 0.1)",
  onClick,
}) {
  const cardRef = useRef(null);
  const [transform, setTransform] = useState("");
  const [glowPos, setGlowPos] = useState({ x: 50, y: 50, opacity: 0 });

  const handleMouseMove = (e) => {
    const card = cardRef.current;
    if (!card) return;

    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -maxTilt;
    const rotateY = ((x - centerX) / centerX) * maxTilt;

    setTransform(
      `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateZ(6px) scale3d(1.008, 1.008, 1.008)`
    );

    setGlowPos({
      x: ((x / rect.width) * 100).toFixed(1),
      y: ((y / rect.height) * 100).toFixed(1),
      opacity: 1,
    });
  };

  const handleMouseLeave = () => {
    setTransform("perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px) scale3d(1, 1, 1)");
    setGlowPos((prev) => ({ ...prev, opacity: 0 }));
  };

  return (
    <div
      ref={cardRef}
      className={`tilt-card ${className}`}
      style={{
        transform,
        transition: transform ? "transform 0.12s ease-out, box-shadow 0.25s ease" : "transform 0.5s ease-out, box-shadow 0.25s ease",
        transformStyle: "flat",
        position: "relative",
        ...style,
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
    >
      {/* Dynamic 3D Specular Light Overlay */}
      <div
        className="tilt-specular-light"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          borderRadius: "inherit",
          pointerEvents: "none",
          zIndex: 2,
          background: `radial-gradient(circle 260px at ${glowPos.x}% ${glowPos.y}%, ${glowColor}, transparent 70%)`,
          opacity: glowPos.opacity,
          transition: "opacity 0.3s ease",
        }}
      />
      {/* Content wrapper (kept flat so clicks always match the painted position) */}
      <div style={{ position: "relative", zIndex: 3 }}>
        {children}
      </div>
    </div>
  );
}
