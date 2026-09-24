# Installation

## Windows prerequisites

Install Git, Python 3.12+, and MetaTrader 5. The MT5 terminal must be launched and connected to the intended Demo account before Python integration checks.

## Project environment

```powershell
cd D:\Projects\llm-mt5-agent
python --version
git --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,mt5]"
```

Do not install project dependencies into the global interpreter unless that is an intentional system-wide policy. The project-local `.venv` is preferred.

## Environment file

```powershell
Copy-Item .env.example .env
```

Put credentials only in `.env`, the operating system credential store, or a secret manager. `.env` is ignored by Git. Never paste passwords or API keys into YAML, shell history, tickets, or logs.

## Verify installation

```powershell
python -m mt5_agent --version
python scripts/smoke.py
pytest -m "not integration" -q
ruff check src tests scripts
mypy src
```

## Optional MT5 path

```powershell
$env:MT5_AGENT_MT5_PATH = 'C:\Program Files\Alpari MT5_2\terminal64.exe'
python scripts/check_mt5.py
python scripts/check_market.py
```

If `MT5_AGENT_MT5_PATH` is omitted, MetaTrader5 may discover the default terminal installation. The explicit path is recommended for repeatable Windows development.
