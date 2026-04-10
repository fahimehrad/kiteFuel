# @kitefuel/shared-types

Shared TypeScript type definitions used across KiteCredit front-end and any future TypeScript consumers.

## Contents

| Type | Description |
|------|-------------|
| `HealthResponse` | Shape of `GET /health` response |
| `Loan` | Loan entity mirroring the backend ORM model |
| `LoanStatus` | Union type for loan state machine |

## Usage

```ts
import type { Loan, LoanStatus } from '@kitefuel/shared-types'
```

> This package is `private` and is consumed directly via path alias or monorepo tooling — no publishing required for the MVP.
