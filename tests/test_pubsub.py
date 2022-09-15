import asyncio
import datetime as dt
from pathlib import Path

import pytest

from .utils import make_client_from_config

CONFIGS_DIR = Path(__file__).parent / "configs"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sender,topic",
    [
        (1, "test-topic-1"),
        (2, "test-topic-1"),
        (1, "test-topic-2"),
        (2, "test-topic-2"),
    ],
)
async def test_pubsub(sender: int, topic: str):
    p2p_client1 = await make_client_from_config(
        "test-config-1.yml", service_name="pubsub1"
    )
    p2p_client2 = await make_client_from_config(
        "test-config-2.yml", service_name="pubsub2"
    )

    sender, receiver = (
        (p2p_client1, p2p_client2) if sender == 1 else (p2p_client2, p2p_client1)
    )

    topics = ("test-topic-1", "test-topic-2")

    async with p2p_client1, p2p_client2:
        for topic in topics:
            await p2p_client1.subscribe(topic)
            await p2p_client2.subscribe(topic)

        # Note: we use a datetime in the message because gossipsub will not send duplicate
        # messages. This allows to run the test several times in a row.
        tx_message = f"Date and time: {dt.datetime.now()}"
        await sender.publish(data=tx_message.encode("utf-8"), topic=topic)
        rx_message = await asyncio.wait_for(
            receiver.receive_messages(topic).__anext__(), timeout=3.0
        )

        # Ack the message as we call the iterator with __anext__
        await rx_message.ack()

        assert rx_message.body.decode("utf-8") == tx_message
