'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'motion/react';
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';

const DARK_BG_STYLE = {
  background:
    'radial-gradient(ellipse at 55% 45%, #1a0a3a 0%, #080810 55%, #050508 100%)',
} as const;

export default function Home() {
  const router = useRouter();
  const [isLeaving, setIsLeaving] = useState(false);

  const handleTalkClick = useCallback(() => {
    if (isLeaving) return;
    setIsLeaving(true);
  }, [isLeaving]);

  return (
    <div className="relative h-screen w-screen overflow-hidden" style={DARK_BG_STYLE}>
      {/* Soft top violet glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at 48% 0%, rgba(100,60,200,0.18) 0%, transparent 55%)',
        }}
      />

      {/* ── Desktop: side-by-side │ Mobile: stacked ── */}
      <div className="absolute inset-0 flex flex-col items-center justify-center md:flex-row">

        {/* LEFT — Name + Designation */}
        <motion.div
          className="w-full px-10 pb-10 pt-16 md:w-[44%] md:px-16 md:pb-0 md:pt-0"
          initial={{ opacity: 0, x: -28 }}
          animate={isLeaving ? { opacity: 0, x: -44 } : { opacity: 1, x: 0 }}
          transition={{
            duration: isLeaving ? 0.5 : 0.75,
            ease: [0.32, 0.72, 0, 1],
          }}
        >
          <h1
            className="text-[clamp(2.6rem,5vw,4rem)] font-bold leading-[1.05] tracking-tight text-white/90"
            style={{ fontFamily: 'var(--font-space-grotesk)' }}
          >
            Mihir<br />Chauhan
          </h1>
          <p
            className="mt-4 text-[10px] font-semibold tracking-[0.3em] text-white/30 uppercase"
            style={{ fontFamily: 'var(--font-space-grotesk)' }}
          >
            Backend &amp; Systems Engineer
          </p>
        </motion.div>

        {/* RIGHT — Visualizer + CTA */}
        {/* onAnimationComplete fires when exit finishes → navigate exactly then */}
        <motion.div
          className="flex flex-1 flex-col items-center justify-center gap-8"
          initial={{ opacity: 0, scale: 0.91 }}
          animate={isLeaving ? { opacity: 0, scale: 1.1 } : { opacity: 1, scale: 1 }}
          transition={{
            duration: isLeaving ? 0.65 : 0.9,
            ease: 'easeOut',
            delay: isLeaving ? 0 : 0.12,
          }}
          onAnimationComplete={() => {
            if (isLeaving) router.push('/talk');
          }}
        >
          <AgentAudioVisualizerAura
            size="xl"
            state="listening"
            themeMode="dark"
            colorShift={0.35}
          />

          <motion.button
            onClick={handleTalkClick}
            className="rounded-full px-9 py-3 text-sm font-semibold"
            style={{
              background: 'rgba(120,80,220,0.2)',
              border: '1px solid rgba(120,80,220,0.5)',
              color: 'rgba(200,170,255,0.95)',
              fontFamily: 'var(--font-space-grotesk)',
              letterSpacing: '0.06em',
            }}
            whileHover={{ background: 'rgba(120,80,220,0.32)', scale: 1.03 }}
            whileTap={{ scale: 0.96 }}
            transition={{ duration: 0.18 }}
          >
            Talk to Melvin
          </motion.button>
        </motion.div>

      </div>
    </div>
  );
}
