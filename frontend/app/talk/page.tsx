'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { TokenSource } from 'livekit-client';
import {
  useSession,
  useSessionContext,
  useAgent,
  useSessionMessages,
  type AgentState,
} from '@livekit/components-react';
import { motion, AnimatePresence } from 'motion/react';
import { ScrollTextIcon } from 'lucide-react';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import { AgentControlBar } from '@/components/agents-ui/agent-control-bar';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';

const TOKEN_SOURCE = TokenSource.endpoint('/api/token');

const DARK_BG_STYLE = {
  background: 'radial-gradient(ellipse at 55% 45%, #1a0a3a 0%, #080810 55%, #050508 100%)',
} as const;

const OVERLAY_STYLE = {
  background:
    'linear-gradient(135deg, rgba(80,40,160,0.18) 0%, transparent 50%, rgba(40,20,100,0.12) 100%)',
  backgroundSize: '200% 200%',
  animation: 'talk-bg-shift 12s ease-in-out infinite',
} as const;

// Shared fade transition for all top-level states
const STATE_TRANSITION = { duration: 0.45, ease: 'easeOut' } as const;

function PageBranding() {
  return (
    <div className="absolute top-6 left-7 z-20">
      <p
        className="text-2xl font-bold tracking-widest text-white/90"
        style={{ fontFamily: 'var(--font-space-grotesk)' }}
      >
        MIHIR
      </p>
      <p
        className="mt-0.5 text-[10px] font-medium tracking-[0.25em] text-white/40 uppercase"
        style={{ fontFamily: 'var(--font-space-grotesk)' }}
      >
        voice portfolio
      </p>
    </div>
  );
}

function AgentStateLabel({ state }: { state: AgentState }) {
  const labels: Partial<Record<AgentState, string>> = {
    connecting: 'Connecting…',
    listening: 'Listening',
    thinking: 'Thinking…',
    speaking: 'Speaking',
    idle: 'Ready',
  };
  const label = labels[state] ?? 'Ready';

  return (
    <div className="h-6 flex items-center justify-center">
      <AnimatePresence mode="wait">
        <motion.span
          key={label}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25 }}
          className="text-xs tracking-[0.15em] uppercase text-white/35"
        >
          {label}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

