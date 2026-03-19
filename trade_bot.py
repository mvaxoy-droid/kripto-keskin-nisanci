import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import threading
import http.server
import socketserver
import os
from datetime import datetime

# --- RENDER'I KANDIRAN VE KENDİNE PİNG ATAN SİSTEM ---
def keep_alive():
    PORT = int(os.environ.get("PORT", 10000))
    Handler = http.server.SimpleHTTPRequestHandler
    
    # Kendi kendine ping atma fonksiyonu
    def self_ping():
        while True:
            try:
                # Kendi Render linkine istek atar
                requests.get("https://kripto-keskin-nisanci.onrender.com", timeout=10)
                print("Kendi kendine ping atıldı, Render uyanık tutuluyor.")
            except:
                print("Ping atılamadı ama sorun değil.")
            time.sleep(600) # 10 dakikada bir ping at

    threading.Thread(target=self_ping, daemon=True).start()

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Render için sahte port ({PORT}) açıldı.")
            httpd.serve_forever()
    except Exception as e:
        print(f"Port hatası: {e}")

threading.Thread(target=keep_alive, daemon=True).start()

# --- SENİN TELEGRAM BİLGİLERİN ---
TOKEN = "8737469275:AAHp9QIRGjHI-kus-yetC2IfzolbRrV1zl4" 
CHAT_ID = "1513813948"

# --- AYARLAR ---
VOLATILITE_SINIRI_YUZDE = 5.0
COOLDOWN_SURESI_SANIYE = 7200 # 2 saatte bir rapor atar
son_fiyat = None
son_bekleme_mesaji_zamani = 0

def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    parametreler = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    try:
        requests.get(url, params=parametreler, timeout=10)
        return True
    except:
        return False

def piyasa_durum_ozeti(fiyat, rsi, trend, hacim_durumu):
    return f"""
📊 *Anlık Durum Özeti*
💰 *BTC Fiyatı:* {fiyat:.2f} $
📈 *RSI (14):* {rsi:.1f}
🌊 *Trend (EMA200):* {trend}
📊 *Hacim:* {hacim_durumu}
"""

def canli_piyasa_analizi(sembol='BTC/USDT', zaman_dilimi='1h'):
    global son_fiyat, son_bekleme_mesaji_zamani
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
        guncel_fiyat = anlik['close']
        
        if son_fiyat is None:
            son_fiyat = guncel_fiyat
            return 
        
        fiyat_degisim_yuzdesi = ((guncel_fiyat - son_fiyat) / son_fiyat) * 100
        trend_yonu = "Yükseliş" if guncel_fiyat > anlik['EMA_200'] else "Düşüş"
        hacim_durumu = "Yeterli ✅" if anlik['volume'] > anlik['Hacim_Ortalama'] else "Düşük ❌"
        ozet = piyasa_durum_ozeti(guncel_fiyat, anlik['RSI_14'], trend_yonu, hacim_durumu)

        # Volatilite Mesajı
        if abs(fiyat_degisim_yuzdesi) >= VOLATILITE_SINIRI_YUZDE:
            yon = "DÜŞTÜ 📉" if fiyat_degisim_yuzdesi < 0 else "YÜKSELDİ 📈"
            telegram_mesaj_gonder(f"⚠️ *DİKKAT: SERT HAREKET!*\n{sembol} %{abs(fiyat_degisim_yuzdesi):.2f} {yon}!\n\n{ozet}")
            son_fiyat = guncel_fiyat
            return

        # Sinyal Kontrolü
        long_sarti = (anlik['close'] > anlik['EMA_200']) and (anlik['close'] <= anlik['Destek_20'] * 1.02) and (anlik['RSI_14'] < 45) and (anlik['MACD'] > anlik['MACD_Sinyal']) and (anlik['volume'] > anlik['Hacim_Ortalama'])
        short_sarti = (anlik['close'] < anlik['EMA_200']) and (anlik['close'] >= anlik['Direnc_20'] * 0.98) and (anlik['RSI_14'] > 55) and (anlik['MACD'] < anlik['MACD_Sinyal']) and (anlik['volume'] > anlik['Hacim_Ortalama'])
        
        if long_sarti:
            telegram_mesaj_gonder(f"🟢 *ALIM (LONG) SİNYALİ!*\n\n{ozet}")
        elif short_sarti:
            telegram_mesaj_gonder(f"🔴 *SATIŞ (SHORT) SİNYALİ!*\n\n{ozet}")
        else:
            su_anki_zaman = time.time()
            if (su_anki_zaman - son_bekleme_mesaji_zamani) > COOLDOWN_SURESI_SANIYE:
                telegram_mesaj_gonder(f"🛑 *DURUM: BEKLEMEDE*\n\n{ozet}")
                son_bekleme_mesaji_zamani = su_anki_zaman 
            
        son_fiyat = guncel_fiyat
        
    except Exception as e:
        print(f"Hata: {e}")

# Başlat
telegram_mesaj_gonder("🚀 *BOT TAM GAZ DEVAM EDİYOR!*")
while True:
    canli_piyasa_analizi('BTC/USDT', '1h')
    time.sleep(300) # 5 dakikada bir tara
