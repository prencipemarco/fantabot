# bot.py - Versione ottimizzata per Render
import requests
import json
import os
import time
from datetime import datetime, timedelta
import schedule
import logging

# Setup logging per Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RenderFantacalcioBot:
    def __init__(self):
        # Variabili d'ambiente Render
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.api_key = os.environ.get('FOOTBALL_API_KEY', '')
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("❌ Mancano TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID nelle variabili d'ambiente")
        
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Stato in memoria (Render non ha filesystem persistente)
        self.notification_state = {
            "last_close": None,
            "last_open": None,
            "last_check": None
        }
        
        logger.info("🤖 Bot Fantacalcio inizializzato per Render")
    
    def send_message(self, message):
        """Invia messaggio Telegram con retry"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"✅ Messaggio inviato (tentativo {attempt + 1})")
                    return True
                else:
                    logger.warning(f"⚠️ Tentativo {attempt + 1} fallito: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Errore tentativo {attempt + 1}: {e}")
                
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Backoff esponenziale
        
        logger.error("❌ Impossibile inviare messaggio dopo tutti i tentativi")
        return False
    
    def get_current_matchday_fixtures(self):
        """Ottiene le partite della giornata corrente"""
        # Calendario manuale Serie A 2024/25
        # AGGIORNA QUESTE DATE con il calendario reale
        current_fixtures = [
            # Esempio giornata - MODIFICA CON DATE REALI
            {
                "datetime": datetime(2024, 9, 21, 15, 0),  # 21/09/2024 15:00
                "home": "Milan", 
                "away": "Inter"
            },
            {
                "datetime": datetime(2024, 9, 21, 18, 0),  # 21/09/2024 18:00
                "home": "Juventus",
                "away": "Roma" 
            },
            {
                "datetime": datetime(2024, 9, 22, 20, 45),  # 22/09/2024 20:45
                "home": "Napoli",
                "away": "Atalanta"
            }
        ]
        
        # Filtra solo le partite di oggi/domani
        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        filtered_fixtures = []
        for fixture in current_fixtures:
            fixture_date = fixture["datetime"].date()
            if fixture_date == today or fixture_date == tomorrow:
                filtered_fixtures.append(fixture)
        
        return sorted(filtered_fixtures, key=lambda x: x["datetime"])
    
    def should_close_market(self, fixtures):
        """Determina se chiudere il mercato"""
        if not fixtures:
            return False, None
        
        now = datetime.now()
        first_match = fixtures[0]
        first_match_time = first_match["datetime"]
        
        # Chiude 2 ore prima della prima partita
        close_time = first_match_time - timedelta(hours=2)
        
        # Controlla se è il momento giusto e non è già stato fatto oggi
        if (close_time <= now <= first_match_time and 
            self.notification_state["last_close"] != first_match_time.strftime("%Y-%m-%d")):
            return True, first_match_time.strftime("%Y-%m-%d")
        
        return False, None
    
    def should_open_market(self, fixtures):
        """Determina se aprire il mercato"""
        if not fixtures:
            return False, None
        
        now = datetime.now()
        last_match = fixtures[-1]
        last_match_time = last_match["datetime"]
        
        # Apre 3 ore dopo l'ultima partita
        open_time = last_match_time + timedelta(hours=3)
        
        # Controlla se è il momento giusto e non è già stato fatto
        if (now >= open_time and 
            self.notification_state["last_open"] != last_match_time.strftime("%Y-%m-%d")):
            return True, last_match_time.strftime("%Y-%m-%d")
        
        return False, None
    
    def create_close_message(self, fixtures):
        """Crea messaggio chiusura mercato"""
        first_match = fixtures[0]
        total_matches = len(fixtures)
        
        # Lista partite
        matches_text = ""
        for i, match in enumerate(fixtures, 1):
            time_str = match["datetime"].strftime("%H:%M")
            date_str = match["datetime"].strftime("%d/%m")
            matches_text += f"{i}. {date_str} {time_str} - {match['home']} vs {match['away']}\n"
        
        message = f"""🚨 <b>MERCATO FANTACALCIO CHIUSO</b> 🚨

📅 <b>Giornata di Serie A iniziata!</b>

⏰ Prima partita: <b>{first_match['datetime'].strftime('%d/%m alle %H:%M')}</b>
🏆 Partite programmate: <b>{total_matches}</b>

<b>📋 Calendario completo:</b>
{matches_text}
❌ <b>MERCATO CHIUSO</b> fino al termine
⏳ Riaprirà 3 ore dopo l'ultima partita