function PendingState({ onCancel }: { onCancel: () => void }) {
  return (
    <motion.div
      key="pending"
      className="relative flex h-screen w-screen flex-col items-center justify-center overflow-hidden"
      style={DARK_BG_STYLE}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={STATE_TRANSITION}
    >
      <div className="absolute inset-0 pointer-events-none" style={OVERLAY_STYLE} />
      <PageBranding />

      <div className="flex flex-col items-center gap-4">
        <AgentAudioVisualizerAura
          size="xl"
          state="connecting"
          themeMode="dark"
          colorShift={0.35}
        />
        <div className="h-6 flex items-center justify-center">
          <motion.span
            className="text-xs tracking-[0.2em] uppercase text-white/35"
            style={{ fontFamily: 'var(--font-space-grotesk)' }}
            animate={{ opacity: [0.35, 0.9, 0.35] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
          >
            Connecting…
          </motion.span>
        </div>
      </div>

      <button
        onClick={onCancel}
        className="absolute bottom-8 text-xs text-white/15 hover:text-white/35 transition-colors"
      >
        cancel
      </button>
    </motion.div>
  );
}

function FinishedState({ failureReasons }: { failureReasons?: string[] }) {
  const hasFailed = failureReasons && failureReasons.length > 0;
  return (
    <motion.div
      key="finished"
      className="relative flex h-screen w-screen flex-col items-center justify-center overflow-hidden gap-6"
      style={DARK_BG_STYLE}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={STATE_TRANSITION}
    >
      <div
        className="h-3 w-3 rounded-full"
        style={{
          background: hasFailed ? '#f87171' : '#4ade80',
          boxShadow: hasFailed ? '0 0 12px #f87171' : '0 0 12px #4ade80',
        }}
      />
      <p
        className="text-sm text-white/50 max-w-xs text-center"
        style={{ fontFamily: 'var(--font-space-grotesk)' }}
      >
        {hasFailed
          ? `Something went wrong: ${failureReasons!.join(', ')}`
          : "You've left the conversation."}
      </p>
      <div className="flex gap-3">
        <Link href="/talk">
          <button
            className="px-5 py-2 rounded-full text-sm font-medium transition-all"
            style={{
              background: 'rgba(120,80,220,0.2)',
              border: '1px solid rgba(120,80,220,0.4)',
              color: 'rgba(180,150,255,0.9)',
              fontFamily: 'var(--font-space-grotesk)',
            }}
          >
            Talk again
          </button>
        </Link>
        <Link href="/">
          <button
            className="px-5 py-2 rounded-full text-sm font-medium transition-all"
            style={{
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.1)',
              color: 'rgba(255,255,255,0.4)',
              fontFamily: 'var(--font-space-grotesk)',
            }}
          >
            Back to home
          </button>
        </Link>
      </div>
    </motion.div>
  );
}

function TalkContent() {
  const session = useSessionContext();
  const agent = useAgent();
  const { messages } = useSessionMessages();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);

  // Single return with AnimatePresence so every state transition crossfades
  return (
    <AnimatePresence mode="wait">
      {agent.isPending && (
        <PendingState key="pending" onCancel={() => session.end()} />
      )}

      {agent.isFinished && (
        <FinishedState key="finished" failureReasons={agent.failureReasons} />
      )}

      {!agent.isPending && !agent.isFinished && (
        <motion.div
          key="active"
          className="relative h-screen w-screen overflow-hidden"
          style={DARK_BG_STYLE}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={STATE_TRANSITION}
        >
          {/* Animated gradient overlay */}
          <div className="absolute inset-0 pointer-events-none" style={OVERLAY_STYLE} />

          {/* Top-left branding */}
          <PageBranding />

          {/* Top-right transcript toggle */}
          <button
            onClick={() => setShowTranscript((v) => !v)}
            className="absolute top-5 right-5 z-20 flex items-center justify-center w-9 h-9 rounded-full transition-all"
            style={{
              background: showTranscript ? 'rgba(120,80,220,0.2)' : 'rgba(255,255,255,0.05)',
              border: showTranscript
                ? '1px solid rgba(120,80,220,0.4)'
                : '1px solid rgba(255,255,255,0.08)',
              color: showTranscript ? 'rgba(180,150,255,0.9)' : 'rgba(255,255,255,0.3)',
            }}
          >
            <ScrollTextIcon size={15} />
          </button>

          {/* Center column — visualizer + controls */}
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
            <StartAudioButton label="Click to allow audio" />
            <AgentAudioVisualizerAura
              size="xl"
              state={agent.state}
              audioTrack={agent.microphoneTrack}
              themeMode="dark"
              colorShift={0.35}
            />
            <AgentStateLabel state={agent.state} />
            <AgentControlBar
              controls={{ microphone: true, leave: true, chat: true }}
              isConnected={agent.isConnected}
              isChatOpen={isChatOpen}
              onIsChatOpenChange={setIsChatOpen}
              onDisconnect={() => session.end()}
              className="border-white/8 bg-white/5 backdrop-blur-sm"
            />
          </div>

          {/* Transcript panel — slides in from right */}
          <AnimatePresence>
            {showTranscript && (
              <motion.div
                key="transcript"
                initial={{ x: '100%', opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: '100%', opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
                className="absolute right-0 top-0 bottom-0 z-30 w-80 flex flex-col"
                style={{
                  background: 'rgba(0,0,0,0.25)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  borderLeft: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <div
                  className="px-4 py-4 shrink-0"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <span
                    className="text-[11px] font-semibold tracking-[0.2em] uppercase text-white/40"
                    style={{ fontFamily: 'var(--font-space-grotesk)' }}
                  >
                    Transcript
                  </span>
                </div>
                <div className="flex-1 min-h-0 overflow-hidden">
                  <AgentChatTranscript
                    agentState={agent.state}
                    messages={messages}
                    className="h-full"
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default function TalkPage() {
  const session = useSession(TOKEN_SOURCE, { agentName: 'melvin' });

  useEffect(() => {
    session.start();
    return () => {
      session.end();
    };
  }, []);

  return (
    <AgentSessionProvider session={session}>
      <TalkContent />
    </AgentSessionProvider>
  );
}
