import pytest

from .utils import PEER_ID_SERVICE_1, PEER_ID_SERVICE_2, make_client_from_config


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_file,expected_peer_id",
    [
        ("test-config-1.yml", PEER_ID_SERVICE_1),
        ("test-config-2.yml", PEER_ID_SERVICE_2),
    ],
)
async def test_identify(config_file, expected_peer_id):
    p2p_client = await make_client_from_config(config_file, service_name="identify")
    async with p2p_client:
        node_id = await p2p_client.identify()
        assert node_id.peer_id == expected_peer_id
