"""Detect USDT (BEP20) payments to our wallet by reading Transfer logs from public BSC RPCs."""
import time

import requests

USDT_BEP20 = "0x55d398326f99059fF775485246999027B3197955"  # 18 decimals
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
RPCS = [
    "https://bsc-rpc.publicnode.com",
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-dataseed1.defibit.io",
    "https://bsc-dataseed1.ninicoin.io",
]
CHUNK = 1000          # blocks per eth_getLogs call
MAX_BACKLOG = 30000   # never scan further back than this many blocks (~6 h)
CONFIRMATIONS = 3


def _rpc(method, params):
    last = None
    for url in RPCS:
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=25)
            j = r.json()
            if "error" in j:
                last = j["error"]
                continue
            return j["result"]
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.5)
    raise RuntimeError(f"all BSC RPCs failed for {method}: {last}")


def to_topic(address):
    return "0x" + "0" * 24 + address.lower().replace("0x", "")


def scan(address, last_block):
    """Return (transfers, new_last_block). transfers: [{tx, amount, block}]"""
    latest = int(_rpc("eth_blockNumber", []), 16) - CONFIRMATIONS
    start = max(last_block + 1, latest - MAX_BACKLOG) if last_block else latest - 400
    transfers = []
    b = start
    while b <= latest:
        end = min(b + CHUNK - 1, latest)
        logs = _rpc("eth_getLogs", [{
            "fromBlock": hex(b), "toBlock": hex(end), "address": USDT_BEP20,
            "topics": [TRANSFER_TOPIC, None, to_topic(address)],
        }])
        for lg in logs:
            transfers.append({
                "tx": lg["transactionHash"] + ":" + str(int(lg.get("logIndex", "0x0"), 16)),
                "amount": int(lg["data"], 16) / 10**18,
                "block": int(lg["blockNumber"], 16),
            })
        b = end + 1
    return transfers, latest


def unique_amount(base_price, taken):
    """base 24.99 -> 24.99, 24.98, ... so each open order has a distinct amount."""
    for k in range(0, 90):
        amt = round(base_price - k * 0.01, 2)
        if all(abs(amt - x) > 0.0005 for x in taken):
            return amt
    return round(base_price - 0.9, 2)


def match(transfers, open_orders, used_tx):
    """open_orders: {oid: amount}. Returns [(oid, tx)]."""
    matched = []
    remaining = dict(open_orders)
    for tr in transfers:
        if tr["tx"] in used_tx:
            continue
        for oid, amt in list(remaining.items()):
            if abs(tr["amount"] - amt) < 0.0005:
                matched.append((oid, tr["tx"]))
                del remaining[oid]
                break
    return matched
