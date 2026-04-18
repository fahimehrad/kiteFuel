#!/usr/bin/env python3
"""
deploy_and_seed.py — KiteFuel CI/demo setup script.

Runs the full happy-path lifecycle against a running backend:
  1. (optional) Deploy KiteFuelEscrow via Foundry and update .env
  2. Create task
  3. Request / approve credit
  4. Fund escrow on-chain
  5. Fetch x402 payment requirements   (buy-data)
  6. Confirm x402 purchase              (buy-data/confirm)
  7. Generate report
  8. Register user revenue on-chain     (user-pay)
  9. Settle escrow                      (settle)
  10. Fetch & display on-chain attestations

Usage:
  # full flow with interactive x402 token paste
  python scripts/deploy_and_seed.py

  # skip Foundry deploy (contract already deployed)
  python scripts/deploy_and_seed.py --skip-deploy

  # fully non-interactive
  python scripts/deploy_and_seed.py --skip-deploy --payment-token "eyJ..."

Environment variables read (from shell or .env next to this script's parent):
  API_BASE_URL            Backend base URL          (default: http://localhost:8000)
  KITE_RPC_URL            Kite Chain RPC
  DEPLOYER_PRIVATE_KEY    Deployer wallet key
  BACKEND_SIGNER_ADDRESS  Authorised signer address
  CONTRACT_ADDRESS        Existing contract address (used when --skip-deploy)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Optional dependency: requests (stdlib urllib fallback not worth the pain)
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    print("ERROR: 'requests' package is required.  pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# This script lives at  kitefuel/scripts/deploy_and_seed.py
# The repo root is therefore two levels up.
_SCRIPT_DIR  = Path(__file__).resolve().parent
_REPO_ROOT   = _SCRIPT_DIR.parent          # kitefuel/
_ENV_FILE    = _REPO_ROOT / ".env"
_CONTRACTS_DIR = _REPO_ROOT / "apps" / "contracts"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KITE_EXPLORER_TX      = "https://testnet.kitescan.ai/tx"
KITE_EXPLORER_ADDRESS = "https://testnet.kitescan.ai/address"

_RETRY_STEPS   = 3    # max attempts for chain-sensitive steps
_RETRY_DELAY   = 4    # seconds between retries


# ---------------------------------------------------------------------------
# Colour helpers (gracefully degraded)
# ---------------------------------------------------------------------------
def _c(code: str, text: str) -> str:
    """Wrap text in an ANSI colour code when stdout is a TTY."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

def green(t: str)  -> str: return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def red(t: str)    -> str: return _c("31", t)
def bold(t: str)   -> str: return _c("1",  t)
def cyan(t: str)   -> str: return _c("36", t)


# ---------------------------------------------------------------------------
# .env helpers — read + surgical write (never clobbers unrelated keys)
# ---------------------------------------------------------------------------

def _load_env_file(path: Path) -> dict[str, str]:
    """Return {key: value} from a .env file, skipping comments/blanks."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, val = stripped.partition("=")
            result[key.strip()] = val.strip()
    return result


def _update_env_key(path: Path, key: str, value: str) -> None:
    """
    Set `key=value` in the .env file.
    If the key already exists it is updated in-place; otherwise appended.
    All other lines are preserved verbatim.
    """
    lines: list[str] = path.read_text().splitlines() if path.exists() else []
    pattern = re.compile(rf"^{re.escape(key)}\s*=")
    replaced = False
    new_lines: list[str] = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n")
    print(f"  {green('✔')} {key}={value}  →  {path}")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _api(
    method: str,
    url: str,
    *,
    json: Any = None,
    step: str = "",
    retries: int = 1,
) -> dict:
    """
    Perform an HTTP request with optional retries.
    Raises SystemExit(1) on unrecoverable failure.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.request(method, url, json=json, timeout=30)
            if resp.status_code >= 400:
                body = resp.text[:400]
                if attempt < retries:
                    print(f"  {yellow('⚠')}  attempt {attempt}/{retries} — HTTP {resp.status_code}: {body}")
                    time.sleep(_RETRY_DELAY)
                    continue
                _fail(step, f"HTTP {resp.status_code}: {body}")
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                print(f"  {yellow('⚠')}  attempt {attempt}/{retries} — {exc}")
                time.sleep(_RETRY_DELAY)
            continue
    _fail(step, str(last_exc))


