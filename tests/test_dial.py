import pytest
from aleph_p2p_client.exceptions import DialFailedException, DialWrongPeerException

from .utils import (
    PEER_ID_SERVICE_1,
    PEER_ID_SERVICE_2,
    make_client_from_config,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_file,peer_multiaddr,peer_id",
    [
        ("test-config-1.yml", "/dns/p2p-service-2/tcp/40250", PEER_ID_SERVICE_2),
        ("test-config-2.yml", "/dns/p2p-service-1/tcp/4025", PEER_ID_SERVICE_1),
    ],
)
async def test_dial(config_file: str, peer_multiaddr: str, peer_id: str):
    p2p_client = await make_client_from_config(config_file, service_name="dial")

    async with p2p_client:
        await p2p_client.dial(peer_id=peer_id, multiaddr=peer_multiaddr)


@pytest.mark.asyncio
async def test_dial_self():
    p2p_client = await make_client_from_config(
        "test-config-1.yml", service_name="dial-self"
    )
    async with p2p_client:
        with pytest.raises(DialWrongPeerException):
            await p2p_client.dial(
                peer_id=PEER_ID_SERVICE_1, multiaddr="/ip4/127.0.0.1/tcp/4025"
            )


@pytest.mark.asyncio
async def test_dial_with_wrong_peer_id():
    peer_id = "QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
    multiaddr = f"/dns/p2p-service-1/tcp/4025"

    p2p_client = await make_client_from_config(
        "test-config-2.yml", service_name="dial-wrong-peer"
    )
    async with p2p_client:
        with pytest.raises(DialWrongPeerException):
            await p2p_client.dial(peer_id=peer_id, multiaddr=multiaddr)


@pytest.mark.asyncio
async def test_dial_nonexistent_peer():
    peer_id = "QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
    multiaddr = f"/ip4/127.0.0.1/tcp/5000"

    p2p_client = await make_client_from_config(
        "test-config-2.yml", service_name="dial-nonexistent-peer"
    )
    async with p2p_client:
        with pytest.raises(DialFailedException):
            await p2p_client.dial(peer_id=peer_id, multiaddr=multiaddr)
