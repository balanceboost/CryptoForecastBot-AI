import asyncio
import logging
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import telegram
import websockets
import json
from datetime import datetime, timezone
import talib
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import RotatingFileHandler
from rich.console import Console
from rich.logging import RichHandler
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
from sklearn.metrics import accuracy_score
import pickle
import os

# Настройка логирования
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('crypto_forecast_bot.log', maxBytes=10*1024*1024, backupCount=5),
        RichHandler(console=console, show_time=False, show_path=False)
    ]
)
logger = logging.getLogger('crypto_forecast_bot')

# Конфигурация
CONFIG = {
    'BINANCE_API_KEY': '',
    'BINANCE_API_SECRET': '',
    'TELEGRAM_BOT_TOKEN': ':AAEIKbVGgGxzUfw0i8pg6whBvLsxK5dzw2A',
    'TELEGRAM_CHAT_ID': '',
    'TRADING_PAIRS': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'CFX/USDT', 'JTO/USDT', 'GMX/USDT', 'FET/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'TRX/USDT', 'DOT/USDT', 'LINK/USDT', 'TON/USDT', 'SHIB/USDT', 'LTC/USDT', 'BCH/USDT', 'NEAR/USDT', 'APT/USDT', 'HBAR/USDT', 'PEPE/USDT', 'FIL/USDT', 'SUI/USDT', 'ARB/USDT', 'OP/USDT', 'ICP/USDT', 'VET/USDT', 'ALGO/USDT', 'INJ/USDT', 'GALA/USDT', 'THETA/USDT', 'FLOW/USDT', 'XLM/USDT', 'ZIL/USDT', 'SAND/USDT', 'MANA/USDT', 'CHZ/USDT'],  # Список пар для анализа, например ['BTC/USDT', 'ETH/USDT'], если пуст использует 'MAX_SYMBOLS'
    'TIMEFRAMES': ['5m', '15m'],  # Таймфреймы для анализа (1 мин, 5 мин, 15 мин)
    'UPDATE_INTERVAL': 30,  # Интервал обновления цикла анализа в секундах
    'MIN_LIQUIDITY': 5000,  # Минимальная ликвидность пары в USDT для включения в анализ
    'SPREAD_THRESHOLD': 0.003,  # Максимальный допустимый спред (в долях)
    'LOW_LIQUIDITY_HOURS': [(0, 4)],  # Часы низкой ликвидности (UTC), когда анализ приостанавливается
    'MAX_SYMBOLS': 100,  # Максимальное количество торговых пар для анализа
    'MIN_RR_RATIO': 0.5,  # Минимальное соотношение риск/прибыль для сигналов
    'SIGNAL_COOLDOWN': 1800,  # Минимальный интервал между сигналами для одной пары (в секундах)
    'MIN_STOP_SIZE': 0.003,  # Минимальный размер стоп-лосса (в долях от цены)
    'MIN_TAKE_SIZE': 0.0075,  # Минимальный размер тейк-профита (в долях от цены)
    'MAX_TAKE_RANGE': 5.0,  # Максимальный диапазон тейк-профита (в долях от ATR)
    'MIN_SIGNAL_INTERVAL': 1800,  # Минимальный интервал между сигналами для одной пары (в секундах, дублирует SIGNAL_COOLDOWN)
    'MODEL_DIR': 'models',  # Папка для хранения моделей и скейлеров
    'VOLATILITY_THRESHOLD': 0.01,  # Порог волатильности для определения рыночного состояния
    'ADX_THRESHOLD': 15,  # Порог ADX для определения тренда
    'RETRAIN_INTERVAL': 172800,  # Интервал переобучения модели в секундах (2 дня)
    'HISTORY_LIMIT': 5000,  # Максимальное количество исторических свечей для обучения
    'SCORE_THRESHOLD': 0.65,  # Порог уверенности модели для генерации сигнала
    'MAX_SIGNALS_PER_CYCLE': 50,  # Максимальное количество сигналов за один цикл анализа
    'MIN_ATR_FACTOR': 0.005,  # Минимальный коэффициент ATR для расчёта стоп-лосса и тейк-профита
    'VOLUME_THRESHOLD': 1.0,  # Порог объёма (в долях от среднего) для подтверждения сигнала
    'BREAKOUT_WINDOW': 5,  # Окно для определения пробоя уровней
    'SUPPORT_RESISTANCE_WINDOW': 50,  # Окно для расчёта уровней поддержки и сопротивления
    'MIN_CLASS_RATIO': 0.1,  # Минимальная доля каждого класса для сбалансированного обучения
    'RETURN_THRESHOLD_FACTOR': 0.5  # Коэффициент для расчёта порога доходности
}

