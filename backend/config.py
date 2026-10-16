"""Central configuration for AegisGraph backend. All values overridable via env."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    falkor_host: str = os.getenv("FALKOR_HOST", "localhost")
    falkor_port: int = int(os.getenv("FALKOR_PORT", "6379"))
    falkor_username: str = os.getenv("FALKOR_USERNAME", "")
    falkor_password: str = os.getenv("FALKOR_PASSWORD", "")
    prod_graph: str = os.getenv("PROD_GRAPH", "prod_graph")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    # When True the backend seeds prod_graph on startup if it is empty.
    auto_seed: bool = os.getenv("AUTO_SEED", "true").lower() == "true"


settings = Settings()
