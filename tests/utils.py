from pathlib import Path

import yaml
from aleph_p2p_client import AlephP2PServiceClient, make_p2p_service_client
from aleph_p2p_client.defaults import *

PEER_ID_SERVICE_1 = "QmTXr8ecVWn8DMdDxQktL3YgNrVh7hp33CTMGhN1sqmwRp"
PEER_ID_SERVICE_2 = "QmRCDLs8BX6vD46SzsACrDc7sc9pTGTo2RhDzAB68YMzWo"

CONFIGS_DIR = Path(__file__).parent / "configs"


async def make_client_from_config(
    config_file: str, service_name: str
) -> AlephP2PServiceClient:

    config_path = CONFIGS_DIR / config_file

    with config_path.open() as f:
        config_dict = yaml.safe_load(f)

    rmq = config_dict["rabbitmq"]
    p2p = config_dict["p2p"]

    return await make_p2p_service_client(
        service_name=service_name,
        # The MQ is only reachable through localhost. The hostname in config files uses the Docker
        # network DNS, which is unavailable out of Docker.
        mq_host="localhost",
        mq_port=rmq.get("port", DEFAULT_MQ_PORT),
        mq_username=rmq.get("username", DEFAULT_MQ_USERNAME),
        mq_password=rmq.get("password", DEFAULT_MQ_PASSWORD),
        mq_pub_exchange_name=rmq.get("pub_exchange", DEFAULT_PUB_EXCHANGE_NAME),
        mq_sub_exchange_name=rmq.get("sub_exchange", DEFAULT_SUB_EXCHANGE_NAME),
        # Use localhost, same reason as the MQ host.
        http_host="localhost",
        http_port=p2p.get("control_port", DEFAULT_HTTP_PORT),
    )