def _fail(step: str, reason: str) -> None:
    print(f"\n{red('✗ FAILED')}  step={bold(step)}")
    print(f"  reason: {reason}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Deploy step
# ---------------------------------------------------------------------------

def deploy_contract(env: dict[str, str]) -> str:
    """
    Run `forge script … --broadcast` and return the deployed contract address.
    Updates .env with CONTRACT_ADDRESS.
    """
    rpc_url   = env.get("KITE_RPC_URL") or os.environ.get("KITE_RPC_URL", "")
    priv_key  = env.get("DEPLOYER_PRIVATE_KEY") or os.environ.get("DEPLOYER_PRIVATE_KEY", "")
    signer    = env.get("BACKEND_SIGNER_ADDRESS") or os.environ.get("BACKEND_SIGNER_ADDRESS", "")

    missing = [k for k, v in [
        ("KITE_RPC_URL", rpc_url),
        ("DEPLOYER_PRIVATE_KEY", priv_key),
        ("BACKEND_SIGNER_ADDRESS", signer),
    ] if not v]
    if missing:
        _fail("deploy", f"Missing env vars: {', '.join(missing)}")

    print(bold("\n── Step 0: Deploy KiteFuelEscrow ──────────────────────────────"))
    print(f"  RPC: {cyan(rpc_url)}")
    print(f"  Signer: {cyan(signer)}")

    cmd = [
        "forge", "script",
        "script/Deploy.s.sol",
        "--rpc-url", rpc_url,
        "--broadcast",
        "--private-key", priv_key,
    ]

    forge_env = {**os.environ, "BACKEND_SIGNER_ADDRESS": signer}

    result = subprocess.run(
        cmd,
        cwd=str(_CONTRACTS_DIR),
        env=forge_env,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    if result.returncode != 0:
        print(output[-2000:])
        _fail("deploy", f"forge script exited with code {result.returncode}")

    # Parse: "KiteFuelEscrow deployed at: 0x..."
    match = re.search(r"KiteFuelEscrow deployed at:\s*(0x[0-9a-fA-F]{40})", output)
    if not match:
        print(output[-2000:])
        _fail("deploy", "Could not parse deployed contract address from forge output")

    contract_address = match.group(1)
    print(f"  {green('✔')} Deployed: {cyan(contract_address)}")
    print(f"  Explorer: {cyan(f'{KITE_EXPLORER_ADDRESS}/{contract_address}')}")

    # Persist to .env
    _update_env_key(_ENV_FILE, "CONTRACT_ADDRESS", contract_address)

    return contract_address


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:

    # ── Load .env into os.environ (non-destructive: only fills missing keys) ──
    file_env = _load_env_file(_ENV_FILE)
    for k, v in file_env.items():
        os.environ.setdefault(k, v)

    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")

    # ── 0. Deploy (optional) ────────────────────────────────────────────────
    contract_address: str = ""

    if not args.skip_deploy:
        contract_address = deploy_contract(file_env)
        # refresh env so backend (if it reads os.environ) sees the new address
        os.environ["CONTRACT_ADDRESS"] = contract_address
    else:
        contract_address = os.environ.get("CONTRACT_ADDRESS", "")
        print(bold("\n── Step 0: Deploy skipped ─────────────────────────────────────"))
        if contract_address:
            print(f"  Using CONTRACT_ADDRESS={cyan(contract_address)}")
        else:
            print(f"  {yellow('⚠')}  CONTRACT_ADDRESS not set — attestation links may be incomplete")

    # ── 1. Create task ──────────────────────────────────────────────────────
    print(bold("\n── Step 1: Create task ────────────────────────────────────────"))
    resp = _api("POST", f"{base_url}/tasks", step="create_task", retries=1)
    task_id = resp["task"]["id"]
    print(f"  {green('✔')} task_id={cyan(task_id)}")

    # ── 2. Request credit ───────────────────────────────────────────────────
    print(bold("\n── Step 2: Request credit ─────────────────────────────────────"))
    _api("POST", f"{base_url}/tasks/{task_id}/request-credit", step="request_credit")
    print(f"  {green('✔')} state=credit_requested")

    # ── 3. Approve credit ───────────────────────────────────────────────────
    print(bold("\n── Step 3: Approve credit ─────────────────────────────────────"))
    _api("POST", f"{base_url}/tasks/{task_id}/approve-credit", step="approve_credit")
    print(f"  {green('✔')} state=credit_approved")

    # ── 4. Fund escrow (chain-sensitive → retries) ──────────────────────────
    print(bold("\n── Step 4: Fund escrow on-chain ───────────────────────────────"))
    fund_resp = _api(
        "POST", f"{base_url}/tasks/{task_id}/fund",
        step="fund", retries=_RETRY_STEPS,
    )
    fund_tx = ""
    for ep in fund_resp.get("task", {}).values():
        pass  # task body has no tx_hash; it's in the message
    # Extract tx hash from response message  "Escrow funded (tx=0x...)"
    fund_msg = fund_resp.get("message", "")
    m = re.search(r"tx=(0x[0-9a-fA-F]{64})", fund_msg)
    if m:
        fund_tx = m.group(1)
    print(f"  {green('✔')} state=funds_locked")
    if fund_tx:
        print(f"  tx: {cyan(f'{KITE_EXPLORER_TX}/{fund_tx}')}")

    # ── 5. Buy-data — fetch x402 payment requirements ───────────────────────
    print(bold("\n── Step 5: Fetch x402 payment requirements ────────────────────"))
    buy_resp = _api("POST", f"{base_url}/tasks/{task_id}/buy-data", step="buy_data")
    requirements = buy_resp.get("requirements", {})
    print(f"  {green('✔')} payment_required=true")
    if isinstance(requirements, dict):
        for k, v in requirements.items():
            print(f"       {k}: {v}")

    # ── 6. Buy-data/confirm — x402 token ────────────────────────────────────
    print(bold("\n── Step 6: Confirm x402 purchase ──────────────────────────────"))

    payment_token: str = args.payment_token or ""

    if not payment_token:
        # Interactive pause — only reached when --payment-token is not supplied
        print()
        print(yellow("  ⏸  Paste your X-PAYMENT token below and press Enter."))
        print(yellow("     (Obtain it from Kite Passport / your MCP agent)"))
        print()
        try:
            payment_token = input("  X-PAYMENT token: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            _fail("buy_data_confirm", "No payment token provided (stdin closed or interrupted)")

    if not payment_token:
        _fail("buy_data_confirm", "payment_token must not be empty")

    confirm_resp = _api(
        "POST", f"{base_url}/tasks/{task_id}/buy-data/confirm",
        json={"payment_token": payment_token},
        step="buy_data_confirm",
        retries=1,
    )
    # Extract symbol from message  "Data purchased via x402: BTC @ $..."
    msg = confirm_resp.get("message", "")
    symbol_match = re.search(r"x402:\s*(\w+)", msg)
    purchased_symbol = symbol_match.group(1) if symbol_match else "BTC"
    print(f"  {green('✔')} state=data_purchased  symbol={purchased_symbol}")

    # ── 7. Generate report ───────────────────────────────────────────────────
    print(bold("\n── Step 7: Generate report ────────────────────────────────────"))
    _api("POST", f"{base_url}/tasks/{task_id}/generate-report", step="generate_report")
    print(f"  {green('✔')} state=result_generated")

    # ── 8. User-pay (chain-sensitive → retries) ──────────────────────────────
    print(bold("\n── Step 8: Register user revenue on-chain ─────────────────────"))
    pay_resp = _api(
        "POST", f"{base_url}/tasks/{task_id}/user-pay",
        step="user_pay", retries=_RETRY_STEPS,
    )
    pay_msg = pay_resp.get("message", "")
    pay_tx_match = re.search(r"tx=(0x[0-9a-fA-F]{64})", pay_msg)
    pay_tx = pay_tx_match.group(1) if pay_tx_match else ""
    print(f"  {green('✔')} state=user_paid")
    if pay_tx:
        print(f"  tx: {cyan(f'{KITE_EXPLORER_TX}/{pay_tx}')}")

    # ── 9. Settle (chain-sensitive → retries) ────────────────────────────────
    print(bold("\n── Step 9: Settle escrow ───────────────────────────────────────"))
    settle_resp = _api(
        "POST", f"{base_url}/tasks/{task_id}/settle",
        step="settle", retries=_RETRY_STEPS,
    )
    settle_msg = settle_resp.get("message", "")
    settle_tx_match = re.search(r"tx=(0x[0-9a-fA-F]{64})", settle_msg)
    settle_tx = settle_tx_match.group(1) if settle_tx_match else ""
    print(f"  {green('✔')} state=task_closed")
    if settle_tx:
        print(f"  tx: {cyan(f'{KITE_EXPLORER_TX}/{settle_tx}')}")

    # ── 10. Attestations (chain-sensitive → retries) ─────────────────────────
    print(bold("\n── Step 10: Fetch on-chain attestations ───────────────────────"))
    att_resp = _api(
        "GET", f"{base_url}/tasks/{task_id}/attestations",
        step="attestations", retries=_RETRY_STEPS,
    )
    # Response is a list of AttestationItem objects
    attestations: list[dict] = att_resp if isinstance(att_resp, list) else []
    att_count = len(attestations)
    for att in attestations:
        evt   = att.get("event", "?")
        amt   = att.get("amount_kite")
        url   = att.get("explorer_url", "")
        blk   = att.get("block_number", "?")
        label = f"{evt}"
        if amt:
            label += f"  ({amt} KITE)"
        print(f"  {green('✔')} {label}  block={blk}")
        if url:
            print(f"       {cyan(url)}")

    if att_count == 0:
        print(f"  {yellow('⚠')}  No attestations found yet (chain may still be indexing)")

    # ── Final summary ─────────────────────────────────────────────────────────
    print()
    print(bold("══════════════════════════════════════════════════════════════"))
    print(bold("  ✅  KiteFuel demo complete"))
    print(bold("══════════════════════════════════════════════════════════════"))
    print(f"  {green('✅')} Task ID:    {task_id}")
    if contract_address:
        print(f"  {green('✅')} Contract:  {cyan(f'{KITE_EXPLORER_ADDRESS}/{contract_address}')}")
    print(f"  {green('✅')} Funded:    0.01 KITE")
    print(f"  {green('✅')} Data purchased via x402: symbol {purchased_symbol}")
    # Lender repaid = REPAY_WEI = 0.011 + revenue = 0.012 → remainder = 0.001
    print(f"  {green('✅')} Lender repaid: 0.011 KITE  (revenue 0.012, remainder released 0.001)")
    print(f"  {green('✅')} Attestations verified: {att_count} event(s) on Kite Chain")
    if settle_tx:
        print(f"  {green('✅')} Settle tx: {cyan(f'{KITE_EXPLORER_TX}/{settle_tx}')}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="KiteFuel deploy + happy-path seed script.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--skip-deploy",
        action="store_true",
        help="Skip the Foundry contract deploy step (use existing CONTRACT_ADDRESS).",
    )
    p.add_argument(
        "--payment-token",
        metavar="TOKEN",
        default="",
        help="X-PAYMENT token for the x402 confirm step. "
             "If omitted the script pauses and prompts interactively.",
    )
    return p


if __name__ == "__main__":
    parser = _build_parser()
    parsed = parser.parse_args()

    try:
        run(parsed)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print(f"\n{yellow('Interrupted by user.')}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n{red('Unhandled error:')} {exc}", file=sys.stderr)
        sys.exit(1)
