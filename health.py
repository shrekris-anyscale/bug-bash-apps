import logging
from typing import Dict

from starlette.requests import Request

import ray
from ray import serve
from ray.serve._private.constants import SERVE_NAMESPACE
from ray.serve.handle import DeploymentHandle


logger = logging.getLogger("ray.serve")


HEALTH_LOCK_ACTOR_NAME = "health_lock"


@ray.remote(name=HEALTH_LOCK_ACTOR_NAME, namespace=SERVE_NAMESPACE, lifetime="detached")
class HealthLock:

    def __init__(self):
        self._healthy = True
    
    def set_health(self, healthy: bool):
        self._healthy = healthy
    
    def is_healthy(self) -> bool:
        return self._healthy


@serve.deployment(ray_actor_options={"num_cpus": 0})
class Writer:
    """This deployment controls the `Health` deployment's health."""

    def __init__(self, health_deployment: DeploymentHandle):
        self.health_deployment = health_deployment
        try:
            self.health_lock_actor = HealthLock.remote()
        except ValueError:
            self.health_lock_actor = ray.get_actor(
                name=HEALTH_LOCK_ACTOR_NAME, namespace=SERVE_NAMESPACE
            )

    async def __call__(self, request: Request):
        request_json: Dict = await request.json()
        logger.info(f"Received request: {request_json}")
        if request_json.get("write") == "healthy":
            logger.info(f"Making replicas healthy.")
            await self.health_lock_actor.set_health.remote(True)
        elif request_json.get("write") == "unhealthy":
            logger.info(f"Making replicas unhealthy.")
            await self.health_lock_actor.set_health.remote(False)
        return "Hello!"


@serve.deployment(ray_actor_options={"num_cpus": 0})
class Health:
    """This deployment's health can be controlled by sending requests.
    
    The health broadcasting only works if all the replicas are on a single
    node, and on the same node as the writer.
    """

    def __init__(self):
        try:
            self.health_lock_actor = HealthLock.remote()
        except ValueError:
            self.health_lock_actor = ray.get_actor(
                name=HEALTH_LOCK_ACTOR_NAME, namespace=SERVE_NAMESPACE
            )

    async def check_health(self):
        if not (await self.health_lock_actor.is_healthy.remote()):
            raise RuntimeError("Not healthy!")


app = Writer.bind(Health.bind())
