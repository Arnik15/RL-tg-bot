import logging
import re
import paramiko
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# === 1. ЗАГРУЗКА КОНФИГУРАЦИИ ===
load_dotenv()

TOKEN = os.getenv("TOKEN")
RM_HOST = os.getenv("RM_HOST", "localhost")
RM_PORT = int(os.getenv("RM_PORT", 22))
RM_USER = os.getenv("RM_USER", "user")
RM_PASSWORD = os.getenv("RM_PASSWORD", "password")

# === 2. НАСТРОЙКА ЛОГГИРОВАНИЯ ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log"
)
logger = logging.getLogger(__name__)

# === 3. СОСТОЯНИЯ ДЛЯ ДИАЛОГОВ ===
ENTERING_TEXT = 1
APT_CHOICE = 2  # Добавляем состояние для выбора
APT_SEARCH = 3  # Состояние поиска пакета

# === 4. РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ ===
EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
PHONE_PATTERN =  r"([\+7|8]-[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})"
PASSWORD_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()])[A-Za-z\d!@#$%^&*()]{8,}$"


# === 5. SSH ФУНКЦИИ ===
def ssh_execute(command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(RM_HOST, RM_PORT, RM_USER, RM_PASSWORD, timeout=10)

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8', errors='ignore')
        errors = stderr.read().decode('utf-8', errors='ignore')

        ssh.close()

        return output if output else errors or "Команда выполнена"
    except Exception as e:
        return f"Ошибка SSH: {str(e)}"


# === 6. ФУНКЦИИ ПОИСКА ===
def find_emails(text):
    return re.findall(EMAIL_PATTERN, text)


def find_phones(text):
    phones = re.findall(PHONE_PATTERN, text)
    # Нормализуем формат
    normalized = []
    for phone in phones:
        phone = re.sub(r'\D', '', phone)  # Оставляем только цифры
        phone = '+7' + phone[1:]
        normalized.append(phone)
    return normalized


def check_password(password):
    if re.match(PASSWORD_PATTERN, password):
        return "✅ Пароль сложный"
    else:
        return "❌ Пароль простой"


# === 7. ОБРАБОТЧИКИ КОМАНД ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    commands = [
        "/find_email - Найти email в тексте",
        "/find_phone_number - Найти телефоны в тексте",
        "/verify_password - Проверить сложность пароля",
        "/get_release - Информация о релизе ОС",
        "/get_uname - Информация о системе",
        "/get_uptime - Время работы системы",
        "/get_df - Состояние дисков",
        "/get_free - Состояние памяти",
        "/get_mpstat - Загрузка CPU",
        "/get_w - Активные пользователи",
        "/get_auths - Последние входы",
        "/get_critical - Критические события",
        "/get_ps - Запущенные процессы",
        "/get_ss - Используемые порты",
        "/get_apt_list - Установленные пакеты",
        "/get_services - Запущенные сервисы",
        "/help - Список команд"
    ]

    await update.message.reply_text(
        "🤖 Бот для практического задания\n\n" +
        "\n".join(commands)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /help"""
    await start(update, context)


# === 8. ОБРАБОТЧИКИ ПОИСКА ===
async def find_email_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ЗАПОМИНАЕМ КОМАНДУ
    context.user_data['last_command'] = '/find_email'
    await update.message.reply_text("Отправьте текст для поиска email:")
    return ENTERING_TEXT


async def find_phone_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_command'] = '/find_phone_number'
    await update.message.reply_text("Отправьте текст для поиска номеров телефонов:")
    return ENTERING_TEXT


async def verify_password_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_command'] = '/verify_password'
    await update.message.reply_text("Отправьте пароль для проверки сложности:")
    return ENTERING_TEXT


async def process_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # ПОЛУЧАЕМ КОМАНДУ ИЗ ПАМЯТИ
    command = context.user_data.get('last_command', '')
    logger.info(f"Обработка команды: {command}, текст: {text[:50]}...")

    if command == '/find_email':
        emails = find_emails(text)
        if emails:
            response = "Найдены email:\n" + "\n".join(emails[:20])  # Ограничиваем вывод
            if len(emails) > 20:
                response += f"\n... и ещё {len(emails) - 20} email"
        else:
            response = "Email не найдены"

    elif command == '/find_phone_number':
        phones = find_phones(text)
        if phones:
            response = "Найдены телефоны:\n" + "\n".join(phones[:20])
            if len(phones) > 20:
                response += f"\n... и ещё {len(phones) - 20} номеров"
        else:
            response = "Телефоны не найдены"

    elif command == '/verify_password':
        response = check_password(text)

    else:
        response = f"Неизвестная команда: {command}"

    # ОЧИЩАЕМ ПАМЯТЬ О КОМАНДЕ
    if 'last_command' in context.user_data:
        del context.user_data['last_command']

    await update.message.reply_text(response)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    # ОЧИЩАЕМ ПАМЯТЬ
    if 'last_command' in context.user_data:
        del context.user_data['last_command']
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END


# === 9. SSH КОМАНДЫ ===
async def get_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("cat /etc/os-release || cat /etc/*-release || lsb_release -a")
    await update.message.reply_text(f"```\n{result[:3000]}\n```", parse_mode="Markdown")


async def get_uname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("uname -a")
    await update.message.reply_text(f"```\n{result}\n```", parse_mode="Markdown")


async def get_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("uptime -p")
    await update.message.reply_text(f"⏱ Время работы: {result}")


async def get_df(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("df -h")
    await update.message.reply_text(f"```\n{result[:3000]}\n```", parse_mode="Markdown")


async def get_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("free -h")
    await update.message.reply_text(f"```\n{result}\n```", parse_mode="Markdown")


async def get_mpstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("mpstat || echo 'Установите sysstat: sudo apt install sysstat'")
    await update.message.reply_text(f"```\n{result[:2000]}\n```", parse_mode="Markdown")


async def get_w(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("w")
    await update.message.reply_text(f"```\n{result[:2000]}\n```", parse_mode="Markdown")


async def get_auths(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("last -n 10")
    await update.message.reply_text(f"```\n{result[:2000]}\n```", parse_mode="Markdown")


async def get_critical(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute(
        "journalctl -p crit -n 5 2>/dev/null || tail -n 5 /var/log/syslog 2>/dev/null || echo 'Логи недоступны'")
    await update.message.reply_text(f"```\n{result[:2000]}\n```", parse_mode="Markdown")


async def get_ps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("ps aux --sort=-%cpu | head -20")
    await update.message.reply_text(f"```\n{result[:3000]}\n```", parse_mode="Markdown")


async def get_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute("ss -tuln")
    await update.message.reply_text(f"```\n{result[:3000]}\n```", parse_mode="Markdown")


async def get_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ssh_execute(
        "systemctl list-units --type=service --state=running 2>/dev/null || service --status-all 2>/dev/null || echo 'Не удалось получить список сервисов'")
    await update.message.reply_text(f"```\n{result[:3000]}\n```", parse_mode="Markdown")


# === 10. ИСПРАВЛЕННЫЙ ОБРАБОТЧИК ДЛЯ ПАКЕТОВ ===
async def get_apt_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Все пакеты", "Поиск пакета"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )
    return APT_CHOICE


async def handle_apt_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text

    if choice == "Все пакеты":
        result = ssh_execute("dpkg -l | head -30")
        await update.message.reply_text(
            f"Первые 30 пакетов:\n```\n{result}\n```",
            parse_mode="Markdown",
            reply_markup=None
        )
        return ConversationHandler.END

    elif choice == "Поиск пакета":
        await update.message.reply_text(
            "Введите имя пакета для поиска:",
            reply_markup=None
        )
        return APT_SEARCH


async def handle_apt_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    package = update.message.text
    result = ssh_execute(f"dpkg -l | grep -i '{package}' | head -20")

    await update.message.reply_text(
        f"Результаты поиска '{package}':\n```\n{result or 'Пакет не найден'}\n```",
        parse_mode="Markdown",
        reply_markup=None
    )
    return ConversationHandler.END


# === 11. ГЛАВНАЯ ФУНКЦИЯ ===
def main():
    """Запуск бота"""

    # Создаём приложение
    app = Application.builder().token(TOKEN).build()

    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # ConversationHandler для поиска email
    email_conv = ConversationHandler(
        entry_points=[CommandHandler("find_email", find_email_start)],
        states={
            ENTERING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ConversationHandler для поиска телефонов
    phone_conv = ConversationHandler(
        entry_points=[CommandHandler("find_phone_number", find_phone_start)],
        states={
            ENTERING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ConversationHandler для проверки пароля
    password_conv = ConversationHandler(
        entry_points=[CommandHandler("verify_password", verify_password_start)],
        states={
            ENTERING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ConversationHandler для пакетов
    apt_conv = ConversationHandler(
        entry_points=[CommandHandler("get_apt_list", get_apt_list)],
        states={
            APT_CHOICE: [  # Состояние выбора кнопки
                MessageHandler(
                    filters.Regex(r'^(Все пакеты|Поиск пакета)$'),
                    handle_apt_choice
                )
            ],
            APT_SEARCH: [  # Состояние поиска
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_apt_search
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Добавляем все обработчики
    app.add_handler(email_conv)
    app.add_handler(phone_conv)
    app.add_handler(password_conv)
    app.add_handler(apt_conv)

    # SSH команды (простые обработчики)
    ssh_commands = [
        ("get_release", get_release),
        ("get_uname", get_uname),
        ("get_uptime", get_uptime),
        ("get_df", get_df),
        ("get_free", get_free),
        ("get_mpstat", get_mpstat),
        ("get_w", get_w),
        ("get_auths", get_auths),
        ("get_critical", get_critical),
        ("get_ps", get_ps),
        ("get_ss", get_ss),
        ("get_services", get_services),
    ]

    for cmd, handler in ssh_commands:
        app.add_handler(CommandHandler(cmd, handler))

    # Запускаем бота
    print("🤖 Бот запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()
