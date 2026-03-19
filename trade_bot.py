import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
from datetime import datetime

# --- SENİN TELEGRAM BİLGİLERİN ---
TOKEN = "8737469275:AAHp9QIRGjHI-kus-yetC2IfzolbRrV1zl4" 
CHAT_ID = "1513813948"

def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    parametreler = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    for i in range(3):
        try:
            response = requests.get(url, params=parametreler, timeout=10)
            if response.status_code == 200:
                print("Mesaj başarıyla gönderildi.")
                return True
        except Exception as e:
            print(f"Deneme {i+1} başarısız: {e}")
            time.sleep(5)
    return False

def canli_piyasa_analizi(sembol='BTC/USDT', zaman_dilimi='1h'):
    borsa = ccxt.kucoin({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
    try:
        mumlar = borsa.fetch_ohlcv(sembol, timeframe=zaman_dilimi, limit=250)
        df = pd.DataFrame(mumlar, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['RSI_14'] = df.ta.rsi(length=14)
        df['EMA_200'] = df.ta.ema(length=200)
        df['Destek_20'] = df['low'].rolling(window=20).min()
        df['Direnc_20'] = df['high'].rolling(window=20).max()
        macd = df.ta.macd()
        df['MACD'] = macd.iloc[:, 0]
        df['MACD_Sinyal'] = macd.iloc[:, 2]
        df['Hacim_Ortalama'] = df['volume'].rolling(window=20).mean()
        df.dropna(inplace=True)
        anlik = df.iloc[-1]
        fiyat = anlik['close']
        
        long_sarti = (anlik['close'] > anlik['EMA_200']) and (anlik['close'] <= anlik['Destek_20'] * 1.02) and (anlik['RSI_14'] < 45) and (anlik['MACD'] > anlik['MACD_Sinyal']) and (anlik['volume'] > anlik['Hacim_Ortalama'])
        short_sarti = (anlik['close'] < anlik['EMA_200']) and (anlik['close'] >= anlik['Direnc_20'] * 0.98) and (anlik['RSI_14'] > 55) and (anlik['MACD'] < anlik['MACD_Sinyal']) and (anlik['volume'] > anlik['Hacim_Ortalama'])
        
        su_an = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if long_sarti:
            telegram_mesaj_gonder(f"🟢 *ALIM (LONG)*\n📌 {sembol}\n💲 {fiyat} $\n⏱️ {su_an}")
        elif short_sarti:
            telegram_mesaj_gonder(f"🔴 *SATIŞ (SHORT)*\n📌 {sembol}\n💲 {fiyat} $\n⏱️ {su_an}")
        else:
            print(f"[{su_an}] Fırsat yok.")
    except Exception as e:
        print(f"Hata: {e}")

print("Bot Render üzerinde başlatılıyor...")
telegram_mesaj_gonder("🚀 *RENDER SİSTEMİ AKTİF!*")
while True:
    canli_piyasa_analizi('BTC/USDT', '1h')
    time.sleep(300)
