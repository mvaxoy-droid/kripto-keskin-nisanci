import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
from datetime import datetime

# --- SENİN TELEGRAM BİLGİLERİN ---
TOKEN = "8737469275:AAHp9QIRGjHI-kus-yetC2IfzolbRrV1zl4" 
CHAT_ID = "1513813948"

# --- YENİ EKLENEN AYARLAR VE HAFIZA ---
VOLATILITE_SINIRI_YUZDE = 5.0  # %5'lik ani değişimde acil durum uyarısı
COOLDOWN_SURESI_SANIYE = 7200  # "Durum Beklemede" mesajları için 2 saat aralık
son_fiyat = None
son_bekleme_mesaji_zamani = 0

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
        su_an = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # İlk açılışta referans fiyatı kaydet
        if son_fiyat is None:
            son_fiyat = guncel_fiyat
            print(f"[{su_an}] İlk referans fiyatı alındı: {son_fiyat}")
            return # İlk döngüyü fiyatı ezberlemek için kullan
        
        # --- 1. VOLATİLİTE KONTROLÜ (ACİL DURUM) ---
        fiyat_degisim_yuzdesi = ((guncel_fiyat - son_fiyat) / son_fiyat) * 100
        
        # Özet verilerini anlık hesapla
        trend_yonu = "Yükseliş (Fiyat > EMA200)" if guncel_fiyat > anlik['EMA_200'] else "Düşüş (Fiyat < EMA200)"
        hacim_durumu = "Yeterli ✅" if anlik['volume'] > anlik['Hacim_Ortalama'] else "Düşük ❌"
        ozet = piyasa_durum_ozeti(guncel_fiyat, anlik['RSI_14'], trend_yonu, hacim_durumu)

        if abs(fiyat_degisim_yuzdesi) >= VOLATILITE_SINIRI_YUZDE:
            yon = "DÜŞTÜ 📉" if fiyat_degisim_yuzdesi < 0 else "YÜKSELDİ 📈"
            acil_mesaj = f"⚠️ *DİKKAT: SERT HAREKET!*\n{sembol} aniden %{abs(fiyat_degisim_yuzdesi):.2f} {yon}!\n\n{ozet}"
            telegram_mesaj_gonder(acil_mesaj)
            son_fiyat = guncel_fiyat # Fiyatı güncelle
            return # Piyasa çok dalgalı, bu 5 dakikalık döngüde sinyal arama, sadece uyarı ver.

        # --- 2. SİNYAL KONTROLÜ ---
        long_sarti = (anlik['close'] > anlik['EMA_200']) and (anlik['close'] <= anlik['Destek_20'] * 1.02) and (anlik['RSI_14'] < 45) and (anlik['MACD'] > anlik['MACD_Sinyal']) and (anlik['volume'] > anlik['Hacim_Ortalama'])
        short_sarti = (anlik['close'] < anlik['EMA_200']) and (anlik['close'] >= anlik['Direnc_20'] * 0.98) and (anlik['RSI_14'] > 55) and (anlik['MACD'] < anlik['MACD_Sinyal']) and (anlik['volume'] > anlik['Hacim_Ortalama'])
        
        if long_sarti:
            telegram_mesaj_gonder(f"🟢 *ALIM (LONG) SİNYALİ!*\n📌 {sembol}\n\n{ozet}")
        elif short_sarti:
            telegram_mesaj_gonder(f"🔴 *SATIŞ (SHORT) SİNYALİ!*\n📌 {sembol}\n\n{ozet}")
        else:
            # --- 3. NEDEN İŞLEM YOK? GEREKÇE ANALİZİ ---
            gerekce = "Piyasa yatay seyrediyor, belirgin bir sinyal koşulu oluşmadı."
            if anlik['volume'] <= anlik['Hacim_Ortalama']:
                gerekce = "Hacim, işlemi onaylamak için yeterince yüksek değil."
            elif (anlik['close'] > anlik['EMA_200']) and (anlik['close'] > anlik['Destek_20'] * 1.02):
                gerekce = "Trend yukarı ancak fiyat güvenli alım desteğine kadar geri çekilmedi."
            elif (anlik['close'] < anlik['EMA_200']) and (anlik['close'] < anlik['Direnc_20'] * 0.98):
                gerekce = "Trend aşağı ancak fiyat short açmak için dirence yeterince yakın değil."

            # --- 4. BEKLEME BİLDİRİMİ (COOLDOWN SİSTEMİ) ---
            su_anki_zaman = time.time()
            if (su_anki_zaman - son_bekleme_mesaji_zamani) > COOLDOWN_SURESI_SANIYE:
                durum_mesaji = f"🛑 *DURUM: BEKLEMEDE*\n*Gerekçe:* {gerekce}\n\n{ozet}"
                telegram_mesaj_gonder(durum_mesaji)
                son_bekleme_mesaji_zamani = su_anki_zaman # Sayacı sıfırla
            
            print(f"[{su_an}] Fırsat yok. Gerekçe: {gerekce}")

        son_fiyat = guncel_fiyat # Döngü sonunda referans fiyatı kaydet
        
    except Exception as e:
        print(f"Hata: {e}")

print("Bot Render üzerinde başlatılıyor...")
telegram_mesaj_gonder("🚀 *RENDER SİSTEMİ GÜNCELLENDİ VE AKTİF!*")
while True:
    canli_piyasa_analizi('BTC/USDT', '1h')
    time.sleep(300)
