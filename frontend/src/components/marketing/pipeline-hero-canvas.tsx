"use client";

import { useEffect, useRef } from "react";

// The one real motion moment on this page, and it's not decoration — it's
// a literal, simplified redraw of the same six-stage pipeline trace the
// product itself shows on every ticket (see PipelineTrace). Tickets
// (dots) flow left to right through the real stage names in the real
// signal colors, because the actual differentiator is that this process
// is inspectable — a generic floating-3D-object hero would be exactly
// the kind of decoration unrelated to the product this was built to avoid.
const STAGE_LABELS = ["Redacted", "Classified", "Scored", "Retrieved", "Drafted", "Routed"];
const SIGNAL_MEDIUM = "#e5a82e";
const SIGNAL_LOW = "#3fb27f";
const LANE_COLOR = "#2a313a";
const LABEL_COLOR = "#8b96a3";
const PARTICLE_COUNT = 12;
const FLASH_DURATION_MS = 450;

type Particle = { progress: number; prevProgress: number; speed: number; yAmplitude: number };

export function PipelineHeroCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    const dpr = window.devicePixelRatio || 1;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function resize() {
      const rect = canvas!.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    const particles: Particle[] = Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
      progress: i / PARTICLE_COUNT,
      prevProgress: i / PARTICLE_COUNT,
      speed: 0.00022 + Math.random() * 0.00018,
      yAmplitude: 8 + Math.random() * 10,
    }));

    // A stage "flashes" the moment a particle actually crosses it — not a
    // constant idle pulse — so the motion reads as "this stage just did
    // something to this ticket," not ambient decoration.
    const stageFlashAt = new Array(STAGE_LABELS.length).fill(-Infinity);

    let raf = 0;

    function draw(now: number, last: number) {
      const dt = last ? now - last : 16;
      ctx!.clearRect(0, 0, width, height);

      const laneY = height * 0.6;
      const marginX = width * 0.05;
      const usableWidth = width - marginX * 2;
      const stageCount = STAGE_LABELS.length;
      const slotWidth = usableWidth / (stageCount - 1);
      // Six labels genuinely don't fit side by side below roughly this
      // width (mobile) — rather than let them overlap into illegible
      // mush, drop the text and let the dots/lane/particles carry it.
      const showLabels = slotWidth > 78;

      ctx!.strokeStyle = LANE_COLOR;
      ctx!.lineWidth = 1;
      ctx!.beginPath();
      ctx!.moveTo(marginX, laneY);
      ctx!.lineTo(width - marginX, laneY);
      ctx!.stroke();

      // Update particles first and detect stage crossings, so this
      // frame's dot draw already reflects any flash that just triggered.
      for (const p of particles) {
        p.prevProgress = p.progress;
        if (!reduceMotion) {
          p.progress += p.speed * dt;
          if (p.progress > 1) p.progress -= 1;
        }
        for (let s = 0; s < stageCount; s++) {
          const stageProgress = s / (stageCount - 1);
          const crossed =
            p.progress >= stageProgress && p.prevProgress < stageProgress && p.progress - p.prevProgress < 0.5;
          if (crossed) stageFlashAt[s] = now;
        }
      }

      for (let s = 0; s < stageCount; s++) {
        const x = marginX + (usableWidth * s) / (stageCount - 1);
        const sinceFlash = now - stageFlashAt[s];
        const flash = sinceFlash < FLASH_DURATION_MS ? 1 - sinceFlash / FLASH_DURATION_MS : 0;
        const radius = 3.5 + flash * 3;

        if (flash > 0) {
          ctx!.beginPath();
          ctx!.arc(x, laneY, radius, 0, Math.PI * 2);
          ctx!.fillStyle = SIGNAL_MEDIUM;
          ctx!.globalAlpha = flash * 0.8;
          ctx!.fill();
          ctx!.globalAlpha = 1;
        }

        ctx!.beginPath();
        ctx!.arc(x, laneY, 3.5, 0, Math.PI * 2);
        ctx!.fillStyle = LANE_COLOR;
        ctx!.fill();

        if (showLabels) {
          ctx!.fillStyle = LABEL_COLOR;
          ctx!.font = "500 10px var(--font-ibm-plex-mono), ui-monospace, monospace";
          // Center-aligned labels on the first/last stage can overflow
          // past the canvas edge — anchor those two inward instead of
          // centering them exactly on the edge dot.
          ctx!.textAlign = s === 0 ? "left" : s === stageCount - 1 ? "right" : "center";
          ctx!.fillText(STAGE_LABELS[s].toUpperCase(), x, laneY + 20);
        }
      }

      for (const p of particles) {
        const x = marginX + usableWidth * p.progress;
        const y = laneY - Math.sin(p.progress * Math.PI) * p.yAmplitude;
        const nearEnd = p.progress > 0.88;

        ctx!.beginPath();
        ctx!.arc(x, y, nearEnd ? 3.5 : 2.5, 0, Math.PI * 2);
        ctx!.fillStyle = nearEnd ? SIGNAL_LOW : SIGNAL_MEDIUM;
        ctx!.globalAlpha = 0.9;
        ctx!.fill();
        ctx!.globalAlpha = 1;
      }

      raf = requestAnimationFrame((t) => draw(t, now));
    }

    raf = requestAnimationFrame((t) => draw(t, 0));

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="h-full w-full" aria-hidden="true" />;
}
