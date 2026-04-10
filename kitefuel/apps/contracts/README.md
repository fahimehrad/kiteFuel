# KiteFuel — Smart Contracts

Solidity contracts managed with **Foundry**.

## Stack
- [Foundry](https://book.getfoundry.sh/) — build, test, deploy toolchain
- Solidity `^0.8.x`
- `forge-std` — testing and scripting utilities

## Getting Started

```bash
# Build all contracts
forge build

# Run tests
forge test

# Start a local EVM node (separate terminal)
anvil
```

## Project Structure

```
src/
└── Counter.sol        # Foundry placeholder — will become KiteFuel.sol
test/
└── Counter.t.sol      # Placeholder test suite
script/
└── Counter.s.sol      # Placeholder deploy script
lib/
└── forge-std/         # Foundry standard library (git submodule)
foundry.toml           # Foundry configuration
```

## Planned Contract: `KiteFuel.sol`

The escrow-first contract will implement the following MVP flow:

1. Lender deposits capital → funds locked in escrow
2. Agent draws credit against the escrow to buy paid data
3. User pays into the contract after receiving the report
4. Contract repays lender first (principal + fee)
5. Remainder is released to the agent

> ⚠️ No business logic is implemented in this scaffold. `Counter.sol` is the Foundry default placeholder.

## Deploying (future)

```bash
# Deploy to local Anvil
forge script script/Deploy.s.sol --rpc-url $ANVIL_RPC_URL --broadcast

# Deploy to testnet
forge script script/Deploy.s.sol --rpc-url $ANVIL_RPC_URL --private-key $BACKEND_SIGNER_PRIVATE_KEY --broadcast
```
