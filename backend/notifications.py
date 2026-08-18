"""
Karyawan AI — Notifications Module
Modul untuk mengirimkan notifikasi ke user via WhatsApp atau Telegram.
"""
import os
import requests
import json
from config import settings

def send_whatsapp_notification(message: str) -> bool:
    """
    Mengirim notifikasi WhatsApp menggunakan API Fonnte (atau API generic sejenis).
    Pastikan WA_API_TOKEN sudah diset di .env.
    """
    wa_token = os.getenv("WA_API_TOKEN")
    wa_target = os.getenv("WA_TARGET_NUMBER") # Nomor tujuan
    
    if not wa_token or not wa_target:
        print("INFO: WA_API_TOKEN atau WA_TARGET_NUMBER tidak di-set. Notifikasi WA dilewati.")
        return False
        
    try:
        # Menggunakan Fonnte API sebagai default
        url = "https://api.fonnte.com/send"
        headers = {
            'Authorization': wa_token
        }
        data = {
            'target': wa_target,
            'message': message,
            'countryCode': '62'
        }
        
        response = requests.post(url, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            print(f"Notifikasi WA berhasil dikirim ke {wa_target}")
            return True
        else:
            print(f"Gagal kirim WA: {response.text}")
            return False
    except Exception as e:
        print(f"Error kirim WA: {e}")
        return False

def send_telegram_notification(message: str) -> bool:
    """
    Mengirim notifikasi Telegram menggunakan Telegram Bot API.
    Pastikan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID diset di .env.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        return False
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error kirim Telegram: {e}")
        return False

def send_notification(title: str, message: str):
    """
    Fungsi utama untuk mengirim notifikasi ke semua channel yang tersedia.
    """
    full_message = f"🤖 *Karyawan AI Alert*\n\n*{title}*\n{message}"
    
    # Coba WA dulu
    wa_sent = send_whatsapp_notification(full_message)
    
    # Coba Telegram (bisa keduanya kalau di-set)
    send_telegram_notification(full_message)
    
    return True
