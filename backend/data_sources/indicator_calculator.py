import numpy as np
import pandas as pd
import talib
from typing import Dict, Any


class IndicatorCalculator:

    MA_PARAMS = {
        '1m': {'ma_period': [5, 10, 20, 30, 60, 120],
               'bbands_period': 20, 'bbands_std_up': 2.2, 'bbands_std_dn': 2.0,
               'bbands_overb_threshold': 0.85, 'bbands_overs_threshold': 0.15},
        '5m': {'ma_period': [6, 12, 24, 36, 72, 144],
               'bbands_period': 18, 'bbands_std_up': 2.1, 'bbands_std_dn': 2.1,
               'bbands_overb_threshold': 0.83, 'bbands_overs_threshold': 0.17},
        '15m': {'ma_period': [4, 8, 16, 24, 48, 96],
                'bbands_period': 15, 'bbands_std_up': 2.0, 'bbands_std_dn': 2.0,
                'bbands_overb_threshold': 0.80, 'bbands_overs_threshold': 0.20},
        '30m': {'ma_period': [3, 6, 12, 18, 36, 72],
                'bbands_period': 12, 'bbands_std_up': 1.9, 'bbands_std_dn': 1.9,
                'bbands_overb_threshold': 0.80, 'bbands_overs_threshold': 0.20},
        '60m': {'ma_period': [3, 5, 8, 13, 21, 34],
                'bbands_period': 10, 'bbands_std_up': 1.8, 'bbands_std_dn': 1.8,
                'bbands_overb_threshold': 0.80, 'bbands_overs_threshold': 0.20},
        '1d': {'ma_period': [5, 10, 20, 30, 60, 120, 250],
               'bbands_period': 20, 'bbands_std_up': 2, 'bbands_std_dn': 2,
               'bbands_overb_threshold': 0.80, 'bbands_overs_threshold': 0.20},
        '1wk': {'ma_period': [5, 10, 20, 30, 60],
                'bbands_period': 18, 'bbands_std_up': 2.1, 'bbands_std_dn': 2.1,
                'bbands_overb_threshold': 0.75, 'bbands_overs_threshold': 0.25},
        '1mo': {'ma_period': [3, 5, 10, 12, 24, 36],
                'bbands_period': 10, 'bbands_std_up': 2.3, 'bbands_std_dn': 2.3,
                'bbands_overb_threshold': 0.75, 'bbands_overs_threshold': 0.25},
        '3mo': {'ma_period': [2, 4, 8, 12, 16],
                'bbands_period': 6, 'bbands_std_up': 2.4, 'bbands_std_dn': 2.4,
                'bbands_overb_threshold': 0.70, 'bbands_overs_threshold': 0.30},
    }

    KDJ_PARAMS = {
        '1m': {'fastk_period': 5, 'slowk_period': 2, 'slowd_period': 2, 'overbought': 85, 'oversold': 15},
        '5m': {'fastk_period': 7, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 83, 'oversold': 17},
        '15m': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
        '30m': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
        '60m': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
        '1d': {'fastk_period': 9, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 80, 'oversold': 20},
        '1wk': {'fastk_period': 7, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 75, 'oversold': 25},
        '1mo': {'fastk_period': 5, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 75, 'oversold': 25},
        '3mo': {'fastk_period': 5, 'slowk_period': 3, 'slowd_period': 3, 'overbought': 70, 'oversold': 30},
    }

    MACD_PARAMS = {
        '1m': {'fastperiod': 6, 'slowperiod': 13, 'signalperiod': 4},
        '5m': {'fastperiod': 8, 'slowperiod': 17, 'signalperiod': 5},
        '15m': {'fastperiod': 10, 'slowperiod': 21, 'signalperiod': 7},
        '30m': {'fastperiod': 10, 'slowperiod': 23, 'signalperiod': 8},
        '60m': {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9},
        '1d': {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9},
        '1wk': {'fastperiod': 8, 'slowperiod': 17, 'signalperiod': 7},
        '1mo': {'fastperiod': 6, 'slowperiod': 13, 'signalperiod': 6},
        '3mo': {'fastperiod': 4, 'slowperiod': 8, 'signalperiod': 3},
    }

    RSI_PARAMS = {
        '1m': {'timeperiod': 9, 'overbought': 75, 'oversold': 25},
        '5m': {'timeperiod': 11, 'overbought': 73, 'oversold': 27},
        '15m': {'timeperiod': 12, 'overbought': 72, 'oversold': 28},
        '30m': {'timeperiod': 13, 'overbought': 71, 'oversold': 29},
        '60m': {'timeperiod': 14, 'overbought': 70, 'oversold': 30},
        '1d': {'timeperiod': 14, 'overbought': 70, 'oversold': 30},
        '1wk': {'timeperiod': 10, 'overbought': 65, 'oversold': 35},
        '1mo': {'timeperiod': 8, 'overbought': 65, 'oversold': 35},
        '3mo': {'timeperiod': 6, 'overbought': 60, 'oversold': 40},
    }

    MA_TYPE_MAPPING = {
        'sma': 0, 'ema': 1, 'wma': 2, 'dema': 3,
        'tema': 4, 'trima': 5, 'kama': 6,
    }

    MAJOR_CANDLESTICK_PATTERNS = {
        'CDLENGULFING': 'Engulfing Pattern',
        'CDLHARAMI': 'Harami Pattern',
        'CDLDOJI': 'Doji',
        'CDLHAMMER': 'Hammer',
        'CDLSHOOTINGSTAR': 'Shooting Star',
    }

    def compute_moving_averages(self, df: pd.DataFrame, interval: str, ma_type: str) -> pd.DataFrame:
        if isinstance(ma_type, str):
            ma_type_int = self.MA_TYPE_MAPPING.get(ma_type.lower())
            if ma_type_int is None:
                raise ValueError(f"Unsupported ma_type: {ma_type}")
        else:
            ma_type_int = ma_type

        if interval not in self.MA_PARAMS:
            raise ValueError(f"Unsupported interval: {interval}")

        params = self.MA_PARAMS[interval]
        output_df = pd.DataFrame()

        for ma_period in params['ma_period']:
            output_df[f'{ma_period}'] = talib.MA(df['Close'], timeperiod=ma_period, matype=ma_type_int)

        output_df['bbands_upper'], output_df['bbands_middle'], output_df['bbands_lower'] = talib.BBANDS(
            df['Close'],
            timeperiod=params['bbands_period'],
            nbdevup=params['bbands_std_up'],
            nbdevdn=params['bbands_std_dn'],
            matype=ma_type_int,
        )

        output_df['bbands_position'] = np.where(
            output_df['bbands_upper'].isna() | output_df['bbands_lower'].isna(), np.nan,
            np.where(df['Close'] >= output_df['bbands_upper'], 1.0,
            np.where(df['Close'] <= output_df['bbands_lower'], 0.0,
                     (df['Close'] - output_df['bbands_lower']) / (output_df['bbands_upper'] - output_df['bbands_lower'])))
        )

        output_df['bbands_overbs_signal'] = np.where(
            output_df['bbands_position'].isna(), 0,
            np.where(output_df['bbands_position'] >= params['bbands_overb_threshold'], -1,
            np.where(output_df['bbands_position'] <= params['bbands_overs_threshold'], 1, 0))
        )

        output_df.drop(['bbands_middle', 'bbands_position'], axis=1, inplace=True)
        return output_df

    def compute_kdj(self, df: pd.DataFrame, interval: str) -> Dict[str, Any]:
        if interval not in self.KDJ_PARAMS:
            raise ValueError(f"Unsupported interval: {interval}")

        params = self.KDJ_PARAMS[interval]
        H, L, C = df['High'], df['Low'], df['Close']

        low_list = L.rolling(params['fastk_period']).min()
        high_list = H.rolling(params['fastk_period']).max()
        rsv = 100 * ((C - low_list) / (high_list - low_list)).values

        k0 = 50
        d0 = 50
        k_factor = 1 / params['slowk_period']
        d_factor = 1 / params['slowd_period']

        k_list = []
        for v in rsv:
            if v == v:
                k0 = k_factor * v + (1 - k_factor) * k0
                k_list.append(k0)
            else:
                k_list.append(np.nan)

        d_list = []
        for k in k_list:
            if k == k:
                d0 = d_factor * k + (1 - d_factor) * d0
                d_list.append(d0)
            else:
                d_list.append(np.nan)

        j_list = [3 * k - 2 * d for k, d in zip(k_list, d_list)]

        k_series = pd.Series(k_list, index=df.index, name='K')
        d_series = pd.Series(d_list, index=df.index, name='D')
        j_series = pd.Series(j_list, index=df.index, name='J')

        kdj_cross_signal = np.where(
            k_series.notna() & d_series.notna() & (k_series > d_series) & (k_series.shift(1) <= d_series.shift(1)), 1,
            np.where(k_series.notna() & d_series.notna() & (k_series < d_series) & (k_series.shift(1) >= d_series.shift(1)), -1, 0))

        kdj_overbs_signal = np.where(
            k_series.notna() & d_series.notna() & (k_series > params['overbought']) & (d_series > params['overbought']), -1, 0)
        kdj_overbs_signal = np.where(
            k_series.notna() & d_series.notna() & (k_series < params['oversold']) & (d_series < params['oversold']), 1, kdj_overbs_signal)

        return {
            'k': k_series,
            'd': d_series,
            'j': j_series,
            'kdj_cross_signal': kdj_cross_signal,
            'kdj_overbs_signal': kdj_overbs_signal,
        }

    def compute_macd(self, df: pd.DataFrame, interval: str) -> Dict[str, Any]:
        if interval not in self.MACD_PARAMS:
            raise ValueError(f"Unsupported interval: {interval}")

        params = self.MACD_PARAMS[interval]
        macd, macd_signal_line, macd_hist = talib.MACD(
            df['Close'],
            fastperiod=params['fastperiod'],
            slowperiod=params['slowperiod'],
            signalperiod=params['signalperiod'],
        )
        macd_hist = macd_hist * 2

        macd = pd.Series(macd, index=df.index)
        macd_signal_line = pd.Series(macd_signal_line, index=df.index)
        macd_hist = pd.Series(macd_hist, index=df.index)

        macd_cross_signal = np.where(
            (macd > 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) &
            (macd > macd_signal_line) & (macd.shift(1) <= macd_signal_line.shift(1)), 2,
            np.where(
                (macd > 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) &
                (macd < macd_signal_line) & (macd.shift(1) >= macd_signal_line.shift(1)), -1, 0))
        macd_cross_signal = np.where(
            (macd < 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) &
            (macd > macd_signal_line) & (macd.shift(1) <= macd_signal_line.shift(1)), 1,
            np.where(
                (macd < 0) & (macd.shift(1).notna()) & (macd_signal_line.shift(1).notna()) &
                (macd < macd_signal_line) & (macd.shift(1) >= macd_signal_line.shift(1)), -2, macd_cross_signal))

        return {
            'macd': macd,
            'macd_signal_line': macd_signal_line,
            'macd_hist': macd_hist,
            'macd_cross_signal': macd_cross_signal,
        }

    def compute_rsi(self, df: pd.DataFrame, interval: str) -> Dict[str, Any]:
        if interval not in self.RSI_PARAMS:
            raise ValueError(f"Unsupported interval: {interval}")

        params = self.RSI_PARAMS[interval]
        rsi = talib.RSI(df['Close'], timeperiod=params['timeperiod'])
        rsi = pd.Series(rsi, index=df.index)

        rsi_overbs_signal = np.where(
            rsi.notna() & (rsi > params['overbought']), -1,
            np.where(rsi.notna() & (rsi < params['oversold']), 1, 0))

        return {
            'rsi': rsi,
            'rsi_overbs_signal': rsi_overbs_signal,
        }

    def compute_candlestick_patterns(self, df: pd.DataFrame, interval: str) -> pd.DataFrame:
        op = df['Open'].astype(float)
        hi = df['High'].astype(float)
        lo = df['Low'].astype(float)
        cl = df['Close'].astype(float)

        output_df = pd.DataFrame(index=df.index)
        for pattern_func in self.MAJOR_CANDLESTICK_PATTERNS:
            pattern_result = getattr(talib, pattern_func)(op, hi, lo, cl)
            pattern_result = pattern_result.fillna(0)
            output_df[pattern_func] = np.where(pattern_result > 0, 1,
                                               np.where(pattern_result < 0, -1, 0))

        output_df['cdl_pattern_signal'] = output_df.sum(axis=1)
        return output_df

    def compute_all_indicators(self, stock_price_df: pd.DataFrame, interval: str) -> Dict[str, Any]:
        result = {'stock_price': stock_price_df}

        for ma_type in ['sma', 'ema', 'wma', 'dema', 'tema', 'kama']:
            result[ma_type] = self.compute_moving_averages(stock_price_df, interval, ma_type)

        result['kdj'] = self.compute_kdj(stock_price_df, interval)
        result['macd'] = self.compute_macd(stock_price_df, interval)
        result['rsi'] = self.compute_rsi(stock_price_df, interval)
        result['cdl_pattern'] = self.compute_candlestick_patterns(stock_price_df, interval)

        return result
