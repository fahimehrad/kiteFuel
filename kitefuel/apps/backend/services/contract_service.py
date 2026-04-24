import json
import os
from pathlib import Path
from typing import Any

import structlog
from web3 import Web3
from web3.types import TxReceipt

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Path to compiled Foundry artifact (relative to this file's repo root)
# ---------------------------------------------------------------------------

_backend_root = Path(__file__).resolve().parents[1]
_ABI_PATH = Path(os.environ.get("CONTRACT_ABI_PATH") or str(_backend_root / "artifacts" / "KiteFuelEscrow.json"))

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ContractError(Exception):
    def __init__(self, method_name: str, message: str) -> None:
        self.method_name = method_name
        self.message = message
        super().__init__(f"[{method_name}] {message}")


# ---------------------------------------------------------------------------
# ContractService
# ---------------------------------------------------------------------------

def get_rpc_url() -> str:
    """Return the RPC endpoint to use.

    Prefers KITE_RPC_URL (Kite Chain testnet) when set;
    falls back to ANVIL_RPC_URL for local Anvil development.
    """
    return os.environ.get("KITE_RPC_URL") or os.environ["ANVIL_RPC_URL"]


class ContractService:
    """Thin wrapper around the KiteFuelEscrow contract.

    Reads config from environment variables:
      KITE_RPC_URL                – JSON-RPC endpoint for Kite Chain testnet (preferred)
      ANVIL_RPC_URL               – JSON-RPC endpoint for local Anvil (fallback)
      BACKEND_SIGNER_PRIVATE_KEY  – hex-encoded private key (with or without 0x)
      CONTRACT_ADDRESS            – deployed contract address
    """

    # Fallback gas limit when estimate_gas fails
    _GAS_FALLBACK = 300_000

    def __init__(self) -> None:
        rpc_url = get_rpc_url()
        private_key = os.environ["BACKEND_SIGNER_PRIVATE_KEY"]
        contract_address = os.environ["CONTRACT_ADDRESS"]

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=self._load_abi(),
        )

        logger.info(
            "contract_service_initialised",
            signer=self.account.address,
            contract=self.contract_address,
            rpc=rpc_url,
            network="kite_testnet" if os.environ.get("KITE_RPC_URL") else "anvil_local",
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def create_task_escrow(
        self,
        task_id: bytes,
        borrower: str,
        lender: str,
        credit_amount_wei: int,
        repay_amount_wei: int,
    ) -> str:
        fn = self.contract.functions.createTaskEscrow(
            task_id,
            Web3.to_checksum_address(borrower),
            Web3.to_checksum_address(lender),
            credit_amount_wei,
            repay_amount_wei,
        )
        return self._send(fn, "createTaskEscrow")

    def fund_credit(self, task_id: bytes, value_wei: int) -> str:
        fn = self.contract.functions.fundCredit(task_id)
        return self._send(fn, "fundCredit", value_wei=value_wei)

    def mark_spend(self, task_id: bytes, amount_wei: int, provider_address: str) -> str:
        fn = self.contract.functions.markSpend(
            task_id,
            amount_wei,
            Web3.to_checksum_address(provider_address),
        )
        return self._send(fn, "markSpend")

    def register_revenue(self, task_id: bytes, value_wei: int) -> str:
        fn = self.contract.functions.registerRevenue(task_id)
        return self._send(fn, "registerRevenue", value_wei=value_wei)

    def settle(self, task_id: bytes) -> str:
        fn = self.contract.functions.settle(task_id)
        return self._send(fn, "settle")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send(self, fn: Any, method_name: str, value_wei: int = 0) -> str:
        """Build, sign, broadcast, and wait for a transaction."""
        sender = self.account.address
        nonce = self.w3.eth.get_transaction_count(sender, "pending")

        tx_params: dict[str, Any] = {
            "from": sender,
            "nonce": nonce,
            "chainId": self.w3.eth.chain_id,
            "value": value_wei,
        }

        # Gas estimation with fallback
        try:
            tx_params["gas"] = fn.estimate_gas(tx_params)
        except Exception as exc:
            logger.warning(
                "gas_estimation_failed",
                method=method_name,
                error=str(exc),
                fallback_gas=self._GAS_FALLBACK,
            )
            tx_params["gas"] = self._GAS_FALLBACK

        tx_params["gasPrice"] = self.w3.eth.gas_price

        raw_tx = fn.build_transaction(tx_params)
        signed = self.account.sign_transaction(raw_tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt: TxReceipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        tx_hash_hex = receipt["transactionHash"].hex()

        logger.info(
            "transaction_sent",
            method=method_name,
            tx_hash=tx_hash_hex,
            contract=self.contract_address,
            status=receipt["status"],
            token="KITE",
        )

        if receipt["status"] == 0:
            raise ContractError(
                method_name,
                f"transaction reverted (tx={tx_hash_hex})",
            )

        return tx_hash_hex

    @staticmethod
    def _load_abi() -> list[dict]:
        if not _ABI_PATH.exists():
            raise FileNotFoundError(
                f"Contract artifact not found at {_ABI_PATH}. "
                "Run `forge build` in apps/contracts first."
            )
        with _ABI_PATH.open() as fh:
            artifact = json.load(fh)
        return artifact["abi"]
