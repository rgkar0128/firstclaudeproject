import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    anthropic_api_key: str


def load_config() -> Config:
    missing = []
    for var in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "ANTHROPIC_API_KEY"):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        neo4j_uri=os.environ["NEO4J_URI"],
        neo4j_username=os.environ["NEO4J_USERNAME"],
        neo4j_password=os.environ["NEO4J_PASSWORD"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    )
