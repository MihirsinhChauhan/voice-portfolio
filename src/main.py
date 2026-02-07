import os
import argparse
from dotenv import load_dotenv
from livekit.agents import AgentServer, cli
from src.hooks.session import portfolio_agent_handler
from src.utils.logging import logger

if os.path.exists(".env.local"):
    load_dotenv(".env.local")

def setup_server():
    server = AgentServer()
    server.rtc_session()(portfolio_agent_handler)
    return server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Portfolio Agent")
    parser.add_argument(
        "mode", nargs="?", default="start",
        choices=["console", "dev", "start"],
        help="console: run the server in console mode | dev: hot reload + colorful logs | start: production mode with clean logs"
    )

    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    logger.setLevel(args.log_level)


    cli.run_app(setup_server())