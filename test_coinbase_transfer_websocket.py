from utils.coinbase_transfer import CoinbaseTransferClient
from utils.coinbase_websocket import generate_jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def test_generate_jwt():
    api_key = "organizations/test/apiKeys/test"
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    token = generate_jwt(api_key, pem)
    assert isinstance(token, str)


def test_transfer_payload_building(monkeypatch):
    called = {}

    def fake_post(url, json=None, headers=None, timeout=0):
        called['url'] = url
        called['json'] = json
        called['headers'] = headers
        class Resp:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {'data': 'ok'}
        return Resp()

    monkeypatch.setattr('utils.coinbase_transfer.requests.post', fake_post)
    client = CoinbaseTransferClient('token')
    resp = client.send_crypto('acct', 'addr', '0.1', 'BTC')
    assert resp == {'data': 'ok'}
    assert called['url'].endswith('/accounts/acct/transactions')
    assert called['headers']['Authorization'] == 'Bearer token'
    assert called['json']['type'] == 'send'
