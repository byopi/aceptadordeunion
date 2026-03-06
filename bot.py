import logging
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
)

# ── Configuración ─────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "TU_TOKEN_AQUI")

CAPTCHA_TIMEOUT = 120  # Segundos para completar el captcha

# ── Mensajes ──────────────────────────────────────────────────────────────────

MSG_START = (
    "👋 ¡Bienvenido/a, {nombre}!\n\n"
    "Soy un bot que gestiona el acceso a tus canales y grupos mediante captcha.\n\n"
    "Escribe /help para ver el menú de opciones."
)

MSG_HELP = "📋 *Menú de opciones* — ¿Qué deseas hacer?"

MSG_CAPTCHA = (
    "👋 ¡Hola, {nombre}!\n\n"
    "Para unirte al grupo necesitas verificar que no eres un robot.\n\n"
    "Tienes *2 minutos* para presionar el botón:"
)
MSG_APROBADO  = "✅ ¡Verificación exitosa! Ya puedes acceder. Bienvenido/a, {nombre}."
MSG_TIMEOUT   = "⏰ Tu tiempo para completar el captcha expiró. Vuelve a solicitar la unión."

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_canales(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.bot_data.setdefault("canales", {})


def menu_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Agregar canal/grupo",  callback_data="menu:agregar")],
        [InlineKeyboardButton("🗑️ Eliminar canal/grupo", callback_data="menu:eliminar")],
        [InlineKeyboardButton("📋 Ver canales activos",  callback_data="menu:listar")],
        [InlineKeyboardButton("ℹ️ Cómo configurar",      callback_data="menu:ayuda")],
    ])

# ── Comandos ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nombre = update.effective_user.first_name
    await update.message.reply_text(MSG_START.format(nombre=nombre))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        MSG_HELP,
        parse_mode="Markdown",
        reply_markup=menu_principal(),
    )


async def cmd_agregar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra un canal: /agregar <chat_id>"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Uso correcto: `/agregar <chat_id>`\n\n"
            "Ejemplo: `/agregar -1001234567890`",
            parse_mode="Markdown",
        )
        return

    chat_id_str = context.args[0]

    try:
        chat = await context.bot.get_chat(int(chat_id_str))
    except Exception:
        await update.message.reply_text(
            "❌ No pude encontrar ese canal/grupo.\n"
            "Asegúrate de que el bot sea administrador y el chat_id sea correcto."
        )
        return

    canales = get_canales(context)
    canales[chat_id_str] = chat.title or chat_id_str

    await update.message.reply_text(
        f"✅ Canal *{chat.title}* registrado correctamente.\n\n"
        "A partir de ahora, los usuarios recibirán el captcha al solicitar unirse.",
        parse_mode="Markdown",
    )
    logger.info("Canal agregado: %s (%s)", chat.title, chat_id_str)

# ── Menú interactivo ──────────────────────────────────────────────────────────

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    accion = query.data.split(":")[1]

    if accion == "agregar":
        await query.edit_message_text(
            "➕ *Agregar canal o grupo*\n\n"
            "Para registrar un canal/grupo:\n\n"
            "1️⃣ Agrega este bot como *administrador* del canal o grupo\n"
            "2️⃣ Activa *'Aprobar nuevos miembros'* en los ajustes del grupo\n"
            "3️⃣ Envía el comando:\n\n"
            "`/agregar <chat_id>`\n\n"
            "📌 Para obtener el chat\\_id, reenvía un mensaje del grupo al bot "
            "@userinfobot o usa @RawDataBot.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Volver al menú", callback_data="menu:volver")]
            ]),
        )

    elif accion == "eliminar":
        canales = get_canales(context)
        if not canales:
            texto   = "⚠️ No tienes ningún canal registrado aún."
            botones = [[InlineKeyboardButton("🔙 Volver", callback_data="menu:volver")]]
        else:
            texto   = "🗑️ *Selecciona el canal que deseas eliminar:*"
            botones = [
                [InlineKeyboardButton(f"❌ {titulo}", callback_data=f"del:{cid}")]
                for cid, titulo in canales.items()
            ]
            botones.append([InlineKeyboardButton("🔙 Volver", callback_data="menu:volver")])

        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botones),
        )

    elif accion == "listar":
        canales = get_canales(context)
        if not canales:
            texto = "📋 *Canales activos*\n\nNo hay ningún canal registrado todavía."
        else:
            lista = "\n".join(f"• {titulo} (`{cid}`)" for cid, titulo in canales.items())
            texto = f"📋 *Canales activos ({len(canales)}):*\n\n{lista}"

        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Volver al menú", callback_data="menu:volver")]
            ]),
        )

    elif accion == "ayuda":
        await query.edit_message_text(
            "ℹ️ *¿Cómo funciona el captcha?*\n\n"
            "1. Un usuario solicita unirse a tu canal/grupo\n"
            "2. El bot le envía un mensaje privado con el botón *'No soy un robot'*\n"
            "3. Si lo presiona en *2 minutos* → se aprueba su entrada ✅\n"
            "4. Si no responde a tiempo → se rechaza automáticamente ❌\n\n"
            "⚠️ *Requisitos:*\n"
            "• El bot debe ser *administrador* del canal\n"
            "• El usuario debe haber iniciado el bot al menos una vez\n"
            "• Debe estar activo *'Aprobar nuevos miembros'* en el grupo",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Volver al menú", callback_data="menu:volver")]
            ]),
        )

    elif accion == "volver":
        await query.edit_message_text(
            MSG_HELP,
            parse_mode="Markdown",
            reply_markup=menu_principal(),
        )


