"""Tests for the Tradier API client wrapper."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("TRADIER_API_TOKEN", "ci_dummy")
os.environ.setdefault("TRADIER_ACCOUNT_ID", "TESTACCT")


def test_client_sandbox_url():
    from iron_condor_0dte.tradier_client import TradierClient
    client = TradierClient(token="tok", account_id="ACC", paper=True)
    assert "sandbox.tradier.com" in client.base_url


def test_client_live_url():
    from iron_condor_0dte.tradier_client import TradierClient
    client = TradierClient(token="tok", account_id="ACC", paper=False)
    assert "api.tradier.com" in client.base_url


def test_client_stores_account_id():
    from iron_condor_0dte.tradier_client import TradierClient
    client = TradierClient(token="tok", account_id="6YB67181", paper=True)
    assert client.account_id == "6YB67181"


def test_multileg_order_correct_param_format():
    """Tradier requires option_symbol[N]/side[N]/quantity[N] — not leg[N][...] format."""
    from iron_condor_0dte.tradier_client import TradierClient
    client = TradierClient(token="tok", account_id="ACC", paper=True)

    with patch.object(client, "_post") as mock_post:
        mock_post.return_value = {"order": {"id": "999", "status": "ok"}}
        legs = [
            {"symbol": "SPY260527C00580000", "side": "buy_to_open"},
            {"symbol": "SPY260527C00578000", "side": "sell_to_open"},
            {"symbol": "SPY260527P00560000", "side": "buy_to_open"},
            {"symbol": "SPY260527P00562000", "side": "sell_to_open"},
        ]
        result = client.place_multileg_order(legs, qty=20)

    data = mock_post.call_args[0][1]
    assert data["class"] == "multileg"
    assert data["type"]  == "market"
    # Tradier working format: option_symbol[N] not leg[N][option_symbol]
    assert "option_symbol[0]" in data
    assert "option_symbol[3]" in data
    assert data["option_symbol[0]"] == "SPY260527C00580000"
    assert data["side[1]"]          == "sell_to_open"
    assert data["quantity[2]"]      == 20


def test_multileg_order_raises_on_rejection():
    from iron_condor_0dte.tradier_client import TradierClient
    client = TradierClient(token="tok", account_id="ACC", paper=True)

    with patch.object(client, "_post") as mock_post:
        mock_post.return_value = {"errors": {"error": "Invalid parameter"}}
        with pytest.raises(RuntimeError, match="Tradier order rejected"):
            client.place_multileg_order(
                [{"symbol": "SPY260527C00580000", "side": "buy_to_open"}], qty=1
            )


def test_get_positions_returns_list():
    from iron_condor_0dte.tradier_client import TradierClient
    client = TradierClient(token="tok", account_id="ACC", paper=True)

    with patch.object(client, "_get") as mock_get:
        mock_get.return_value = {"positions": "null"}
        result = client.get_positions()
    assert result == []


def test_get_positions_single_position_wrapped():
    from iron_condor_0dte.tradier_client import TradierClient
    client = TradierClient(token="tok", account_id="ACC", paper=True)

    single = {"symbol": "SPY260527C00580000", "quantity": 10}
    with patch.object(client, "_get") as mock_get:
        mock_get.return_value = {"positions": {"position": single}}
        result = client.get_positions()
    assert isinstance(result, list)
    assert len(result) == 1
