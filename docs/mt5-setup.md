# MT5 setup

The verified development terminal is:

```text
C:\Program Files\Alpari MT5_2\terminal64.exe
C:\Users\BazikadeStore\AppData\Roaming\MetaQuotes\Terminal\AF19ECCF568F855DF9D3196BBF8BF315
```

## Checklist

1. Launch the terminal.
2. Confirm the account is `Alpari-MT5-Demo`, not a real account.
3. Confirm the terminal reports a connection and the expected server.
4. Confirm `EURUSD` is available and the desired timeframe has candles.
5. Enable Algo Trading only when an intentional Demo execution test is planned.
6. Keep Python integration checks read-only by default.

Read-only verification:

```powershell
$env:MT5_AGENT_MT5_PATH = 'C:\Program Files\Alpari MT5_2\terminal64.exe'
python scripts/check_mt5.py
python scripts/check_market.py
```

The probe dynamically reads symbol information. Broker-specific contract size, tick value, volume step, and trade mode should be checked before any demo order test.

## Failure handling

The adapters distinguish disconnected terminals, unavailable symbols, missing candles, stale snapshots, invalid arguments, and broker trade restrictions. A failed observation stops the cycle. A disconnected non-dry executor does not submit an order without a verified connection.
