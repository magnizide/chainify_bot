#!/usr/bin/env python
# pylint: disable=unused-argument, wrong-import-position
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import os, requests, re
import helpers
from  dotenv import load_dotenv
from bson import json_util

from telegram import  Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
API_BASE_URI = os.getenv('API_BASE_URI')
CADENA_TEMPLATE = '''<b>Titulo</b>: {titulo}
<b>id</b>: {id}
<b>slug</b>: {slug}
<b>autor</b>: {autor_nombre}
<b>fecha_inicio</b>: {fecha_inicio}
<b>fecha_fin</b>: {fecha_fin}
<b>dias_aviso</b>: {dia_aviso}
<b>mensaje</b>: {mensaje}
<b>participantes</b>:
'''

ELECCION_CADENA, GUARDAR_VALOR_CADENA = range(2)
ELECCION_PARTICIPANTE, GUARDAR_VALOR_PARTICIPANTE, RETRY = range(2, 5) 
SUBMIT, SHOW_DATA = range(5, 7) 

opciones_teclado_cadena = [
    ['Titulo', 'Mensaje de notificación'],
    ['Fecha de inicio', 'Fecha de fin'],
    ['dias de aviso', 'Periodicidad'],
    ['Participantes'],
    ['Ver Info'],
    ['Listo']
]

opciones_teclado_participantes = [
    ['Nombre'],
    ['Puesto'],
    ['Numero']
]

markup_cadena = ReplyKeyboardMarkup(opciones_teclado_cadena, one_time_keyboard=True)
markup_participante = ReplyKeyboardMarkup(opciones_teclado_participantes, one_time_keyboard=True)

participante_dict = {}
participantes_list = []

# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hola {user.mention_html()}! usa este bot para crear y administrar tus cadenas."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")

async def get_my_cadenas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    api_response = requests.get(f"{API_BASE_URI}/cadenas/autor/{user_id}")
    messge_template = '''<b><u>{titulo}</u></b> 🔗:\n\t\t id: {id}\n\t\t slug: {slug}\n'''
    final_message = ''
    
    if api_response.status_code != 200:
        await update.message.reply_text('There has been an error on the api response')
        return None
    
    json_res = api_response.json()        
    computable_response = json_util.loads(json_util.dumps(json_res))

    for i in computable_response:
        final_message += messge_template.format(id= str(i['_id']), slug = i['slug'], titulo= i['titulo'])
        # print(final_message)
    
    await update.message.reply_html(final_message)

