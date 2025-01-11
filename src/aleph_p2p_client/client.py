from dataclasses import dataclass
from typing import AsyncIterator, Dict

import aio_pika
import aiohttp

from .defaults import *
from .exceptions import (
    DialFailedException,
    DialWrongPeerException,
    InternalServiceException,
)


@dataclass
class NodeId:
    peer_id: str


class AlephP2PMessageQueueClient:
    def __init__(
        self,
        service_name: str,
        peer_id: str,
        connection: aio_pika.abc.AbstractConnection,
        channel: aio_pika.abc.AbstractChannel,
        pub_exchange: aio_pika.abc.AbstractExchange,
        sub_exchange: aio_pika.abc.AbstractExchange,
    ):
        self.service_name = service_name
        self.peer_id = peer_id
        self.connection = connection
        self.channel = channel
        self.pub_exchange = pub_exchange
        self.sub_exchange = sub_exchange

        self.subscriptions: Dict[str, aio_pika.abc.AbstractQueue] = {}

    async def close(self):
        await self.connection.close()

    async def publish(self, data: bytes, topic: str, loopback: bool = False):
        message = aio_pika.Message(body=data)
        await self.pub_exchange.publish(message, routing_key=topic)

        if loopback:
            await self.sub_exchange.publish(
                message, routing_key=f"p2p.{topic}.{self.peer_id}"
            )

    async def subscribe(self, topic: str):
        if topic in self.subscriptions:
            return

        queue_name = f"p2p-sub-queue-{self.service_name}-{topic}"
        queue = await self.channel.declare_queue(name=queue_name)

        await queue.bind(self.sub_exchange, routing_key=f"*.{topic}.*")

        self.subscriptions[topic] = queue

    async def receive_messages(
        self, topic: str
    ) -> AsyncIterator[aio_pika.abc.AbstractIncomingMessage]:
        if topic not in self.subscriptions:
            await self.subscribe(topic)

        sub_queue = self.subscriptions[topic]

        async with sub_queue.iterator() as queue_iter:
            async for message in queue_iter:
                yield message
                # This condition prevents double ACK issues given by aiopika and rabbitmq if a lot of messages
                # are received
                if not message.processed:
                    await message.ack()


class AlephP2PHttpClient:
    def __init__(self, http_session: aiohttp.ClientSession):
        self.http_session = http_session

    async def identify(self) -> NodeId:
        response = await self.http_session.get("/api/p2p/identify")
        response.raise_for_status()

        body = await response.json()
        return NodeId(peer_id=body["peer_id"])

    async def dial(self, peer_id: str, multiaddr: str):
        response = await self.http_session.post(
            "/api/p2p/dial", json={"peer_id": peer_id, "multiaddr": multiaddr}
        )

        if response.status == 200:
            return
        if response.status == 403:
            raise DialWrongPeerException(
                f"Wrong peer: peer ID '{peer_id}' is not associated to multiaddr '{multiaddr}'"
            )
        elif response.status == 404:
            raise DialFailedException("Could not reach peer")

        raise InternalServiceException(await response.text())

    async def close(self):
        await self.http_session.close()


class AlephP2PServiceClient:
    """
    Client class for the Aleph P2P service.

    The Aleph P2P service provides services in the form of several RabbitMQ
    exchanges/queues and a HTTP server. By combining both, users can
    send/receive messages over P2P pubsub interfaces and perform several
    P2P-specific operations like dialing external peers or retrieving
    parameters of the local node.

    This class is mostly a thin wrapper on top of the HTTP and message queue client
    classes. This allows users to only use a single object to access the service,
    regardless of whether the methods use HTTP calls or message queues.

    Note that instances of this class should be built using the factory function
    `make_p2p_service_client`.
    """

    def __init__(
        self,
        mq_client: AlephP2PMessageQueueClient,
        http_client: AlephP2PHttpClient,
    ):
        self.mq_client = mq_client
        self.http_client = http_client

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.mq_client.close()

    async def identify(self) -> NodeId:
        return await self.http_client.identify()

    async def dial(self, peer_id: str, multiaddr: str):
        return await self.http_client.dial(peer_id=peer_id, multiaddr=multiaddr)

    async def publish(self, data: bytes, topic: str, loopback: bool = False):
        await self.mq_client.publish(data=data, topic=topic, loopback=loopback)

    async def subscribe(self, topic: str):
        await self.mq_client.subscribe(topic)

    async def receive_messages(
        self, topic: str
    ) -> AsyncIterator[aio_pika.abc.AbstractIncomingMessage]:

        async for message in self.mq_client.receive_messages(topic):
            yield message


async def declare_mq_objects(
    service_name: str,
    peer_id: str,
    mq_host: str,
    mq_port: int,
    mq_username: str,
    mq_password: str,
    mq_pub_exchange_name: str,
    mq_sub_exchange_name: str,
):
    connection = await aio_pika.connect_robust(
        host=mq_host, port=mq_port, login=mq_username, password=mq_password
    )
    channel = await connection.channel()
    pub_exchange = await channel.declare_exchange(
        name=mq_pub_exchange_name, type=aio_pika.ExchangeType.TOPIC, auto_delete=False
    )

    sub_exchange = await channel.declare_exchange(
        name=mq_sub_exchange_name, type=aio_pika.ExchangeType.TOPIC, auto_delete=False
    )

    return AlephP2PMessageQueueClient(
        service_name=service_name,
        peer_id=peer_id,
        connection=connection,
        channel=channel,
        pub_exchange=pub_exchange,
        sub_exchange=sub_exchange,
    )


async def make_p2p_service_client(
    service_name: str,
    mq_host: str = DEFAULT_MQ_HOST,
    mq_port: int = DEFAULT_MQ_PORT,
    mq_username: str = DEFAULT_MQ_USERNAME,
    mq_password: str = DEFAULT_MQ_PASSWORD,
    mq_pub_exchange_name: str = DEFAULT_PUB_EXCHANGE_NAME,
    mq_sub_exchange_name: str = DEFAULT_SUB_EXCHANGE_NAME,
    http_host: str = DEFAULT_HTTP_HOST,
    http_port: int = DEFAULT_HTTP_PORT,
) -> AlephP2PServiceClient:

    http_session = aiohttp.ClientSession(base_url=f"http://{http_host}:{http_port}/")
    http_client = AlephP2PHttpClient(http_session=http_session)

    peer_id = (await http_client.identify()).peer_id

    mq_client = await declare_mq_objects(
        service_name=service_name,
        peer_id=peer_id,
        mq_host=mq_host,
        mq_port=mq_port,
        mq_username=mq_username,
        mq_password=mq_password,
        mq_pub_exchange_name=mq_pub_exchange_name,
        mq_sub_exchange_name=mq_sub_exchange_name,
    )

    return AlephP2PServiceClient(mq_client=mq_client, http_client=http_client)
