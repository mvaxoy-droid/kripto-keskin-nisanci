import ccxt
import pandas as pd
import requests
import time
import threading
import http.server
import socketserver
import os
from datetime import datetime

# --- RENDER UYANIK TUTMA SİSTEMİ ---
def keep_alive():
    PORT = int(os.environ.get("PORT", 10000))
    def self_ping():
        while True:
            try:
                requests.get("https://kripto-keskin-nisanci.onrender.com", timeout=10)
            except:
                pass
            time.sleep(600)
    threading.Thread(target=self_ping, daemon=True).start()
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# --- AYARLAR ---
TOKEN = "8737469275:AAHp9QIRGjHI-kus-yetC2IfzolbRrV1zl4" 
CHAT_ID = "1513813948"
VOLATILITE_SINIRI = 5.0
COOLDOWN = 60
son_fiyat = None
son_bekleme_mesaji_zamani = 0

def telegram_mesaj_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

# --- ANA ANALİZ MOTORU (HATA DÜZELTİLMİŞ) ---
def canli_piyasa_analizi():
    global son_fiyat, son_bekleme_mesaji_zamani
    try:
        borsa = ccxt.kucoin({'enableRateLimit': True})
        mumlar = borsa.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=200)
        df = pd.DataFrame(mumlar, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # İndikatörleri manuel ve güvenli hesapla
        df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['Destek_20'] = df['low'].rolling(window=20).min()
        df['Direnc_20'] = df['high'].rolling(window=20).max()
        df['Hacim_Ort'] = df['volume'].rolling(window=20).mean()
        
        # RSI Hesaplama (Manuel)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        anlik = df.iloc[-1]
        fiyat = anlik['close']
        rsi = anlik['RSI_14']
        su_an = datetime.now().strftime("%H:%M:%S")

        if son_fiyat is None:
            son_fiyat = fiyat
            print(f"[{su_an}] İlk fiyat hafızaya alındı: {fiyat}")
            return

        # Raporlama
        trend = "Yükseliş" if fiyat > anlik['EMA_200'] else "Düşüş"
        hacim_durumu = "Yeterli ✅" if anlik['volume'] > anlik['Hacim_Ort'] else "Düşük ❌"
        rapor = f"\n💰 Fiyat: {fiyat:.2f}$\n📈 RSI: {rsi:.1f}\n🌊 Trend: {trend}\n📊 Hacim: {hacim_durumu}"

        # Değişim Kontrolü
        degisim = ((fiyat - son_fiyat) / son_fiyat) * 100
        if abs(degisim) >= VOLATILITE_SINIRI:
            telegram_mesaj_gonder(f"⚠️ *SERT HAREKET (%{abs(degisim):.2f})*\n{rapor}")
            son_fiyat = fiyat
            return

        # Sinyal Mantığı
        long = (fiyat > anlik['EMA_200']) and (fiyat <= anlik['Destek_20'] * 1.02) and (rsi < 45)
        short = (fiyat < anlik['EMA_200']) and (fiyat >= anlik['Direnc_20'] * 0.98) and (rsi > 55)

        if long:
            telegram_mesaj_gonder(f"🟢 *LONG SİNYALİ*\n{rapor}")
        elif short:
            telegram_mesaj_gonder(f"🔴 *SHORT SİNYALİ*\n{rapor}")
        else:
            if (time.time() - son_bekleme_mesaji_zamani) > COOLDOWN:
                telegram_mesaj_gonder(f"🛑 *DURUM: BEKLEMEDE*\n{rapor}")
                son_bekleme_mesaji_zamani = time.time()
        
        print(f"[{su_an}] Başarıyla analiz edildi. BTC: {fiyat}")
        son_fiyat = fiyat

    except Exception as e:
        print(f"Hata detayı: {e}")

# BAŞLAT
telegram_mesaj_gonder("🚀 *BOT SON GÜNCELLEME İLE AKTİF!* (Hatalar giderildi)")
while True:
    canli_piyasa_analizi()
    time.sleep(60)
