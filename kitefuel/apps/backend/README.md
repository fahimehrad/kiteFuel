# KiteFuel — Backend

Python REST API built with **FastAPI**, **SQLAlchemy**, **Alembic**, and **web3.py**.

## Stack
- [FastAPI](https://fastapi.tiangolo.com/) — async web framework
- [SQLAlchemy 2](https://www.sqlalchemy.org/) — ORM
- [Alembic](https://alembic.sqlalchemy.org/) — database migrations
- [web3.py](https://web3py.readthedocs.io/) — Ethereum / contract interaction
- [Uvicorn](https://www.uvicorn.org/) — ASGI server

## Getting Started

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy and edit the top-level env file
cp ../../.env.example ../../.env

uvicorn main:app --reload
# → http://localhost:8000
# → Swagger UI: http://localhost:8000/docs
```

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"kitefuel-backend"}
```

> Only the `/health` endpoint is implemented in this scaffold. Business routes will be added in subsequent tasks.

## Database Migrations

```bash
# After editing models.py, generate a new migration
alembic revision --autogenerate -m "describe change"

# Apply all pending migrations
alembic upgrade head
```

## Project Structure

```
main.py          # FastAPI app entry point — health check only
database.py      # SQLAlchemy engine, session factory, declarative Base
models.py        # ORM models skeleton (Loan entity)
requirements.txt # Python dependencies
alembic/         # Migration scripts and Alembic env
alembic.ini      # Alembic configuration
Dockerfile       # Container image definition
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy connection string |
| `ANVIL_RPC_URL` | Ethereum RPC endpoint (Anvil or testnet) |
| `BACKEND_SIGNER_PRIVATE_KEY` | Wallet private key for signing transactions |
| `CONTRACT_ADDRESS` | Deployed KiteFuel contract address |
