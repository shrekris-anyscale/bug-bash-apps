import os
import logging
from typing import Dict
from filelock import FileLock

from starlette.requests import Request

from ray import serve
from ray.serve.handle import DeploymentHandle


logger = logging.getLogger("ray.serve")


HEALTH_FILE = "/tmp/health.txt"


@serve.deployment(ray_actor_options={"num_cpus": 0})
class Writer:
    """This deployment controls the `Health` deployment's health."""

    def __init__(self, health_deployment: DeploymentHandle):
        self.health_deployment = health_deployment
        if self._read_health() not in ["healthy", "unhealthy"]:
            self._write_health("healthy")

    async def __call__(self, request: Request):
        request_json: Dict = await request.json()
        logger.info(f"Received request: {request_json}")
        self._write_health(request_json["write"])
        logger.info(f"Wrote {request_json['write']} to health file.")
        return "Hello!"
    
    def _read_health(self) -> str:
        with FileLock(f"{HEALTH_FILE}.lock"):
            if not os.path.exists(HEALTH_FILE):
                f = open(HEALTH_FILE, "w+")
                f.close()
                return
            else:
                with open(HEALTH_FILE, "r+") as f:
                    return f.read()
    
    def _write_health(self, content: str):
        with FileLock(f"{HEALTH_FILE}.lock"):
            with open(HEALTH_FILE, "w+") as f:
                f.write(content)
                f.flush()


@serve.deployment(ray_actor_options={"num_cpus": 0})
class Health:
    """This deployment's health can be controlled by sending requests.
    
    The health broadcasting only works if all the replicas are on a single
    node, and on the same node as the writer.
    """

    def check_health(self):
        if not self._read_health() == "healthy":
            raise RuntimeError("Not healthy!")
    
    def _read_health(self) -> str:
        with FileLock(f"{HEALTH_FILE}.lock"):
            if not os.path.exists(HEALTH_FILE):
                f = open(HEALTH_FILE, "w+")
                f.close()
                return
            else:
                with open(HEALTH_FILE, "r+") as f:
                    return f.read()


app = Writer.bind(Health.bind())
