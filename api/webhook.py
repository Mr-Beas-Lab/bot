from http.server import BaseHTTPRequestHandler
import os
import json
import asyncio
from telebot.async_telebot import AsyncTeleBot  
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

# Initialize bot
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = AsyncTeleBot(BOT_TOKEN)

# Initialize Firebase
firebase_config = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT'))
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {'storageBucket': "mrjohn-8ee8b.appspot.com"})
db = firestore.client()
bucket = storage.bucket()

# Generate language selection keyboard
def generate_language_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("English", callback_data="lang_english"))
    keyboard.add(InlineKeyboardButton("Chinese", callback_data="lang_chinese"))
    keyboard.add(InlineKeyboardButton("Spanish", callback_data="lang_spanish"))
    return keyboard

def generate_start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Open Web App", web_app=WebAppInfo(url="https://mrb-crypto.vercel.app")))
    return keyboard

@bot.message_handler(commands=['start'])  
async def start(message):
    user_id = str(message.from_user.id)  
    user_first_name = str(message.from_user.first_name)  
    user_last_name = message.from_user.last_name
    user_username = message.from_user.username
    user_language_code = str(message.from_user.language_code)
    is_premium = message.from_user.is_premium
    text = message.text.split()
  
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # Prepare user data
            user_data = {
                'userImage': None,
                'firstName': user_first_name,
                'lastName': user_last_name,
                'username': user_username,
                'languageCode': user_language_code,
                'isPremium': is_premium,
                'balance': 0,
                'daily': {
                    'claimedTime': None,
                    'claimedDay': 0
                },
                'WalletAddress': None,
            }

            if len(text) > 1 and text[1].startswith('ref_'):   
                referrer_id = text[1][4:]
                referrer_ref = db.collection('users').document(referrer_id)
                referrer_doc = referrer_ref.get()

                if referrer_doc.exists:
                    user_data['referredBy'] = referrer_id
                    referrer_data = referrer_doc.to_dict()
                    bonus_amount = 500 if is_premium else 100
                    current_balance = referrer_data.get('balance', 0)
                    new_balance = current_balance + bonus_amount

                    referrals = referrer_data.get('referrals', {})
                    if referrals is None:
                        referrals = {}
                    referrals[user_id] = {
                        'addedValue': bonus_amount,
                        'firstName': user_first_name,
                        'lastName': user_last_name,
                        'userImage': None,
                    }  

                    referrer_ref.update({
                        'balance': new_balance,
                        'referrals': referrals
                    })
                else:
                    user_data['referredBy'] = None

            user_ref.set(user_data)

        await bot.reply_to(message, "Please select your language:", reply_markup=generate_language_keyboard())
    except Exception as e:
        error_message = "Error. Please try again!"
        await bot.reply_to(message, error_message)  
        print(f"Error occurred: {str(e)}")  

async def handle_language_selection(call):
    user_id = str(call.from_user.id)
    selected_language = call.data.split('_')[1]  # Extract language from callback data

    # Update user's language in Firestore
    user_ref = db.collection('users').document(user_id)
    user_ref.update({'language': selected_language})

    # Welcome message
    welcome_message = {
        'english': "Hello! 👋\n\nWelcome to Mr. John. Here you can earn coins!",
        'chinese': "你好！👋\n\n欢迎来到 Mr. John。在这里你可以赚取金币！",
        'spanish': "¡Hola! 👋\n\nBienvenido a Mr. John. ¡Aquí puedes ganar monedas!",
    }.get(selected_language, "Hello! 👋\n\nWelcome to Mr. John.")

    # Send the welcome message to the user
    await bot.send_message(user_id, welcome_message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
async def callback_language_selection(call):
    await handle_language_selection(call)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])  
        post_data = self.rfile.read(content_length)
        update_dict = json.loads(post_data.decode('utf-8'))

        asyncio.run(self.process_update(update_dict))

        self.send_response(200)
        self.end_headers()

    async def process_update(self, update_dict):
        update = types.Update.de_json(update_dict)
        await bot.process_new_updates([update])

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write('Hello, BOT is running!'.encode('utf-8'))
 