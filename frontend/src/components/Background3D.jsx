import { useEffect, useRef } from "react";

export default function Background3D() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    // Mouse coordinates with easing
    let mouse = { x: width / 2, y: height / 2, targetX: width / 2, targetY: height / 2 };
    const handleMouseMove = (e) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
    };
    window.addEventListener("mousemove", handleMouseMove);

    // Subtle 3D floating crystal particles
    const particleCount = 38;
    const particles = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      z: Math.random() * 800 + 100, // 3D depth
      size: Math.random() * 2.2 + 1.2,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      color: Math.random() > 0.4 ? "rgba(37, 99, 235," : "rgba(124, 58, 237,",
      alpha: Math.random() * 0.35 + 0.15,
    }));

    let tick = 0;

    const render = () => {
      tick += 0.01;
      mouse.x += (mouse.targetX - mouse.x) * 0.04;
      mouse.y += (mouse.targetY - mouse.y) * 0.04;

      ctx.clearRect(0, 0, width, height);

      // 1. Ethereal Light Theme Ambient Radial Halos
      const grad1 = ctx.createRadialGradient(
        mouse.x * 0.25 + width * 0.25,
        mouse.y * 0.25 + height * 0.2,
        40,
        mouse.x * 0.25 + width * 0.25,
        mouse.y * 0.25 + height * 0.2,
        width * 0.55
      );
      grad1.addColorStop(0, "rgba(59, 130, 246, 0.08)");
      grad1.addColorStop(0.5, "rgba(147, 51, 234, 0.04)");
      grad1.addColorStop(1, "transparent");
      ctx.fillStyle = grad1;
      ctx.fillRect(0, 0, width, height);

      const grad2 = ctx.createRadialGradient(
        width - mouse.x * 0.2,
        height - mouse.y * 0.2,
        30,
        width - mouse.x * 0.2,
        height - mouse.y * 0.2,
        width * 0.5
      );
      grad2.addColorStop(0, "rgba(16, 185, 129, 0.06)");
      grad2.addColorStop(1, "transparent");
      ctx.fillStyle = grad2;
      ctx.fillRect(0, 0, width, height);

      // 2. Light 3D Perspective Grid
      const gridHorizon = height * 0.84;
      const tiltX = (mouse.x - width / 2) * 0.035;

      ctx.save();
      // Horizon line
      const horizonGrad = ctx.createLinearGradient(0, gridHorizon, width, gridHorizon);
      horizonGrad.addColorStop(0, "transparent");
      horizonGrad.addColorStop(0.5, "rgba(99, 102, 241, 0.15)");
      horizonGrad.addColorStop(1, "transparent");
      ctx.strokeStyle = horizonGrad;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(0, gridHorizon);
      ctx.lineTo(width, gridHorizon);
      ctx.stroke();

      // Perspective grid lines
      const lineCount = 14;
      ctx.strokeStyle = "rgba(99, 102, 241, 0.05)";
      ctx.lineWidth = 1;
      for (let i = -lineCount; i <= lineCount; i++) {
        const startX = width / 2 + i * 45 + tiltX;
        ctx.beginPath();
        ctx.moveTo(startX, gridHorizon);
        const endX = width / 2 + i * 180 + tiltX * 3;
        ctx.lineTo(endX, height);
        ctx.stroke();
      }

      // Horizontal depth lines
      const horizontalLines = 6;
      for (let j = 1; j <= horizontalLines; j++) {
        const progress = Math.pow(j / horizontalLines, 2.2);
        const y = gridHorizon + progress * (height - gridHorizon);
        const alpha = progress * 0.07;
        ctx.strokeStyle = `rgba(99, 102, 241, ${alpha})`;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      ctx.restore();

      // 3. Floating 3D Depth Particles
      particles.forEach((p, idx) => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        const parallaxX = (mouse.x - width / 2) * (140 / p.z);
        const parallaxY = (mouse.y - height / 2) * (140 / p.z);
        const drawX = p.x + parallaxX;
        const drawY = p.y + parallaxY;

        const pulse = Math.sin(tick * 2 + idx) * 0.25 + 0.75;
        const radius = p.size * (400 / p.z);

        ctx.beginPath();
        ctx.arc(drawX, drawY, Math.max(0.9, radius), 0, Math.PI * 2);
        ctx.fillStyle = `${p.color} ${p.alpha * pulse})`;
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: 0,
      }}
    />
  );
}
