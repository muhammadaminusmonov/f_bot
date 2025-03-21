import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import filters, Updater, CommandHandler, MessageHandler, CallbackContext, ApplicationBuilder, CallbackQueryHandler


class DB:
    def __init__(self):
        self.conn = sqlite3.connect('school_bot.db')
        self.cursor = self.conn.cursor()

    def create_tables(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            telegram_username TEXT,
            telegram_user_id BIGINT UNIQUE NOT NULL,
            role BOOLEAN DEFAULT FALSE,
            join_datetime DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS not_replied_messages (
            message_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        ''')

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS state (
        user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
        state TEXT DEFAULT 'first_name');
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS send_messages (
        user_id BIGINT,
        message_id BIGINT
        );
        """)

    def tuple_to_dict(self, cursor, data):
        if data is None:
            return {}  # Return an empty dictionary instead of raising an error

        column_names = [col[0] for col in cursor.description]
        return {column_names[i]: value for i, value in enumerate(data)}


    def set_state(self, user_id, state):
        self.cursor.execute('SELECT * FROM state WHERE user_id=?', (user_id,))
        user = self.cursor.fetchone()
        
        if user:
            self.cursor.execute("UPDATE state SET state=? WHERE user_id=?", (state, user_id))
        else:
            self.cursor.execute("INSERT INTO state (user_id, state) VALUES (?, ?)", (user_id, state))
        
        self.conn.commit()


    def get_state(self, user_id):
        self.cursor.execute('SELECT * FROM state WHERE user_id=?', (user_id,))
        return self.tuple_to_dict(self.cursor, self.cursor.fetchone())  # Use the fixed tuple_to_dict


    def user(self, tg_user_id, tg_username=None, first_name=None, last_name=None):
        self.cursor.execute("SELECT * FROM users WHERE telegram_user_id = ?", (tg_user_id,))
        user_data = self.cursor.fetchone()  # Store fetchone() result

        if user_data is None:
            self.cursor.execute(
                "INSERT INTO users (telegram_user_id, telegram_username) VALUES (?, ?)", 
                (tg_user_id, tg_username)
            )
            self.conn.commit()
            self.set_state(tg_user_id, "first_name")
            return False

        # Convert the tuple data to a dictionary
        data = self.tuple_to_dict(self.cursor, user_data)

        # Check if first name or last name is missing and set the state accordingly
        if not data.get("first_name"):
            self.cursor.execute("UPDATE users SET first_name=? WHERE telegram_user_id=?", (first_name, tg_user_id))
            self.conn.commit()
            return False
        elif not data.get("last_name"):
            self.cursor.execute("UPDATE users SET last_name=? WHERE telegram_user_id=?", (last_name, tg_user_id))
            self.conn.commit()
            return False
        else:
            return True  # User is fully registered

    def get_role(self):
        self.cursor.execute("SELECT * FROM users WHERE role = 1")
        row = self.cursor.fetchone()
        return self.tuple_to_dict(self.cursor, row) if row else None

    def user_data(self, tg_user_id):
        self.cursor.execute("SELECT * FROM users WHERE telegram_user_id = ?", (tg_user_id,))
        return self.tuple_to_dict(self.cursor, self.cursor.fetchone())

    def get_user(self, tg_msg_id):
        self.cursor.execute("SELECT * FROM not_replied_messages WHERE message_id = ?", (tg_msg_id,))
        result = self.tuple_to_dict(self.cursor, self.cursor.fetchone())
        return result if result else None

    def save_message(self, user_id, message_id):
        self.cursor.execute(
            "INSERT INTO send_messages (user_id, message_id) VALUES (?, ?)", (user_id, message_id)
        )
        self.conn.commit()

    def get_message(self, user_id):
        self.cursor.execute("SELECT * FROM send_messages WHERE user_id = ?", (user_id,))
        return self.tuple_to_dict(self.cursor, self.cursor.fetchone())
    
    def delete_message(self, user_id):
        self.cursor.execute("DELETE FROM send_messages WHERE user_id = ?", (user_id,))
        self.conn.commit()

# db


TOKEN = "8161300329:AAHWZixXxhe-scOxITVihnH3_qsuYSVkLCU"
db = DB()
user_state = {}

def yes_no_menu(msg_id):
    menu = [
        [InlineKeyboardButton('Yes', callback_data=f'yes_{msg_id}')],
        [InlineKeyboardButton('No', callback_data=f'no_{msg_id}')]
    ]
    return menu


# main


async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    telegram_user_id = user.id
    telegram_username = user.username if user.username else "unknown"

    if db.user(telegram_user_id, telegram_username):
        await update.message.reply_text("Welcome back to our bot!")
    
    if db.get_state(telegram_user_id).get("state") == "first_name":
        await update.message.reply_text("Please enter your first name:")
    elif db.get_state(telegram_user_id).get("state") == "last_name":
        await update.message.reply_text("Please enter your last name:")
    elif db.get_state(telegram_user_id).get("state") == "registered":
        await update.message.reply_text("You have been successfully registered!")

        # Update role for the specific user
        if telegram_user_id == 1635572984:
            db.cursor.execute("UPDATE users SET role=1 WHERE telegram_user_id=?", (telegram_user_id,))
            db.conn.commit()

        # Fetch the role after committing changes
        role_data = db.get_role()
        role = role_data.get("telegram_user_id") if role_data else None  # Ensure it handles None

        # Ensure 'role' is correctly interpreted

        if role == user.id:  # Convert to int for safety
            await update.message.reply_text(
                "You can reply to any student message\n\nWith all good wishes your student Usmonov Muhammadamin",
            )
        else:
            await update.message.reply_text("Now, everything you write will be sent to the mentor with your confirmation before sending!")


async def msg_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    message_id = update.effective_message.message_id
    telegram_user_id = user.id
    telegram_username = user.username if user.username else "unknown"
    state = db.get_state(telegram_user_id).get("state")
    mentor = db.get_role()

    if state == "first_name":
        db.user(telegram_user_id, telegram_username, update.message.text)
        await update.message.reply_text("Please enter your last name:")
        db.set_state(telegram_user_id, "last_name")
    elif state == "last_name":
        db.user(telegram_user_id, telegram_username, last_name=update.message.text)
        db.set_state(telegram_user_id, "registered")
        await update.message.reply_text("You have been successfully registered!")
        await update.message.reply_text("Now, everything you write will be sent to the mentor with your confirmation before sending!")

    if mentor.get('telegram_user_id') != user.id and state == "registered":
        db.save_message(user.id, message_id)

        await update.message.reply_text("Are you sure you want to send this message?", reply_markup=InlineKeyboardMarkup(yes_no_menu(message_id)))
    

    elif mentor.get('telegram_user_id') == user.id and state == "registered":
    # Mentor is replying to a student
        replied_msg = update.message.reply_to_message  # Check if it's a reply

        if replied_msg:

            student_msg_id = replied_msg.message_id
            
            student_id = db.get_user(student_msg_id).get("user_id")
            
            if student_id:
                message = update.message

                if message.text:
                    await context.bot.send_message(chat_id=student_id, text=message.text)

                elif message.photo:
                    await context.bot.send_photo(chat_id=student_id, photo=message.photo[-1].file_id, caption=message.caption)

                elif message.video:
                    await context.bot.send_video(chat_id=student_id, video=message.video.file_id, caption=message.caption)

                elif message.audio:
                    await context.bot.send_audio(chat_id=student_id, audio=message.audio.file_id, caption=message.caption)

                elif message.voice:
                    await context.bot.send_voice(chat_id=student_id, voice=message.voice.file_id, caption=message.caption)

                elif message.document:
                    await context.bot.send_document(chat_id=student_id, document=message.document.file_id, caption=message.caption)

                elif message.animation:
                    await context.bot.send_animation(chat_id=student_id, animation=message.animation.file_id, caption=message.caption)

                elif message.location:
                    await context.bot.send_location(chat_id=student_id, latitude=message.location.latitude, longitude=message.location.longitude)

                elif message.sticker:
                    await context.bot.send_sticker(chat_id=student_id, sticker=message.sticker.file_id)

                else:
                    await context.bot.send_message(chat_id=student_id, text="⚠️ Unsupported message type.")

            
                db.cursor.execute("DELETE FROM not_replied_messages WHERE message_id = ?", (replied_msg.message_id,))
                db.conn.commit()

            else:
                await update.message.reply_text("Error: Could not find the original student message.")



async def callback_query_handler(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    data = update.callback_query.data.split('_')
    chat_id = update.callback_query.message.chat_id
    msg_id = int(data[1])
    mentor = db.get_role()  # Assuming this gets the mentor's info

    # 🔹 Get sender's full name
    user_data = db.user_data(user.id)  # Fetch user details from DB
    first_name = user_data.get("first_name", "Unknown")
    last_name = user_data.get("last_name", "Unknown")

    # 🔹 Check message type
    message = db.get_message(user.id)
    caption = f"📩 Message from {f"{first_name} {last_name}"}:\n\n"  # Common caption format


    if data[0] == "yes":
        await update.callback_query.message.delete()
        await context.bot.send_message(chat_id=mentor['telegram_user_id'], text=caption) 
        forwarded_message =  await context.bot.forward_message(chat_id=mentor['telegram_user_id'], from_chat_id=chat_id, message_id=message.get("message_id"))

        db.cursor.execute("INSERT INTO not_replied_messages (message_id, user_id) VALUES (?, ?)", (forwarded_message.message_id, user.id))
        db.conn.commit()
        await update.callback_query.message.reply_text("Your message has been sent!")

    elif data[0] == "no":
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        await update.callback_query.message.delete()
        await update.callback_query.message.reply_text("Your message send canceled!")
    
    db.delete_message(user.id)


def main():
    db.create_tables()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, msg_handler))  # Handle user messages
    app.add_handler(CallbackQueryHandler(callback_query_handler))  # Handle callback queries

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()