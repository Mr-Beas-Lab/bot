import os
import json
import requests
import asyncio
import datetime
from telebot.async_telebot import AsyncTeleBot
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot import types
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
from message import get_welcome_messages
# Load environment variables
load_dotenv()

# Initialize Telegram Bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = AsyncTeleBot(BOT_TOKEN)

# Initialize Firebase
firebase_config = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {'storageBucket': "mrjohn-8ee8b.appspot.com"})
db = firestore.client()
bucket = storage.bucket()

# Function to generate main keyboard with language selection
def generate_main_keyboard(selected_language=None):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    languages = {
        "language_english": "🇬🇧 English",
        "language_chinese": "🇨🇳 Chinese",
        "language_spanish": "🇪🇸 Spanish"
    }

    buttons = []
    for callback_data, label in languages.items():
        if selected_language and callback_data.endswith(selected_language):
            label += " ✅"
        buttons.append(types.InlineKeyboardButton(label, callback_data=callback_data))

    keyboard.add(*buttons)
    keyboard.add(
        types.InlineKeyboardButton("📢 Join Channel", url="https://t.me/mrbeas_group"),
        types.InlineKeyboardButton("🚀 Launch App", web_app=types.WebAppInfo(url="https://mrb-theta.vercel.app"))
    )
    return keyboard

# Handle /start command
@bot.message_handler(commands=['start'])
async def start(message):
    user_id = str(message.from_user.id)
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # Handle profile photo upload
            photo = await bot.get_user_profile_photos(user_id, limit=1)
            user_image = None
            if photo.total_count > 0:
                file_id = photo.photos[0][-1].file_id
                file_info = await bot.get_file(file_id)
                file_path = file_info.file_path
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

                # Download the image
                response = requests.get(file_url)
                if response.status_code == 200:
                    # Upload the image to Firebase storage
                    blob = bucket.blob(f"user_{user_id}.jpg")
                    blob.upload_from_string(response.content, content_type="image/jpeg")

                    # Generate signed URL for the image
                    user_image = blob.generate_signed_url(datetime.timedelta(days=365), method="GET")

            # Initialize user data without language selected yet
            user_data = {
                'firstName': message.from_user.first_name,
                'lastName': message.from_user.last_name,
                'username': message.from_user.username,
                'languageCode': None,
                'isPremium': message.from_user.is_premium,
                'referrals': {},
                'balance': 0,
                'daily': {'claimedTime': None, 'claimedDay': 0},
                'WalletAddress': None,
                'userImage': user_image
            }

            text = message.text.split()

            # Debugging to see the referral part
            print(f"Referral text: {text}")

            if len(text) > 1 and text[1].startswith('ref_'):
                referrer_id = text[1][4:]

                referrer_ref = db.collection('users').document(referrer_id)
                referrer_doc = referrer_ref.get()

                if referrer_doc.exists:
                    user_data['referredBy'] = referrer_id
                    referrer_data = referrer_doc.to_dict()
                    bonus_amount = 500 if message.from_user.is_premium else 100
                    current_balance = referrer_data.get('balance', 0)
                    new_balance = current_balance + bonus_amount

                    referrals = referrer_data.get('referrals', {})
                    referrals[user_id] = {
                        'addedValue': bonus_amount,
                        'firstName': message.from_user.first_name,
                        'lastName': message.from_user.last_name,
                        'userImage': user_image
                    }

                    referrer_ref.update({
                        'balance': new_balance,
                        'referrals': referrals
                    })
                else:
                    user_data['referredBy'] = None

            user_ref.set(user_data)

        welcome_message = f"Hello {message.from_user.first_name}! 👋\n\nWelcome to Mr. John.\nHere you can earn coins!\nInvite friends to earn more coins together, and level up faster! 🧨"
        keyboard = generate_main_keyboard()
        await bot.reply_to(message, welcome_message, reply_markup=keyboard)

    except Exception as e:
        error_message = "Error. Please try again!"
        await bot.send_message(message.chat.id, error_message)
        print(f"Error occurred: {str(e)}")


# Handle language selection callback
@bot.callback_query_handler(func=lambda call: call.data.startswith('language_'))
async def language_selection(call):
    user_id = str(call.from_user.id)
    selected_language = call.data.split('_')[1]

    user_ref = db.collection('users').document(user_id)
    user_ref.update({'languageCode': selected_language})

    messages = {
        'english': f"Hello {call.from_user.first_name}! 👋\n\nWelcome to Mr. John.\nHere you can earn coins!\nInvite friends to earn more coins together, and level up faster! 🧨",
        'chinese': f"你好 {call.from_user.first_name}！👋\n\n欢迎来到Mr. John。\n在这里你可以赚取硬币！\n邀请朋友一起赚取更多硬币，快速升级！🧨",
        'spanish': f"¡Hola {call.from_user.first_name}! 👋\n\nBienvenido a Mr. John.\n¡Aquí puedes ganar monedas!\nInvita amigos para ganar más monedas juntos y subir de nivel más rápido! 🧨"
    }

    welcome_message = messages.get(selected_language, messages['english'])
    keyboard = generate_main_keyboard(selected_language)
    await bot.edit_message_text(welcome_message, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)


# Handle language selection callback
@bot.callback_query_handler(func=lambda call: call.data.startswith('language_'))
async def language_selection(call):
    user_id = str(call.from_user.id)
    selected_language = call.data.split('_')[1]

    user_ref = db.collection('users').document(user_id)
    user_ref.update({'languageCode': selected_language})

    # Use the imported function to get the welcome messages
    welcome_messages = get_welcome_messages(call.from_user.first_name)

    welcome_message = welcome_messages.get(selected_language, welcome_messages['english'])
    keyboard = generate_main_keyboard(selected_language)
    await bot.edit_message_text(welcome_message, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)


# HTTP Server to handle updates from Telegram Webhook
class Handler(BaseHTTPRequestHandler):
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

 