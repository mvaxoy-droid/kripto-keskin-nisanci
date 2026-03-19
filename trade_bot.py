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

# --- 1. YARDIMCI SİSTEMLER (ARKA PLANDA ÇALIŞIR) ---
def keep_alive():
    PORT = int(os.environ.get("PORT", 10000))
    def self_ping():
        while True:
            try:
                # Botun kendi linkini uyanık tutar
                requests.get("https://kripto-keskin-nisanci.onrender.com", timeout=10)
            except:
                pass
            time.sleep(600)

    threading.Thread(target=self_ping, daemon=True).start()
    
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

# Yardımcı sistemleri ayrı bir kolda başlat
threading.Thread(target=keep_alive, daemon=True).start()

# --- 2. AYARLAR VE TELEGRAM ---
TOKEN = "8737469275:AAHp9QIRGjHI-kus-yetC2IfzolbRrV1zl4" 
CHAT_ID = "1513813948"
VOLATILITE_SINIRI_YUZDE = 5.0
COOLDOWN_SURESI_SANIYE = 7200 # 2 saat
son_fiyat = None
son_bekleme_mesaji_zamani = 0

def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

# --- 3. ANA ANALİZ MOTORU ---
def canli_piyasa_analizi():
    global son_fiyat, son_bekleme_mesaji_zamani
    try:
        borsa = ccxt.kucoin({'enableRateLimit': True})
        mumlar = borsa.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=100)
        df = pd.DataFrame(mumlar, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # İndikatörler
        df['RSI_14'] = df.ta.rsi(length=14)
        df['EMA_200'] = df.ta.ema(length=200)
        df['Destek_20'] = df['low'].rolling(window=20).min()
        df['Direnc_20'] = df['high'].rolling(window=20).max()
        macd = df.ta.macd()
        df['MACD'] = macd.iloc[:, 0]
        df['MACD_Sinyal'] = macd.iloc[:, 2]
        df['Hacim_Ort'] = df['volume'].rolling(window=20).mean()
        
        anlik = df.iloc[-1]
        fiyat = anlik['close']
        su_an = datetime.now().strftime("%H:%M:%S")

        if son_fiyat is None:
            son_fiyat = fiyat
            print(f"[{su_an}] İlk fiyat alındı: {fiyat}")
            return

        # Rapor Metni
        trend = "Yükseliş" if fiyat > anlik['EMA_200'] else "Düşüş"
        hacim = "Yeterli ✅" if anlik['volume'] > anlik['Hacim_Ort'] else "Düşük ❌"
        rapor = f"\n💰 Fiyat: {fiyat:.2f}$\n📈 RSI: {anlik['RSI_14']:.1f}\n🌊 Trend: {trend}\n📊 Hacim: {hacim}"

        # 1. Volatilite Kontrolü
        degisim = ((fiyat - son_fiyat) / son_fiyat) * 100
        if abs(degisim) >= VOLATILITE_SINIRI_YUZDE:
            telegram_mesaj_gonder(f"⚠️ *SERT HAREKET (%{abs(degisim):.2f})*\n{rapor}")
            son_fiyat = fiyat
            return

        # 2. Sinyal Kontrolü
        long = (fiyat > anlik['EMA_200']) and (fiyat <= anlik['Destek_20'] * 1.02) and (anlik['RSI_14'] < 45)
        short = (fiyat < anlik['EMA_200']) and (fiyat >= anlik['Direnc_20'] * 0.98) and (anlik['RSI_14'] > 55)

        if long:
            telegram_mesaj_gonder(f"🟢 *LONG SİNYALİ*\n{rapor}")
        elif short:
            telegram_mesaj_gonder(f"🔴 *SHORT SİNYALİ*\n{rapor}")
        else:
            # Cooldown'a göre bekleme mesajı
            if (time.time() - son_bekleme_mesaji_zamani) > COOLDOWN_SURESI_SANIYE:
                telegram_mesaj_gonder(f"🛑 *DURUM: BEKLEMEDE*\n{rapor}")
                son_bekleme_mesaji_zamani = time.time()
        
        print(f"[{su_an}] Analiz tamamlandı. Fiyat: {fiyat}")
        son_fiyat = fiyat

    except Exception as e:
        print(f"Hata: {e}")

# --- BOTU BAŞLAT ---
telegram_mesaj_gonder("🚀 *BOT KESİNTİSİZ MODDA YENİDEN BAŞLATILDI!*")
while True:
    canli_piyasa_analizi()
    time.sleep(300) # 5 dakikada bir kontrol
