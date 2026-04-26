import os
import sys

from dotenv import load_dotenv
from livekit.agents import AgentServer, cli

from src.hooks.session import portfolio_agent_handler
from src.hooks.session_capture import on_session_end

if os.path.exists(".env.local"):
    load_dotenv(".env.local")


def setup_server():
    server = AgentServer()
    server.rtc_session(agent_name="melvin", on_session_end=on_session_end)(
        portfolio_agent_handler
    )
    return server


if __name__ == "__main__":
    # Match LiveKit Voice AI quickstart: `download-files` pulls Silero, turn-detector,
    # and other plugin assets. See https://docs.livekit.io/agents/start/voice-ai/
    if len(sys.argv) == 1:
        sys.argv.append("start")

    cli.run_app(setup_server())