class CryptoForecastBot:
    """Бот для анализа криптовалют с ML."""
    def __init__(self):
        logger.info("Инициализация CryptoForecastBot...")
        self.exchange = ccxt.binance({
            'apiKey': CONFIG['BINANCE_API_KEY'],
            'secret': CONFIG['BINANCE_API_SECRET'],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
        })
        self.bot = telegram.Bot(token=CONFIG['TELEGRAM_BOT_TOKEN'])
        self.symbols = []
        self.timeframes = CONFIG['TIMEFRAMES']
        self.websocket_url = 'wss://stream.binance.com:9443/ws'
        self.data = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.last_signal_time = {}
        self.models = {tf: None for tf in self.timeframes}
        self.scalers = {tf: StandardScaler() for tf in self.timeframes}
        self.last_retrain = {tf: 0 for tf in self.timeframes}
        self.last_market_state = {tf: 'unknown' for tf in self.timeframes}
        self.signal_count = 0
        os.makedirs(CONFIG['MODEL_DIR'], exist_ok=True)

        # Загрузка сохранённых моделей и скейлеров
        for tf in self.timeframes:
            model_path = os.path.join(CONFIG['MODEL_DIR'], f"model_{tf}.pkl")
            scaler_path = os.path.join(CONFIG['MODEL_DIR'], f"scaler_{tf}.pkl")
            if os.path.exists(model_path) and os.path.exists(scaler_path):
                try:
                    with open(model_path, 'rb') as f:
                        self.models[tf] = pickle.load(f)
                    with open(scaler_path, 'rb') as f:
                        self.scalers[tf] = pickle.load(f)
                    logger.info(f"Загружена модель и скейлер для {tf}")
                except Exception as e:
                    logger.error(f"Ошибка загрузки модели для {tf}: {e}")
        
        logger.info("Бот успешно инициализирован")

    async def validate_api_key(self):
        """Проверка валидности API-ключа."""
        try:
            balance = await self.exchange.fetch_balance()
            logger.info(f"API-ключ валиден, баланс: {balance.get('USDT', {})}")
        except Exception as e:
            logger.error(f"Ошибка проверки API-ключа: {e}")
            raise Exception("Невалидный API-ключ")

    async def run(self):
        """Основной цикл бота."""
        try:
            logger.info("Запуск основного цикла бота...")
            await self.validate_api_key()
            await self.load_symbols()
            if not self.symbols:
                logger.error("Символы не загружены, завершение...")
                return
            for tf in self.timeframes:
                if self.models[tf] is None:
                    logger.info(f"Обучение модели для {tf}")
                    await self.train_model(tf)
            asyncio.create_task(self.websocket_listener())
            await asyncio.sleep(10)
            while True:
                self.signal_count = 0
                signaled_pairs = set()
                for symbol in self.symbols:
                    for tf in self.timeframes:
                        if symbol in signaled_pairs:
                            logger.debug(f"Пропуск {symbol} на {tf}: сигнал уже был в этом цикле")
                            continue
                        if self.signal_count >= CONFIG['MAX_SIGNALS_PER_CYCLE']:
                            logger.info("Достигнут лимит сигналов за цикл, пропуск остальных пар")
                            break
                        result = await self.analyze_pair(symbol, tf)
                        if isinstance(result, dict) and result:
                            await self.send_forecast(result)
                            logger.info(f"Сигнал отправлен для {result['symbol']} на {result['timeframe']}")
                            signaled_pairs.add(symbol)
                            self.signal_count += 1
                    if self.signal_count >= CONFIG['MAX_SIGNALS_PER_CYCLE']:
                        break
                logger.info(f"Цикл анализа завершен, сгенерировано сигналов: {self.signal_count}")
                await asyncio.sleep(CONFIG['UPDATE_INTERVAL'])
        except Exception as e:
            logger.error(f"Ошибка основного цикла: {e}")
            await asyncio.sleep(5)
            await self.run()

    async def load_symbols(self):
        """Загрузка торговых пар USDT."""
        try:
            logger.info("Загрузка торговых пар...")
            await self.exchange.load_markets()
            markets = self.exchange.markets
            self.symbols = []
            for symbol in CONFIG['TRADING_PAIRS']:
                symbol = symbol.upper()
                if (symbol in markets and 
                    markets[symbol]['active'] and 
                    markets[symbol]['type'] == 'spot' and 
                    markets[symbol].get('quote') == 'USDT'):
                    volume = await self.fetch_trading_volume(symbol)
                    df = await self.fetch_ohlcv(symbol, '1h', limit=100)
                    if df.empty or len(df) < 50:
                        logger.info(f"Пропуск {symbol}: недостаточно данных")
                        continue
                    volatility = df['close'].pct_change().rolling(window=20).std().mean()
                    if volume > 10000 and volatility > 0.0001:
                        self.symbols.append(symbol)
                    else:
                        logger.info(f"Пропуск {symbol}: низкий объём {volume:.2f} или волатильность {volatility:.4f}")
                else:
                    logger.debug(f"Пропуск {symbol}: недоступна")
            if not self.symbols:
                logger.warning("Указанные пары недоступны, переход к дефолтным")
                self.symbols = ['BTC/USDT', 'ETH/USDT']
            logger.info(f"Загружено {len(self.symbols)} пар: {self.symbols}")
            self.data = {
                symbol: {tf: pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        for tf in self.timeframes}
                for symbol in self.symbols
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки пар: {e}")
            self.symbols = ['BTC/USDT', 'ETH/USDT']
            self.data = {
                symbol: {tf: pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        for tf in self.timeframes}
                for symbol in self.symbols
            }

    async def fetch_ohlcv(self, symbol, timeframe, limit=200):
        """Получение OHLCV-данных."""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            logger.debug(f"Получено {len(df)} записей для {symbol} на {timeframe}")
            return df
        except Exception as e:
            logger.error(f"Ошибка получения OHLCV для {symbol}: {e}")
            return pd.DataFrame()

    async def fetch_order_book(self, symbol):
        """Получение стакана ордеров."""
        try:
            order_book = await self.exchange.fetch_order_book(symbol, limit=5)
            bids = order_book['bids']
            asks = order_book['asks']
            bid_price = bids[0][0] if bids else 0
            ask_price = asks[0][0] if asks else 0
            if bid_price <= 0 or ask_price <= 0 or bid_price >= ask_price:
                logger.debug(f"Некорректный стакан для {symbol}")
                return None, float('inf')
            spread = (ask_price - bid_price) / bid_price
            liquidity = sum(bid[1] * bid[0] for bid in bids) + sum(ask[1] * ask[0] for ask in asks)
            logger.info(f"Ликвидность для {symbol}: {liquidity:.4f}, спред={spread:.4f}")
            return liquidity, spread
        except Exception as e:
            logger.error(f"Ошибка получения стакана для {symbol}: {e}")
            return None, float('inf')

    async def fetch_trading_volume(self, symbol, timeframe='1h', limit=24):
        """Получение среднего объёма торгов в USDT."""
        try:
            df = await self.fetch_ohlcv(symbol, timeframe, limit)
            avg_volume = (df['volume'] * df['close']).mean()
            return avg_volume
        except Exception as e:
            logger.error(f"Ошибка получения объёма для {symbol}: {e}")
            return 0

    def calculate_indicators(self, df):
        """Расчёт признаков для ML."""
        try:
            if len(df) < 50:
                logger.info(f"Недостаточно данных для индикаторов: {len(df)} записей")
                return df
            df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
            df['roc'] = talib.ROC(df['close'], timeperiod=12)
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            df['avg_price'] = df['close'].rolling(window=50).mean()
            df['norm_atr'] = df['atr'] / df['avg_price']
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
            df['momentum'] = talib.MOM(df['close'], timeperiod=10)
            df['volatility'] = df['close'].pct_change().rolling(window=20).std()
            df['ema_fast'] = talib.EMA(df['close'], timeperiod=12)
            df['ema_slow'] = talib.EMA(df['close'], timeperiod=26)
            df['obv'] = talib.OBV(df['close'], df['volume'])
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['macd'], df['macd_signal'], _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
            logger.debug(f"Рассчитаны индикаторы для {len(df)} записей")
            return df.dropna()
        except Exception as e:
            logger.error(f"Ошибка расчета индикаторов: {e}")
            return df

    def is_bullish_candle(self, df):
        """Проверка бычьей свечи."""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        body = abs(latest['close'] - latest['open'])
        return (latest['close'] > latest['open'] and
                body > 0.5 * (latest['high'] - latest['low']) and
                latest['close'] > prev['close'])

    def is_bearish_candle(self, df):
        """Проверка медвежьей свечи."""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        body = abs(latest['close'] - latest['open'])
        return (latest['close'] < latest['open'] and
                body > 0.5 * (latest['high'] - latest['low']) and
                latest['close'] < prev['close'])

    def prepare_features(self, df):
        """Подготовка признаков для ML с адаптивным порогом."""
        try:
            features = [
                'vwap', 'roc', 'norm_atr', 'adx', 'momentum', 'volatility',
                'ema_fast', 'ema_slow', 'obv', 'close', 'volume', 'rsi',
                'macd', 'macd_signal', 'bb_upper', 'bb_middle', 'bb_lower'
            ]
            X = df[features].dropna()
            if len(X) == 0:
                logger.debug("Нет данных для признаков")
                return None, None, False
            avg_atr = df['norm_atr'].mean()
            return_threshold = CONFIG['RETURN_THRESHOLD_FACTOR'] * avg_atr
            logger.debug(f"Адаптивный порог возврата: {return_threshold:.4f}")
            future_return = df['close'].shift(-1) / df['close'] - 1
            y = pd.Series(0, index=future_return.index)
            y[future_return > return_threshold] = 1
            y[future_return < -return_threshold] = -1
            common_index = X.index.intersection(y.index)
            X = X.loc[common_index]
            y = y.loc[common_index]
            class_counts = y.value_counts()
            logger.debug(f"Баланс классов: {class_counts.to_dict()}")
            balanced = len(class_counts) >= 3 and min(class_counts) >= CONFIG['MIN_CLASS_RATIO'] * len(y)
            return X, y, balanced
        except Exception as e:
            logger.error(f"Ошибка подготовки признаков: {e}")
            return None, None, False

    async def train_model(self, timeframe):
        """Обучение ML-модели для таймфрейма с кросс-валидацией."""
        try:
            logger.info(f"Обучение модели для {timeframe}")
            all_X, all_y = [], []
            for symbol in self.symbols:
                df = await self.fetch_ohlcv(symbol, timeframe, limit=CONFIG['HISTORY_LIMIT'])
                if df.empty or len(df) < 100:
                    logger.info(f"Пропуск {symbol} на {timeframe}: недостаточно данных ({len(df)})")
                    continue
                df = self.calculate_indicators(df)
                logger.debug(f"Данные для {symbol} на {timeframe}: свечей={len(df)}, "
                            f"диапазон цен={df['close'].min():.4f}-{df['close'].max():.4f}, "
                            f"волатильность={df['close'].pct_change().std():.4f}")
                X, y, balanced = self.prepare_features(df)
                if X is None or len(X) == 0 or not balanced:
                    logger.info(f"Пропуск {symbol} на {timeframe}: нет признаков или несбалансированные классы")
                    continue
                if not X.index.equals(y.index):
                    logger.error(f"Несоответствие индексов для {symbol} на {timeframe}: X={len(X)}, y={len(y)}")
                    continue
                all_X.append(X)
                all_y.append(y)
            if not all_X:
                logger.warning(f"Нет данных для обучения на {timeframe}")
                return
            X = pd.concat(all_X, ignore_index=True)
            y = pd.concat(all_y, ignore_index=True)
            if len(X) < 100:
                logger.warning(f"Недостаточно данных для обучения: {len(X)}")
                return
            if len(X) != len(y):
                logger.error(f"Несоответствие размеров X и y: X={len(X)}, y={len(y)}")
                return
            if X.isna().any().any() or y.isna().any():
                logger.error(f"Пропуски в данных: X={X.isna().sum().sum()}, y={y.isna().sum()}")
                return
            class_counts = y.value_counts()
            balanced = len(class_counts) >= 3 and min(class_counts) >= CONFIG['MIN_CLASS_RATIO'] * len(y)
            if not balanced:
                logger.warning(f"Несбалансированные классы для {timeframe}: {class_counts.to_dict()}")
                if self.models[timeframe] is not None:
                    logger.info(f"Используется старая модель для {timeframe}")
                    return
            X_scaled = self.scalers[timeframe].fit_transform(X)
            model = lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.03,
                max_depth=5,
                min_child_samples=50,
                reg_lambda=0.1,
                class_weight='balanced',
                random_state=42,
                verbose=-1
            )
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            val_scores = []
            for train_idx, val_idx in kf.split(X_scaled):
                X_train, X_val = X_scaled[train_idx], X_scaled[val_idx]
                y_train, y_val = y[train_idx], y[val_idx]
                model.fit(X_train, y_train)
                val_pred = model.predict(X_val)
                val_scores.append(accuracy_score(y_val, val_pred))
            val_accuracy = np.mean(val_scores)
            logger.info(f"Точность на кросс-валидации для {timeframe}: {val_accuracy:.4f}")
            model.fit(X_scaled, y)
            self.models[timeframe] = model
            self.last_retrain[timeframe] = datetime.now(timezone.utc).timestamp()
            model_path = os.path.join(CONFIG['MODEL_DIR'], f"model_{timeframe}.pkl")
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            scaler_path = os.path.join(CONFIG['MODEL_DIR'], f"scaler_{timeframe}.pkl")
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scalers[timeframe], f)
            logger.info(f"Модель обучена и сохранена для {timeframe}")
        except Exception as e:
            logger.error(f"Ошибка обучения модели для {timeframe}: {str(e)}", exc_info=True)

    async def check_market_change(self, df, timeframe):
        """Проверка смены рынка для переобучения."""
        try:
            if len(df) < 50:
                return False
            now = datetime.now(timezone.utc).timestamp()
            if now - self.last_retrain[timeframe] < 3600:
                return False
            adx = df['adx'].rolling(window=5).mean().iloc[-1]
            volatility = df['close'].pct_change().rolling(window=20).std().mean()
            current_state = (
                'trend' if adx > CONFIG['ADX_THRESHOLD'] else
                'volatile' if volatility > CONFIG['VOLATILITY_THRESHOLD'] else
                'flat'
            )
            if (current_state != self.last_market_state[timeframe] or
                now - self.last_retrain[timeframe] > CONFIG['RETRAIN_INTERVAL']):
                logger.info(f"Обнаружена смена рынка на {timeframe}: {self.last_market_state[timeframe]} -> {current_state}")
                self.last_market_state[timeframe] = current_state
                await self.train_model(timeframe)
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки рынка: {e}")
            return False

    def is_low_liquidity_time(self):
        """Проверка времени низкой ликвидности."""
        try:
            now = datetime.now(timezone.utc)
            hour = now.hour
            for start, end in CONFIG['LOW_LIQUIDITY_HOURS']:
                if start <= hour < end:
                    logger.info(f"Низкая ликвидность: {hour}:00 UTC")
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки времени ликвидности: {e}")
            return False

    async def confirm_trend_on_higher_tf(self, symbol, timeframe):
        """Подтверждение тренда на старшем таймфрейме."""
        try:
            # Определяем старший таймфрейм
            timeframe_map = {
                '5m': '15m',
                '15m': '1h',
                '1h': '4h',
                '4h': '1d',
                '2h': '8h',
                '8h': '1d',
                '1d': '1w'
            }
            higher_tf = timeframe_map.get(timeframe, '1h')  # По умолчанию 1h, если таймфрейм неизвестен
            logger.debug(f"Проверка тренда для {symbol} на старшем таймфрейме {higher_tf}")

            # Запрашиваем данные для старшего таймфрейма
            df = await self.fetch_ohlcv(symbol, higher_tf, limit=50)
            if df.empty or len(df) < 50:
                logger.info(f"Недостаточно данных на {higher_tf} для {symbol} ({len(df)} записей)")
                return False

            # Рассчитываем индикаторы
            df = self.calculate_indicators(df)
            if len(df) < 50:
                logger.info(f"Недостаточно индикаторов на {higher_tf} для {symbol} ({len(df)} записей)")
                return False

            latest = df.iloc[-1]
            if not all(key in latest for key in ['ema_fast', 'ema_slow', 'adx']):
                logger.error(f"Недостаточно данных индикаторов на {higher_tf} для {symbol}")
                return False

            # Подтверждаем тренд: бычий (EMA fast > slow и ADX > порог) или медвежий
            is_trend = (
                (latest['ema_fast'] > latest['ema_slow'] and latest['adx'] > CONFIG['ADX_THRESHOLD']) or
                (latest['ema_fast'] < latest['ema_slow'] and latest['adx'] > CONFIG['ADX_THRESHOLD'])
            )
            logger.debug(f"Тренд на {higher_tf} для {symbol}: {'подтверждён' if is_trend else 'не подтверждён'} "
                        f"(EMA fast={latest['ema_fast']:.4f}, EMA slow={latest['ema_slow']:.4f}, ADX={latest['adx']:.2f})")
            return is_trend
        except Exception as e:
            logger.error(f"Ошибка проверки тренда на {higher_tf} для {symbol}: {e}")
            return False

    async def analyze_pair(self, symbol, timeframe):
        """Анализ пары с ML, поддержкой флэта и проверкой старшего таймфрейма."""
        try:
            logger.info(f"Анализ пары {symbol} на {timeframe}")
            if self.is_low_liquidity_time():
                logger.info(f"Пропуск {symbol}: низкая ликвидность")
                return None

            now = datetime.now(timezone.utc).timestamp()
            symbol_key = symbol
            if symbol_key in self.last_signal_time and now - self.last_signal_time[symbol_key] < CONFIG['MIN_SIGNAL_INTERVAL']:
                logger.info(f"Пропуск {symbol} на {timeframe}: сигнал слишком частый")
                return None

            df = await self.fetch_ohlcv(symbol, timeframe, limit=100)
            if df.empty or len(df) < 50:
                logger.info(f"Пропуск {symbol} на {timeframe}: недостаточно данных ({len(df)} записей)")
                return None

            liquidity, spread = await self.fetch_order_book(symbol)
            if liquidity is None or liquidity < CONFIG['MIN_LIQUIDITY'] or spread > CONFIG['SPREAD_THRESHOLD']:
                logger.info(f"Пропуск {symbol}: ликвидность={liquidity}, спред={spread:.4f}")
                return None

            df = self.calculate_indicators(df)
            await self.check_market_change(df, timeframe)

            if self.models[timeframe] is None:
                logger.warning(f"Модель для {timeframe} не обучена")
                return None

            X, _, balanced = self.prepare_features(df)
            if X is None or len(X) == 0 or not balanced:
                logger.debug(f"Пропуск {symbol} на {timeframe}: нет признаков или несбалансированные классы")
                return None

            latest = df.iloc[-1]
            required_keys = ['close', 'high', 'low', 'norm_atr', 'volatility', 'ema_fast', 'ema_slow', 'adx']
            if not all(key in latest for key in required_keys):
                logger.error(f"Недостаточно данных в latest для {symbol} на {timeframe}: отсутствуют {set(required_keys) - set(latest.index)}")
                return None

            avg_volatility = df['volatility'].rolling(window=50).mean().iloc[-1]
            if latest['volatility'] < 0.5 * avg_volatility:
                logger.info(f"Пропуск {symbol} на {timeframe}: низкая волатильность ({latest['volatility']:.4f} < {0.5 * avg_volatility:.4f})")
                return None

            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            if latest['volume'] < CONFIG['VOLUME_THRESHOLD'] * avg_volume:
                logger.debug(f"Пропуск {symbol} на {timeframe}: низкий объём ({latest['volume']:.2f} < {CONFIG['VOLUME_THRESHOLD'] * avg_volume:.2f})")
                return None

            entry_price = latest['close']
            norm_atr = max(latest['norm_atr'], CONFIG['MIN_ATR_FACTOR'])
            avg_atr = df['norm_atr'].rolling(window=50).mean().iloc[-1]
            if norm_atr < avg_atr:
                logger.debug(f"Пропуск {symbol} на {timeframe}: низкий ATR ({norm_atr:.4f} < {avg_atr:.4f})")
                return None

            support = df['low'].rolling(window=CONFIG['SUPPORT_RESISTANCE_WINDOW']).min().iloc[-1]
            resistance = df['high'].rolling(window=CONFIG['SUPPORT_RESISTANCE_WINDOW']).max().iloc[-1]

            is_flat = latest['adx'] < CONFIG['ADX_THRESHOLD']
            if not is_flat:
                # Проверка близости к уровням только для трендовых сигналов
                if entry_price < support + 0.5 * norm_atr * entry_price or entry_price > resistance - 0.5 * norm_atr * entry_price:
                    logger.info(f"Пропуск {symbol} на {timeframe}: цена близко к уровням (ADX={latest['adx']:.2f})")
                    return None

            X_latest = pd.DataFrame([X.iloc[-1]], columns=X.columns)
            X_scaled = self.scalers[timeframe].transform(X_latest)
            proba = self.models[timeframe].predict_proba(X_scaled)[0]
            score = proba[1] - proba[-1]
            logger.info(f"ML-скор для {symbol} на {timeframe}: score={score:.4f}, proba={proba.tolist()}")

            signal = None
            if is_flat:
                # Сигналы во флэте: пробой уровней
                if (latest['close'] > resistance and
                    latest['close'] > df['high'].rolling(window=CONFIG['BREAKOUT_WINDOW']).max().iloc[-2]):
                    signal = 'buy'
                    logger.info(f"Флэтовый сигнал покупки для {symbol}: пробой сопротивления {resistance:.4f}")
                elif (latest['close'] < support and
                      latest['close'] < df['low'].rolling(window=CONFIG['BREAKOUT_WINDOW']).min().iloc[-2]):
                    signal = 'sell'
                    logger.info(f"Флэтовый сигнал продажи для {symbol}: пробой поддержки {support:.4f}")
            else:
                # Трендовые сигналы
                if score > CONFIG['SCORE_THRESHOLD'] and latest['ema_fast'] > latest['ema_slow']:
                    signal = 'buy'
                    logger.info(f"Трендовый сигнал покупки для {symbol}: score={score:.2f}, EMA fast={latest['ema_fast']:.4f} > EMA slow={latest['ema_slow']:.4f}")
                elif score < -CONFIG['SCORE_THRESHOLD'] and latest['ema_fast'] < latest['ema_slow']:
                    signal = 'sell'
                    logger.info(f"Трендовый сигнал продажи для {symbol}: score={score:.2f}, EMA fast={latest['ema_fast']:.4f} < EMA slow={latest['ema_slow']:.4f}")

            if not signal:
                logger.info(f"Нет сигнала для {symbol} на {timeframe}")
                return None

            # Проверка свечных паттернов и пробоя
            if signal == 'buy':
                if not (self.is_bullish_candle(df) and
                        latest['close'] > df['high'].rolling(window=CONFIG['BREAKOUT_WINDOW']).max().iloc[-2]):
                    logger.info(f"Пропуск {symbol} на {timeframe}: нет подтверждения покупки (бычья свеча/пробой)")
                    return None
            else:
                if not (self.is_bearish_candle(df) and
                        latest['close'] < df['low'].rolling(window=CONFIG['BREAKOUT_WINDOW']).min().iloc[-2]):
                    logger.info(f"Пропуск {symbol} на {timeframe}: нет подтверждения продажи (медвежья свеча/пробой)")
                    return None

            # Проверка старшего таймфрейма для всех таймфреймов
            if not await self.confirm_trend_on_higher_tf(symbol, timeframe):
                logger.info(f"Пропуск {symbol} на {timeframe}: нет подтверждения тренда на старшем таймфрейме")
                return None

            predicted_return = abs(score) * norm_atr * entry_price
            if signal == 'buy':
                stop_loss = max(entry_price - 2 * norm_atr * entry_price, support * 1.01)
                take_profit = min(entry_price + max(8 * norm_atr * entry_price, predicted_return), resistance * 0.99)
                stop_loss = min(stop_loss, entry_price * (1 - CONFIG['MIN_STOP_SIZE']))
                take_profit = max(take_profit, entry_price * (1 + CONFIG['MIN_TAKE_SIZE']))
                take_profit = min(take_profit, entry_price + CONFIG['MAX_TAKE_RANGE'] * norm_atr * entry_price)
                if take_profit <= entry_price or stop_loss >= entry_price:
                    logger.info(f"Пропуск {symbol} на {timeframe}: некорректный ТП/СЛ (ТП={take_profit:.4f}, СЛ={stop_loss:.4f})")
                    return None
            else:
                stop_loss = min(entry_price + 2 * norm_atr * entry_price, resistance * 0.99)
                take_profit = max(entry_price - max(8 * norm_atr * entry_price, predicted_return), support * 1.01)
                stop_loss = max(stop_loss, entry_price * (1 + CONFIG['MIN_STOP_SIZE']))
                take_profit = min(take_profit, entry_price * (1 - CONFIG['MIN_TAKE_SIZE']))
                take_profit = max(take_profit, entry_price - CONFIG['MAX_TAKE_RANGE'] * norm_atr * entry_price)
                if take_profit >= entry_price or stop_loss <= entry_price:
                    logger.info(f"Пропуск {symbol} на {timeframe}: некорректный ТП/СЛ (ТП={take_profit:.4f}, СЛ={stop_loss:.4f})")
                    return None

            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0

            signal_info = {
                'symbol': symbol,
                'timeframe': timeframe,
                'signal': signal,
                'score': score,
                'rsi': latest.get('rsi', 0),
                'macd': latest.get('macd', 0),
                'rr_ratio': rr_ratio,
                'risk': risk,
                'reward': reward,
                'norm_atr': norm_atr,
                'predicted_return': predicted_return,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'volume': latest['volume'],
                'candle': 'Bullish' if self.is_bullish_candle(df) else 'Bearish' if self.is_bearish_candle(df) else 'Neutral'
            }
            logger.info(f"Сигнал: {json.dumps(signal_info, indent=2)}")

            if rr_ratio < CONFIG['MIN_RR_RATIO']:
                logger.info(f"Пропуск {symbol} на {timeframe}: RR={rr_ratio:.2f} < {CONFIG['MIN_RR_RATIO']}")
                return None

            self.last_signal_time[symbol_key] = now
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'signal': signal,
                'entry': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'score': score,
                'norm_atr': norm_atr
            }
        except Exception as e:
            logger.error(f"Ошибка анализа пары {symbol} на {timeframe}: {e}")
            return None

    async def send_forecast(self, forecast):
        """Отправка прогноза в Telegram."""
        try:
            symbol = forecast['symbol']
            timeframe = forecast['timeframe']
            signal = forecast['signal']
            entry_price = forecast['entry']
            stop_loss = forecast['stop_loss']
            take_profit = forecast['take_profit']
            score = forecast['score']
            norm_atr = forecast['norm_atr']

            position_type = (
                "Краткосрочный" if timeframe in ['1h'] else
                "Среднесрочный" if timeframe in ['2h', '4h'] else
                "Долгосрочный"
            )

            entry_range_min = entry_price - min(0.005 * entry_price, 0.5 * norm_atr * entry_price)
            entry_range_max = entry_price + min(0.005 * entry_price, 0.5 * norm_atr * entry_price)

            if entry_price < 0.001:
                price_format = ".8f"
            elif entry_price < 1.0:
                price_format = ".6f"
            else:
                price_format = ".3f"

            message = (
                f"📩 {symbol} {timeframe} | {position_type}\n"
                f"💰 Цена: ${entry_price:{price_format}}\n"
                f"🔥 Сила сигнала: {score:.2f}\n"
                f"📉 Вход: ${entry_range_max:{price_format}}–${entry_range_min:{price_format}}\n"
                f"🔥 Сигнал: {'Покупка' if signal == 'buy' else 'Продажа'}\n"
                f"⏳ Тейк-профит: ${take_profit:{price_format}}\n"
                f"❌ Стоп-лосс: ${stop_loss:{price_format}}"
            )

            await self.bot.send_message(chat_id=CONFIG['TELEGRAM_CHAT_ID'], text=message)
            logger.info(f"Прогноз отправлен для {symbol} на {timeframe}")
        except Exception as e:
            logger.error(f"Ошибка отправки прогноза: {e}")

    async def websocket_listener(self):
        """Слушатель WebSocket с проверкой дубликатов."""
        try:
            logger.info("Запуск WebSocket...")
            while True:
                async with websockets.connect(self.websocket_url) as ws:
                    # Формируем уникальный список потоков
                    stream_params = list(set(
                        f"{sym.lower().replace('/', '')}@kline_{tf}"
                        for sym in self.symbols for tf in self.timeframes
                    ))
                    subscribe_msg = {
                        "method": "SUBSCRIBE",
                        "params": stream_params,
                        "id": 1
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"Подписка на {len(stream_params)} потоков ({len(self.symbols)} пар x {len(self.timeframes)} таймфреймов)")
                    seen_timestamps = {sym: {tf: set() for tf in self.timeframes} for sym in self.symbols}
                    while True:
                        try:
                            message = await ws.recv()
                            data = json.loads(message)
                            if 'k' not in data:
                                logger.debug(f"Пропуск сообщения без kline: {data.get('e', 'N/A')}")
                                continue
                            kline = data['k']
                            symbol = next(
                                (s for s in self.symbols if s.lower().replace('/', '') == data['s'].lower()),
                                None
                            )
                            if not symbol:
                                logger.debug(f"Пропуск неизвестного символа: {data.get('s', '')}")
                                continue
                            tf = kline['i']
                            if tf not in self.timeframes:
                                logger.debug(f"Пропуск неизвестного таймфрейма: {tf}")
                                continue
                            timestamp = pd.to_datetime(kline['t'], unit='ms')
                            timestamp_str = str(timestamp)
                            if timestamp_str in seen_timestamps[symbol][tf]:
                                logger.debug(f"Дубликат данных для {symbol} {tf} {timestamp_str}")
                                continue
                            seen_timestamps[symbol][tf].add(timestamp_str)
                            # Ограничение размера seen_timestamps
                            if len(seen_timestamps[symbol][tf]) > 100:
                                seen_timestamps[symbol][tf] = set(list(seen_timestamps[symbol][tf])[-100:])
                            new_row = pd.DataFrame([{
                                'timestamp': timestamp,
                                'open': float(kline.get('o', 0)),
                                'high': float(kline.get('h', 0)),
                                'low': float(kline.get('l', 0)),
                                'close': float(kline.get('c', 0)),
                                'volume': float(kline.get('v', 0))
                            }])
                            if not self.data[symbol][tf].empty:
                                self.data[symbol][tf] = pd.concat([self.data[symbol][tf], new_row], ignore_index=True).tail(100)
                            else:
                                self.data[symbol][tf] = new_row
                            logger.debug(f"Данные обновлены для {symbol} на {tf}")
                        except json.JSONDecodeError as e:
                            logger.warning(f"Ошибка декодирования JSON в WebSocket: {e}")
                            continue
                        except Exception as e:
                            logger.warning(f"Ошибка обработки сообщения: {e}")
                            continue
        except Exception as e:
            logger.error(f"Ошибка WebSocket подключения: {e}")
            await asyncio.sleep(5)
            await self.websocket_listener()

async def main():
    """Запуск бота."""
    try:
        logger.info("Запуск бота...")
        bot = CryptoForecastBot()
        await bot.run()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