💡 <i>Ora si gioca! Forza la tua squadra! 🚀</i>"""
        
        return message
    
    def create_open_message(self, fixtures):
        """Crea messaggio apertura mercato"""
        last_match = fixtures[-1]
        
        message = f"""✅ <b>MERCATO FANTACALCIO APERTO</b> ✅

🎉 <b>Giornata di Serie A terminata!</b>

⏰ Ultima partita: <b>{last_match['datetime'].strftime('%d/%m alle %H:%M')}</b>
⚽ {last_match['home']} vs {last_match['away']}

🔓 <b>MERCATO UFFICIALMENTE APERTO</b>
💰 Via libera a tutti i trasferimenti!

📈 <i>Analizza le prestazioni e pianifica i prossimi acquisti</i>
🔄 <i>Il bot controllerà la prossima giornata automaticamente</i>"""
        
        return message
    
    def check_and_notify(self):
        """Controlla se inviare notifiche"""
        try:
            logger.info("🔍 Controllo stato mercato fantacalcio...")
            
            # Ottieni partite
            fixtures = self.get_current_matchday_fixtures()
            
            if not fixtures:
                logger.info("📅 Nessuna partita programmata per oggi/domani")
                return
            
            logger.info(f"⚽ Trovate {len(fixtures)} partite")
            
            # Controlla chiusura mercato
            should_close, close_key = self.should_close_market(fixtures)
            if should_close:
                message = self.create_close_message(fixtures)
                if self.send_message(message):
                    self.notification_state["last_close"] = close_key
                    logger.info("📩 Notifica CHIUSURA inviata")
            
            # Controlla apertura mercato
            should_open, open_key = self.should_open_market(fixtures) 
            if should_open:
                message = self.create_open_message(fixtures)
                if self.send_message(message):
                    self.notification_state["last_open"] = open_key
                    logger.info("📩 Notifica APERTURA inviata")
            
            if not should_close and not should_open:
                logger.info("⏳ Nessuna notifica necessaria al momento")
            
            # Aggiorna timestamp ultimo controllo
            self.notification_state["last_check"] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"❌ Errore nel controllo: {e}")
    
    def send_startup_message(self):
        """Invia messaggio di avvio"""
        message = """🤖 <b>Bot Fantacalcio Attivato!</b>

✅ Connessione Telegram OK
⚽ Monitoraggio Serie A attivo  
🔄 Controlli automatici ogni 30 minuti

📋 <b>Cosa farò:</b>
• 🚨 Avviso chiusura mercato (2h prima)
• ✅ Avviso apertura mercato (3h dopo)
• 📊 Calendario partite complete

🎯 <i>Il tuo assistente fantacalcio è pronto!</i>"""
        
        return self.send_message(message)
    
    def run_continuous(self):
        """Esegue il bot in modalità continua per Render"""
        logger.info("🚀 Avvio bot in modalità continua...")
        
        # Messaggio di avvio
        if self.send_startup_message():
            logger.info("✅ Messaggio di avvio inviato")
        
        # Programma controlli ogni 30 minuti
        schedule.every(30).minutes.do(self.check_and_notify)
        
        # Primo controllo immediato
        self.check_and_notify()
        
        # Loop principale
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Controlla ogni minuto
                
                # Heartbeat ogni ora
                if datetime.now().minute == 0:
                    logger.info("💓 Bot attivo e in ascolto...")
                
            except KeyboardInterrupt:
                logger.info("⛔ Bot fermato dall'utente")
                break
            except Exception as e:
                logger.error(f"❌ Errore nel loop principale: {e}")
                time.sleep(300)  # Attesa 5 minuti in caso di errore

def main():
    """Funzione principale"""
    try:
        # Controlla variabili d'ambiente
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not bot_token:
            print("❌ ERRORE: Variabile TELEGRAM_BOT_TOKEN mancante")
            print("   Aggiungila nelle Environment Variables di Render")
            return
            
        if not chat_id:
            print("❌ ERRORE: Variabile TELEGRAM_CHAT_ID mancante") 
            print("   Aggiungila nelle Environment Variables di Render")
            return
        
        print("🤖 Inizializzazione Bot Fantacalcio...")
        print(f"📱 Token: ...{bot_token[-10:]}")
        print(f"💬 Chat ID: {chat_id}")
        
        # Crea e avvia il bot
        bot = RenderFantacalcioBot()
        bot.run_continuous()
        
    except Exception as e:
        print(f"❌ ERRORE CRITICO: {e}")
        return 1

if __name__ == "__main__":
    main()