async def handle_eliminar_canal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id_str = query.data.split(":")[1]
    canales = get_canales(context)
    titulo  = canales.pop(chat_id_str, "Canal desconocido")

    await query.edit_message_text(
        f"✅ Canal *{titulo}* eliminado correctamente.\n\n"
        "Los usuarios ya no recibirán captcha para ese canal.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="menu:volver")]
        ]),
    )

# ── Captcha ────────────────────────────────────────────────────────────────────

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    join_request = update.chat_join_request
    user = join_request.from_user
    chat = join_request.chat
    chat_id_str = str(chat.id)

    canales = get_canales(context)
    if chat_id_str not in canales:
        return

    logger.info("Solicitud: %s (id=%s) → %s", user.full_name, user.id, chat.title)

    callback_data = f"captcha:{chat.id}:{user.id}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 No soy un robot", callback_data=callback_data)]
    ])

    try:
        msg = await context.bot.send_message(
            chat_id=user.id,
            text=MSG_CAPTCHA.format(nombre=user.first_name),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

        context.job_queue.run_once(
            expire_captcha,
            when=CAPTCHA_TIMEOUT,
            data={
                "user_id": user.id,
                "chat_id": chat.id,
                "msg_id":  msg.message_id,
                "nombre":  user.first_name,
            },
            name=f"expire:{chat.id}:{user.id}",
        )

    except Exception as e:
        logger.warning("No se pudo enviar captcha a %s: %s", user.id, e)


async def handle_captcha_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    _, chat_id_str, user_id_str = query.data.split(":")
    chat_id = int(chat_id_str)
    user_id = int(user_id_str)

    if query.from_user.id != user_id:
        await query.answer("⚠️ Este captcha no es para ti.", show_alert=True)
        return

    nombre = query.from_user.first_name

    try:
        await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
        logger.info("Aprobado: %s (id=%s)", nombre, user_id)

        for job in context.job_queue.get_jobs_by_name(f"expire:{chat_id}:{user_id}"):
            job.schedule_removal()

        await query.edit_message_text(MSG_APROBADO.format(nombre=nombre))

    except Exception as e:
        logger.error("Error al aprobar %s: %s", user_id, e)
        await query.edit_message_text("❌ Ocurrió un error. Intenta de nuevo más tarde.")


async def expire_captcha(context: ContextTypes.DEFAULT_TYPE) -> None:
    data    = context.job.data
    user_id = data["user_id"]
    chat_id = data["chat_id"]
    msg_id  = data["msg_id"]

    logger.info("Captcha expirado: user_id=%s", user_id)

    try:
        await context.bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=msg_id,
            text=MSG_TIMEOUT,
        )
    except Exception as e:
        logger.warning("Error al expirar captcha: %s", e)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("agregar", cmd_agregar))

    app.add_handler(CallbackQueryHandler(handle_menu,           pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(handle_eliminar_canal, pattern=r"^del:"))

    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(CallbackQueryHandler(handle_captcha_response, pattern=r"^captcha:"))

    logger.info("Bot iniciado. Esperando eventos...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()
