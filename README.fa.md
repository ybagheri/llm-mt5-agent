# llm-mt5-agent

[English README](README.md)

دستیار معاملاتی قدرتمند مبتنی بر LLM برای MetaTrader 5؛ با رویکرد دمو، قابل توضیح، قابل آزمایش و دارای محدودیت‌های ایمنی قطعی.

این پروژه داده‌های بازار و حساب MT5 را می‌خواند، تحلیل قطعی price-action انجام می‌دهد، از LLM پیشنهاد ساختاریافته می‌گیرد، سپس پیشنهاد را با قوانین قطعی ریسک اعتبارسنجی و در journal ثبت می‌کند. این سامانه یک دستیار تصمیم‌یار است، نه معامله‌گر خودکار؛ خروجی LLM هرگز نمی‌تواند کنترل‌های ریسک یا اجرای سفارش را دور بزند.

## ویژگی‌ها

- اتصال MT5، حساب، ترمینال، پوزیشن‌ها، سفارش‌ها، تاریخچه، نماد، Tick و OHLCV.
- موتور قطعی تحلیل ساختار بازار و Donchian، جدا از استدلال LLM.
- خروجی ساختاریافته `BUY`، `SELL` یا `HOLD` با fallback امن به `HOLD`.
- الزام تطابق عملیات جهت‌دار LLM با سیگنال قطعی بازار.
- کنترل fail-closed برای زیان روزانه، spread، فاصله stop و ایمنی حساب.
- بررسی تعداد و حجم پوزیشن‌ها در سطح کل حساب.
- حفاظت در برابر سیگنال تکراری، cooldown، حاشیه، session، SL/TP و محدودیت exposure.
- حالت `DRY_RUN` به‌صورت پیش‌فرض؛ بدون ارسال سفارش.
- حالت `DEMO` فقط با اتصال معتبر و حسابی که صراحتاً Demo/Contest باشد.
- `LIVE` به‌صورت پیش‌فرض غیرفعال است و به فعال‌سازی صریح نیاز دارد.
- لایه provider برای APIهای OpenAI-compatible، Ollama و Gemini.
- حافظه و journal محلی SQLite.
- داشبورد محلی فقط‌خواندنی با escaping و security headers.
- لاگ ساختاریافته و audit event با حذف secret و اطلاعات حساس حساب.

## شروع سریع ویندوز

پیش‌نیازها: Git، Python 3.12 یا جدیدتر، MetaTrader 5 و حساب Demo متصل به ترمینال.

```powershell
cd D:\Projects\llm-mt5-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,mt5]"
Copy-Item .env.example .env
python -m mt5_agent --version
pytest -m "not integration" -q
```

ترمینال Alpari ارائه‌شده در این مسیر نصب و اجرا شده است:

```text
C:\Program Files\Alpari MT5_2\terminal64.exe
C:\Users\BazikadeStore\AppData\Roaming\MetaQuotes\Terminal\AF19ECCF568F855DF9D3196BBF8BF315
```

بررسی فقط‌خواندنی به حساب `Alpari-MT5-Demo` متصل شد و داده‌های `EURUSD M1` را دریافت کرد. در زمان بررسی، Algo Trading در ترمینال غیرفعال بود؛ بنابراین هیچ سفارشی ارسال نشد.

## تنظیمات و امنیت

`MT5_AGENT_TRADING_MODE` و `MT5_AGENT_EXECUTION_MODE` باید یکسان باشند؛ `execution_mode` مرجع واقعی است و مقدار پیش‌فرض آن `dry_run` است.

```powershell
$env:MT5_AGENT_MT5_PATH = 'C:\Program Files\Alpari MT5_2\terminal64.exe'
python scripts/check_mt5.py
python scripts/check_market.py
python scripts/check_strategy.py
python scripts/check_plan.py --stub
python scripts/run_agent.py --symbols EURUSD --timeframe M1 --cycles 1
python scripts/run_agent.py --symbols EURUSD --timeframe M1 --loop
python scripts/serve_dashboard.py
```

هیچ‌گاه `.env`، رمز عبور، API key، token یا کلید خصوصی را commit نکنید. فایل `.env` در Git ignore شده است. LLM ممکن است داده بازار و context حساب را دریافت کند؛ پیش از استفاده از سرویس ابری، سیاست نگهداری و آموزش داده و قوانین منطقه‌ای آن را بررسی کنید.

## جریان تصمیم

```text
MT5 -> داده بازار و حساب -> تحلیل قطعی -> context ساختاریافته
   -> LLM planner -> اعتبارسنجی -> risk supervisor
   -> اجرای dry-run/demo/live صریح -> journal SQLite
```

اگر سیگنال قطعی `LONG` نباشد، LLM اجازه `BUY` ندارد؛ برای `SHORT` نیز `SELL` مجاز است. در ابهام، پاسخ `HOLD` است. قوانین ریسک شامل حساب، session، نماد مجاز، زیان روزانه، تعداد پوزیشن، exposure، spread، SL/TP، فاصله stop، تکرار و cooldown هستند.

## آزمون

```powershell
pytest -m "not integration" -q
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
```

آزمون‌های MT5 فقط با فعال‌کردن متغیر زیر اجرا می‌شوند:

```powershell
$env:MT5_AGENT_RUN_LIVE_MT5_TESTS = 'true'
pytest tests/integration -q
```

## مستندات

- [معماری](docs/architecture.md)
- [نصب](docs/installation.md)
- [تنظیمات](docs/configuration.md)
- [راه‌اندازی MT5](docs/mt5-setup.md)
- [LLM](docs/llm.md)
- [سیگنال‌ها](docs/signals.md)
- [مدیریت ریسک](docs/risk-management.md)
- [آزمون](docs/testing.md)
- [عیب‌یابی](docs/troubleshooting.md)
- [توسعه](docs/development.md)
- [پرسش‌های متداول](docs/faq.md)

## هشدار

این پروژه نرم‌افزار آموزشی و تصمیم‌یار است، نه مشاوره مالی یا تضمین سود. معاملات اهرمی می‌توانند بیش از سرمایه اولیه از دست بروند. ابتدا فقط داده و paper/dry-run را آزمایش کنید و سپس در صورت نیاز از حساب Demo استفاده کنید.

## مجوز

MIT؛ جزئیات در [LICENSE](LICENSE).
