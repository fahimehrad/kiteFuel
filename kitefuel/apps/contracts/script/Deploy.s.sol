// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {KiteFuelEscrow} from "../src/KiteFuelEscrow.sol";

/// @title Deploy
/// @notice Deploys KiteFuelEscrow to any EVM network.
///
/// Usage (Kite Chain testnet):
///   forge script script/Deploy.s.sol \
///     --rpc-url $KITE_RPC_URL \
///     --broadcast \
///     --private-key $DEPLOYER_PRIVATE_KEY
///
/// Required environment variables:
///   BACKEND_SIGNER_ADDRESS  – address set as authorizedSigner in the contract
///   DEPLOYER_PRIVATE_KEY    – private key of the deployer wallet
///   KITE_RPC_URL            – https://rpc-testnet.gokite.ai/
contract Deploy is Script {
    function run() external {
        // Read deployer config from environment
        address backendSigner = vm.envAddress("BACKEND_SIGNER_ADDRESS");

        vm.startBroadcast();

        // Deploy KiteFuelEscrow
        KiteFuelEscrow escrow = new KiteFuelEscrow(backendSigner);

        vm.stopBroadcast();

        // ── Log deployed address ──────────────────────────────────────────────
        console.log("KiteFuelEscrow deployed at:", address(escrow));

        // ── Post-deploy verification ──────────────────────────────────────────
        // Read authorizedSigner from the live contract and confirm it matches.
        address signerOnChain = escrow.authorizedSigner();
        console.log("authorizedSigner (on-chain):", signerOnChain);

        require(
            signerOnChain == backendSigner,
            "Deploy: authorizedSigner mismatch"
        );

        console.log("Post-deploy verification passed.");
        console.log("Set VITE_CONTRACT_ADDRESS and CONTRACT_ADDRESS to:", address(escrow));
    }
}