async def get_cadena(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_msg = '''⚠️ <b>El comando ver_cadena requiere un id o slug</b>\nEjemplo:
            - /ver_cadena id=1234567890abcdefghjklm
            - /ver_cadena slug=mi_cadena_ab12'''
    regex = r'^(id|slug)?=\=*'
    reply_msg = ''

    if  len(context.args) != 1 or not re.match(regex, context.args[0]):
        await update.message.reply_html(help_msg)
        return None
    
    identifier = dict([context.args[0].split('=')])
    api_response = requests.get(f"{API_BASE_URI}/cadenas/{identifier.get('slug') or identifier.get('id')}") 
    computable_response = json_util.loads(json_util.dumps(api_response.json()))

    if 'error' in computable_response:
        reply_msg = computable_response["error"].replace("_", "\_")
    else:
        reply_msg = CADENA_TEMPLATE.format(
            id=str(computable_response.get('_id')),
            slug=computable_response.get('slug'),
            titulo=computable_response.get('titulo'),
            autor_nombre=computable_response['autor']['nombre'],
            fecha_inicio=str(computable_response['fecha_inicio'].date()),
            fecha_fin=str(computable_response['fecha_fin'].date()),
            dia_aviso=computable_response['dia_aviso'],
            mensaje=computable_response['mensaje']
        )

        for p in computable_response['participantes']:
            reply_msg += '- <b>{nombre}</b>\n\t\tpuesto: {puesto}\n\t\tnumero: {numero}\n'.format(nombre=p['nombre'], puesto=p['puesto'], numero=p['numero'])
        
    await update.message.reply_html(reply_msg)

async def create_cadena(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_html("Para crear una cadena por favor diligenciar cada una de las siguientes opciones.", reply_markup=markup_cadena)
    return ELECCION_CADENA

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global participantes_list
    user_data = context.user_data
    await update.message.reply_text(
        "La creación de cadena ha sido cancelada.", reply_markup=ReplyKeyboardRemove()
    )
    user_data.clear()
    participante_dict.clear()
    participantes_list = []

    return ConversationHandler.END

async def guardar_eleccion_cadena(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data["choice"] = text
    await update.message.reply_text(f"Provee un valor para {text}.")
    print(context.user_data)

    return GUARDAR_VALOR_CADENA

async def guardar_valor_cadena(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    text = update.message.text
    category = user_data["choice"]
    user_data[category] = text
    del user_data["choice"]

    await update.message.reply_text(
        "Perfecto, estos son los valores que he guardado:"
        f"{helpers.facts_to_str(user_data)}Puedes actualizar un valor o continuar con los demás",
        reply_markup=markup_cadena,
    )
    return ELECCION_CADENA

async def create_participante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_html("Para crear un participante por favor diligenciar cada una de las siguientes opciones.", reply_markup=markup_participante)
    return ELECCION_PARTICIPANTE

async def guardar_eleccion_participante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data["eleccion_participante"] = text
    participante_dict[text] = None
    print(context.user_data, participante_dict)

    await update.message.reply_html("Voy a guardar eleccion participante", reply_markup=ReplyKeyboardRemove())

    print('Voy a guardar eleccion participante')
    return GUARDAR_VALOR_PARTICIPANTE

async def guardar_valor_participante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print(update.message.text)
    user_data = context.user_data
    text = update.message.text
    category = user_data["eleccion_participante"]
    participante_dict[category] = text
    del user_data["eleccion_participante"]

    if not set(['Nombre', 'Puesto', 'Numero']).issubset(participante_dict.keys()):
        diff_params = list(set(['Nombre', 'Puesto', 'Numero']).symmetric_difference(participante_dict.keys()))
        formatted_diff = ", ".join(diff_params)
        await update.message.reply_text(f'Por favor diligencia los campos: {formatted_diff}',reply_markup=markup_participante)
        return ELECCION_PARTICIPANTE
    
    await update.message.reply_text(
        "Perfecto, estos son los valores que he guardado:"
        f"{participante_dict}.",
    )
    retry_options = [
        ['Si'],
        ['No']
    ]
    retry_markup = ReplyKeyboardMarkup(retry_options)
    await update.message.reply_html("¿Quieres crear otro participante?", reply_markup=retry_markup)
    participantes_list.append(participante_dict.copy())
    print(participantes_list)
    participante_dict.clear()    
    return RETRY

async def retry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message.text.lower()
    if message == 'si':
        await update.message.reply_html("vas a crear otro participante", reply_markup=markup_participante)
        return ELECCION_PARTICIPANTE

    context.user_data['participantes'] = participantes_list
    await update.message.reply_html("No vas a volver a crear otro participante", reply_markup=markup_cadena)
    return ConversationHandler.END

async def show_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print("Hola")
    await update.message.reply_html(f"Hola: {context.user_data}", reply_markup=markup_cadena)
    return ELECCION_CADENA

async def submit_listo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return None

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # on non command i.e message - echo the message on Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mis_cadenas", get_my_cadenas))
    application.add_handler(CommandHandler("ver_cadena", get_cadena))

    participantes_conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex('^Participantes$'), create_participante
        )],
        states={
            ELECCION_PARTICIPANTE: [
                MessageHandler(
                    filters.Regex('^(Nombre|Numero|Puesto)$'), guardar_eleccion_participante)
                ],
            GUARDAR_VALOR_PARTICIPANTE: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^(Nombre|Numero|Puesto|Listo|Titulo|Mensaje de notificación|Fecha de inicio|Fecha de fin|dias de aviso|Periodicidad)$")), guardar_valor_participante 
                )
            ],
            RETRY: [
                MessageHandler(
                    filters.Regex('^(Si|No)$'), retry_handler)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    cadena_conv = ConversationHandler(
        entry_points=[
            CommandHandler('crear_cadena', create_cadena)
        ],
        states={
            ELECCION_CADENA: [
                MessageHandler(
                    filters.Regex('^(Titulo|Mensaje de notificación|Fecha de inicio|Fecha de fin|dias de aviso|Periodicidad)$'), guardar_eleccion_cadena,
                ),
                MessageHandler(
                    filters.Regex('^(Ver Info)$'), show_data,
                ),
                participantes_conv
                ],
            GUARDAR_VALOR_CADENA: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^(Nombre|Numero|Puesto|Listo|Titulo|Mensaje de notificación|Fecha de inicio|Fecha de fin|dias de aviso|Periodicidad)$")), guardar_valor_cadena
                )]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(cadena_conv)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()