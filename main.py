import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Environment variable TELEGRAM_BOT_TOKEN is missing")
if not GROQ_API_KEY:
    raise RuntimeError("Environment variable GROQ_API_KEY is missing")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
ai = Groq(api_key=GROQ_API_KEY)

# In-memory history: last 4 user/assistant exchanges per Telegram user.
# Note: this history resets whenever the hosting process restarts.
history = {}

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "Ты дружелюбный ИИ-помощник. Отвечай по-русски, понятно и по делу. "
        "Если не знаешь ответа, честно скажи об этом."
    ),
}


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! Я ИИ-бот Q 🤖\n"
        "Задай мне вопрос. Я могу учитывать предыдущие сообщения.\n"
        "/clear — очистить историю диалога."
    )


@dp.message(Command("clear"))
async def clear(message: Message):
    history.pop(message.from_user.id, None)
    await message.answer("История диалога очищена!")


@dp.message()
async def chat(message: Message):
    if not message.text:
        await message.answer("Пока я умею отвечать только на текстовые сообщения.")
        return

    user_id = message.from_user.id
    previous = history.get(user_id, [])
    user_message = {"role": "user", "content": message.text}

    try:
        response = await asyncio.to_thread(
            ai.chat.completions.create,
            model="openai/gpt-oss-20b",
            messages=[SYSTEM_MESSAGE] + previous[-8:] + [user_message],
            max_completion_tokens=500,
        )
        answer = response.choices[0].message.content
        if not answer:
            answer = "Не получилось сформировать ответ. Попробуй ещё раз."

        history[user_id] = (
            previous + [
                user_message,
                {"role": "assistant", "content": answer},
            ]
        )[-8:]

        for start_index in range(0, len(answer), 4000):
            await message.answer(answer[start_index:start_index + 4000])

    except Exception:
        logger.exception("Failed to process a message")
        await message.answer(
            "Не удалось получить ответ от нейросети. Попробуй ещё раз позже."
        )


async def main():
    logger.info("Starting Telegram bot Q")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
