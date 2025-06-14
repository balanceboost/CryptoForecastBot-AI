# CryptoForecastBotAI

## Описание

**Проект требует доработки, настройки и отладки.**

**CryptoForecastBotAI** — это аналитический бот для прогнозирования движений криптовалютного рынка на бирже Binance с использованием машинного обучения (LightGBM). Бот анализирует рыночные данные, технические индикаторы (VWAP, ROC, ATR, ADX, Momentum, RSI, MACD, Bollinger Bands, OBV, EMA) и свечные паттерны для генерации торговых сигналов. Сигналы отправляются в Telegram-канал с указанием точек входа, стоп-лосса и тейк-профита. Бот поддерживает анализ на таймфреймах 5m и 15m, фильтрацию пар по ликвидности, спреду и объёму, а также адаптивное переобучение модели каждые 2 дня или при смене рыночных условий (тренд/флэт/волатильность). Он не выполняет сделки автоматически, а предоставляет аналитику для принятия торговых решений.

### Основные возможности:
- Анализ торговых пар USDT (настраиваемый список, включает BTC/USDT, ETH/USDT, BNB/USDT и др.).
- Поддержка таймфреймов: 5m, 15m.
- Машинное обучение с LightGBM для прогнозирования сигналов (покупка/продажа).
- Адаптивное переобучение модели каждые 2 дня или при смене рыночного состояния.
- Технические индикаторы с фильтрацией по волатильности, объёму и спреду.
- Подтверждение сигналов на старшем таймфрейме.
- WebSocket для получения рыночных данных в реальном времени.
- Логирование с ротацией файлов и красивым выводом в консоль.
- Сохранение моделей и скейлеров в папке `models`.

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/your-username/CryptoForecastBot.git
   cd CryptoForecastBot
   ```

2. **Установите зависимости:**
   Убедитесь, что у вас установлен Python 3.8+. Создайте виртуальное окружение и установите зависимости:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Для Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Содержимое `requirements.txt`:
   ```
   ccxt>=2.0.0
   pandas>=1.5.0
   numpy>=1.23.0
   python-telegram-bot>=13.7
   websockets>=10.0
   TA-Lib>=0.4.24
   rich>=12.0.0
   lightgbm>=3.3.0
   scikit-learn>=1.0.0
   ```

3. **Установите TA-Lib:**
   Для работы индикаторов требуется библиотека TA-Lib. Следуйте инструкциям для вашей ОС:
   - **Ubuntu/Debian**:
     ```bash
     sudo apt-get install libta-lib0 libta-lib-dev
     pip install TA-Lib
     ```
   - **Windows**:
     Скачайте pre-built бинарники с [Unofficial Windows Binaries for Python](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib) и установите:
     ```bash
     pip install TA_Lib‑0.4.24‑cp39‑cp39‑win_amd64.whl
     ```
   - **MacOS**:
     ```bash
     brew install ta-lib
     pip install TA-Lib
     ```

## Настройка

1. **Обновите конфигурацию в коде:**
   Откройте файл `crypto_forecast_bot.py` и обновите словарь `CONFIG` с вашими ключами и настройками:
   ```python
   CONFIG = {
       'BINANCE_API_KEY': 'your_binance_api_key',
       'BINANCE_API_SECRET': 'your_binance_api_secret',
       'TELEGRAM_BOT_TOKEN': 'your_telegram_bot_token',
       'TELEGRAM_CHAT_ID': 'your_telegram_chat_id',
       'TRADING_PAIRS': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', ...],
       'TIMEFRAMES': ['5m', '15m'],
       ...
   }
   ```
   - **Binance API Key**: Получите на [Binance API Management](https://www.binance.com/en-US/my/settings/api-management).
   - **Telegram Bot Token**: Создайте бота через [@BotFather](https://t.me/BotFather) и получите токен.
   - **Telegram Chat ID**: ID вашего Telegram-канала или группы (можно узнать через бота @getidsbot).

2. **Создайте папку для моделей:**
   Убедитесь, что папка `models` существует в корне проекта:
   ```bash
   mkdir models
   ```

## Использование

1. **Запустите бота:**
   ```bash
   python crypto_forecast_bot.py
   ```

2. **Мониторинг:**
   - Логи записываются в `crypto_forecast_bot.log` с ротацией (макс. 10 МБ, 5 резервных копий).
   - Модели и скейлеры сохраняются в папке `models`.
   - Прогнозы отправляются в указанный Telegram-канал в формате:
     ```
     📩 BTC/USDT 5m | Краткосрочный
     💰 Цена: $45000.000
     🔥 Сила сигнала: 0.65
     📉 Вход: $45225.000–$44775.000
     🔥 Сигнал: Покупка
     ⏳ Тейк-профит: $46000.000
     ❌ Стоп-лосс: $44500.000
     ```

3. **Остановка:**
   Завершите выполнение с помощью `Ctrl+C`.

## Структура проекта

```
CryptoForecastBot/
├── crypto_forecast_bot.py       # Основной скрипт бота
├── models/                      # Папка для моделей и скейлеров
├── crypto_forecast_bot.log      # Лог работы бота
├── requirements.txt             # Зависимости
└── README.md                    # Документация
```

Для поддержки автора: `TFbR9gXb5r6pcALasjX1FKBArbKc4xBjY8` (USDT, сеть TRC-20)

## Контрибьютинг

1. Форкните репозиторий.
2. Создайте ветку для вашей фичи (`git checkout -b feature/your-feature`).
3. Сделайте коммиты с понятными сообщениями.
4. Отправьте Pull Request в `main`.

## Лицензия

Проект распространяется под лицензией MIT. Подробности в файле `LICENSE`.

## Предупреждение

Торговля криптовалютами сопряжена с высокими рисками. Прогнозы бота не являются финансовыми рекомендациями. Используйте бота на свой страх и риск. Автор не несёт ответственности за финансовые убытки.

---

# CryptoForecastBotAI

## Overview

**The project requires further development, customization, and debugging.**

**CryptoForecastBotAI** is an analytical bot designed for forecasting cryptocurrency market movements on the Binance exchange using machine learning (LightGBM). It analyzes market data, technical indicators (VWAP, ROC, ATR, ADX, Momentum, RSI, MACD, Bollinger Bands, OBV, EMA), and candlestick patterns to generate trading signals. The signals are sent to a Telegram channel, including entry points, stop-loss, and take-profit levels. The bot supports analysis on 5m and 15m timeframes, filters pairs by liquidity, spread, and volume, and retrains its model adaptively every 2 days or upon market condition changes. It does not execute trades automatically but provides analytics for informed trading decisions.

### Key Features:
- Analysis of trading pairs (configurable, includes BTC/USDT, ETH/USDT, BNB/USDT, etc.).
- Supported timeframes: 5m, 15m.
- Machine learning with LightGBM for predicting signals (buy/sell).
- Adaptive model retraining every 2 days or when market conditions change (trend/flat/volatility).
- Technical indicators with filtering by volatility, volume, and spread.
- Signal confirmation on higher timeframes.
- WebSocket for real-time market data.
- Logging with file rotation and formatted console output.
- Model and scaler storage in the `models` directory.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/CryptoForecastBot.git
   cd CryptoForecastBot
   ```

