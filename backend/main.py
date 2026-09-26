from telegram_bot import create_bot

def main():
    print("HireMatch AI Telegram Bot is running...")
    app = create_bot()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
