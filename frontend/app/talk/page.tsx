'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { TokenSource } from 'livekit-client';
import {
  useSession,
  useSessionContext,
  useAgent,
  useSessionMessages,
} from '@livekit/components-react';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { AgentAudioVisualizerAura } from '@/components/agents-ui/agent-audio-visualizer-aura';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import { AgentControlBar } from '@/components/agents-ui/agent-control-bar';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { Button } from '@/components/ui/button';

const TOKEN_SOURCE = TokenSource.endpoint('/api/token');

function TalkContent() {
  const session = useSessionContext();
  const agent = useAgent();
  const { messages } = useSessionMessages();
  const [isChatOpen, setIsChatOpen] = useState(false);

  if (agent.isPending) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4">
        <div className="h-12 w-12 animate-pulse rounded-full bg-muted" />
        <p className="text-muted-foreground">
          {agent.state === 'connecting'
            ? 'Connecting…'
            : agent.state === 'initializing' || agent.state === 'idle'
              ? 'Starting Melvin…'
              : 'Getting ready…'}
        </p>
        <Link href="/" className="text-sm text-primary hover:underline">
          Back to home
        </Link>
      </div>
    );
  }

  if (agent.isFinished) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
        {agent.failureReasons && agent.failureReasons.length > 0 ? (
          <>
            <p className="text-destructive">
              Something went wrong: {agent.failureReasons.join(', ')}
            </p>
            <p className="text-sm text-muted-foreground">
              Check the console for details. You can try again or go back home.
            </p>
          </>
        ) : (
          <p className="text-muted-foreground">You’ve left the conversation.</p>
        )}
        <div className="flex gap-3">
          <Button asChild variant="default">
            <Link href="/talk">Talk again</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/">Back to home</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[80vh] flex-col items-center gap-8 px-4 py-8">
      <div className="flex w-full max-w-lg flex-col items-center gap-6">
        <StartAudioButton label="Click to allow audio" />
        <AgentAudioVisualizerAura
          size="lg"
          state={agent.state}
          audioTrack={agent.microphoneTrack}
        />
        <div className="w-full max-w-md">
          <AgentChatTranscript agentState={agent.state} messages={messages} />
        </div>
        <AgentControlBar
          controls={{ microphone: true, leave: true, chat: true }}
          isConnected={agent.isConnected}
          isChatOpen={isChatOpen}
          onIsChatOpenChange={setIsChatOpen}
          onDisconnect={() => session.end()}
        />
      </div>
      <Link href="/" className="text-sm text-muted-foreground hover:underline">
        Back to home
      </Link>
    </div>
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
    <div className="min-h-screen bg-background">
      <header className="border-b border-border px-4 py-3">
        <h1 className="text-lg font-semibold text-foreground">
          Talk to Melvin
        </h1>
      </header>
      <AgentSessionProvider session={session}>
        <TalkContent />
      </AgentSessionProvider>
    </div>
  );
}