2. **Install dependencies:**
   Ensure you have Python 3.8+ installed. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Contents of `requirements.txt`:
   ```
   ccxt>=2.0.0
   pandas>=1.5.0
   numpy>=1.23.0
   python-telegram-bot>=13.7
   websockets>=10.0
   TA-Lib>=0.4.24
   rich>=12.0.0
   lightgbm>=3.3.0
   scikit-learn>=1.0.0
   ```

3. **Install TA-Lib:**
   The TA-Lib library is required for technical indicators. Follow the instructions for your OS:
   - **Ubuntu/Debian**:
     ```bash
     sudo apt-get install libta-lib0 libta-lib-dev
     pip install TA-Lib
     ```
   - **Windows**:
     Download pre-built binaries from [Unofficial Windows Binaries for Python](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib) and install:
     ```bash
     pip install TA_Lib‑0.4.24‑cp39‑cp39‑win_amd64.whl
     ```
   - **macOS**:
     ```bash
     brew install ta-lib
     pip install TA-Lib
     ```

## Configuration

1. **Update configuration in code:**
   Open `crypto_forecast_bot.py` and update the `CONFIG` dictionary with your keys and settings:
   ```python
   CONFIG = {
       'BINANCE_API_KEY': 'your_binance_api_key',
       'BINANCE_API_SECRET': 'your_binance_api_secret',
       'TELEGRAM_BOT_TOKEN': 'your_telegram_bot_token',
       'TELEGRAM_CHAT_ID': 'your_telegram_chat_id',
       'TRADING_PAIRS': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', ...],
       'TIMEFRAMES': ['5m', '15m'],
       ...
   }
   ```
   - **Binance API Key**: Obtain from [Binance API Management](https://www.binance.com/en-US/my/settings/api-management).
   - **Telegram Bot Token**: Create a bot via [@BotFather](https://t.me/BotFather) and get the token.
   - **Telegram Chat ID**: Find your channel or group ID using @getidsbot.

2. **Create a models directory:**
   Ensure the `models` directory exists in the project root:
   ```bash
   mkdir models
   ```

## Usage

1. **Run the bot:**
   ```bash
   python crypto_forecast_bot.py
   ```

2. **Monitoring:**
   - Logs are written to `crypto_forecast_bot.log` with rotation (max 10 MB, 5 backups).
   - Models and scalers are saved in the `models` directory.
   - Forecasts are sent to the specified Telegram channel in the format:
     ```
     📩 BTC/USDT 5m | Short-Term
     💰 Price: $45000.000
     🔥 Signal Strength: 0.65
     📉 Entry: $45225.000–$44775.000
     🔥 Signal: Buy
     ⏳ Take-Profit: $46000.000
     ❌ Stop-Loss: $44500.000
     ```

3. **Stopping:**
   Terminate the bot with `Ctrl+C`.

## Project Structure

```
CryptoForecastBot/
├── crypto_forecast_bot.py       # Main bot script
├── models/                      # Directory for models and scalers
├── crypto_forecast_bot.log      # Bot operation log
├── requirements.txt             # Dependencies
└── README.md                    # Documentation
```

To support the author: `TFbR9gXb5r6pcALasjX1FKBArbKc4xBjY8` (USDT, TRC-20 network)

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit your changes with clear messages.
4. Submit a Pull Request to the `main` branch.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
