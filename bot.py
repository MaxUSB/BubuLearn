import os
import json
import requests
from telebot import TeleBot, types
from bubu_module import ICSParser, BubuLearn


def start_bot():
    config = json.loads(open('config.json', "r").read())
    output_file_name = 'calendar.ics'
    bot = TeleBot(config['bot_token'])

    def check_users(request):
        username = request.from_user.username
        if username in config['bot_allowed_users']:
            return True
        return False

    @bot.message_handler(commands=['start'])
    def send_welcome(request):
        if not check_users(request):
            return

        bot.send_message(
            request.from_user.id,
            text=f'Привет, {request.from_user.first_name}!\nОтправь мне свой файл с расписанием, и я всё выгружу в CRM! 😊'
        )

    @bot.message_handler(content_types=['document'])
    def get_file(request):
        if not check_users(request):
            return

        file_extension = request.document.file_name.split('.')[-1]
        if file_extension != 'ics':
            bot.send_message(request.from_user.id, f'❌ Формат файла .{file_extension} недопустим, необходимо загрузить .ics файл!')
            return
        file_info = bot.get_file(request.document.file_id)
        file = requests.get(f'https://api.telegram.org/file/bot{config["bot_token"]}/{file_info.file_path}')
        if file.status_code != 200:
            bot.send_message(request.from_user.id, f'❌ Не удалось получить файл!')
            return
        output_file = open(output_file_name, 'wb')
        output_file.write(file.content)
        output_file.close()

        keyboard = types.InlineKeyboardMarkup()
        key_yes = types.InlineKeyboardButton(text='😎 Текущую', callback_data='current')
        keyboard.add(key_yes)
        key_no = types.InlineKeyboardButton(text='⏪ Предыдущую', callback_data='last')
        keyboard.add(key_no)
        question = 'За какую неделю выгрузить данные?'

        bot.send_message(request.from_user.id, text=question, reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: True)
    def bubu_upload(request):
        if not check_users(request):
            return

        wait_message = bot.send_message(request.from_user.id, text=f'⌛️ Пожалуйста подождите...')

        bl = None
        failed_uploads = []
        try:
            ics_p = ICSParser(output_file_name)
            events = ics_p.get_events(is_current_week=True if request.data == 'current' else False)
            bl = BubuLearn(config)
            events = bl.drop_duplicates_events(events)
            for event in events:
                success = bl.add_event(event['phone'], event['date'])
                if not success:
                    failed_uploads.append(f"{event['date'].strftime('%d.%m.%Y %H:%M')} ☎️ {event['phone']}")
        except Exception as e:
            bot.send_message(request.from_user.id, f'❌ Ошибка: {e}')
            return
        finally:
            if bl is not None:
                bl.logout()
            if os.path.exists(output_file_name):
                os.remove(output_file_name)

        info_message = '✅ Все уроки удалось добавить!' if len(failed_uploads) == 0 else '❌ Не удалось добавить:\n' + '\n'.join(failed_uploads)
        bot.edit_message_text(chat_id=request.from_user.id, message_id=wait_message.message_id, text=f'🎉 Расписание загружено!\n{info_message}')

    bot.polling(none_stop=True, interval=0)


if __name__ == '__main__':
    start_bot()
