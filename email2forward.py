# -*- coding: utf-8 -*-
# email2forward
# https://github.com/dneupokoev/email2forward
dv_file_version = '230331.01'
#
# Email to Forward: получает email, парсит его и отправляет содержимое письма в мессенджеры.

import settings
import os
import re
import sys
import platform
import configparser
import imaplib
import email
import telebot
import datetime
import time
import json
import requests
#
#
from pathlib import Path

try:  # from project
    dv_path_main = f"{Path(__file__).parent}/"
    dv_file_name = f"{Path(__file__).name}"
except:  # from jupiter
    dv_path_main = f"{Path.cwd()}/"
    dv_path_main = dv_path_main.replace('jupyter/', '')
    dv_file_name = 'unknown_file'

# импортируем библиотеку для логирования
from loguru import logger

# logger.add("log/" + dv_file_name + ".json", level="DEBUG", rotation="00:00", retention='30 days', compression="gz", encoding="utf-8", serialize=True)
# logger.add("log/" + dv_file_name + ".json", level="WARNING", rotation="00:00", retention='30 days', compression="gz", encoding="utf-8", serialize=True)
# logger.add("log/" + dv_file_name + ".json", level="INFO", rotation="00:00", retention='30 days', compression="gz", encoding="utf-8", serialize=True)
logger.remove()  # отключаем логирование в консоль
if settings.DEBUG is True:
    logger.add(settings.PATH_TO_LOG + dv_file_name + ".log", level="DEBUG", rotation="00:00", retention='30 days', compression="gz", encoding="utf-8")
    logger.add(sys.stderr, level="DEBUG")
else:
    logger.add(settings.PATH_TO_LOG + dv_file_name + ".log", level="INFO", rotation="00:00", retention='30 days', compression="gz", encoding="utf-8")
    logger.add(sys.stderr, level="INFO")
logger.enable(dv_file_name)  # даем имя логированию
logger.info(f'***')
logger.info(f'BEGIN')
try:
    # Получаем версию ОС
    logger.info(f'os.version = {platform.platform()}')
except Exception as error:
    # Не удалось получить версию ОС
    logger.error(f'ERROR - os.version: {error = }')
try:
    # Получаем версию питона
    logger.info(f'python.version = {sys.version}')
except Exception as error:
    # Не удалось получить версию питона
    logger.error(f'ERROR - python.version: {error = }')
logger.info(f'{dv_path_main = }')
logger.info(f'{dv_file_name = }')
logger.info(f'{dv_file_version = }')
logger.debug(f'{settings.DEBUG = }')
logger.debug(f'{settings.PATH_TO_LIB = }')
logger.debug(f'{settings.PATH_TO_LOG = }')


#
#
#
#
def get_now(format='%Y-%m-%d %H:%M:%S'):
    '''
    Функция вернет текущую дату и время в заданном формате
    '''
    dv_created = f"{datetime.datetime.fromtimestamp(time.time()).strftime(format)}"
    # dv_created = f"{datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f')}"
    return dv_created


def check_email():
    '''
    Основная функция: читаем данные в почтовом ящике, парсит и отправляет
    '''
    # подключаем почтовый ящик
    mail = imaplib.IMAP4_SSL(settings.CONST_email_imap, 993)
    mail.login(settings.CONST_email_login, settings.CONST_email_password)
    # print(mail.list()) # Отображаем список папок в почтовом ящике
    dv_mail_status, dv_mail_folder = mail.select("INBOX")  # Подключаемся к папке "входящие"
    # dv_mail_status, dv_messages = mail.select("INBOX", readonly=False)
    #
    #
    # Открываем письма:
    # - аргумент "UNSEEN" - все uid-ы непросмотренных писем,
    # - аргумент "ALL" - с разрезе всех писем (если без all, то будет просто порядковый номер и не получится пометить прочитанным)
    dv_mail_status, dv_mail_unseen = mail.uid("search", "UNSEEN", "ALL")
    # # Ограничение по дате (смотрим письма за 3 последних дня)
    # dv_date_start = (datetime.date.today() - datetime.timedelta(3)).strftime("%d-%b-%Y")
    # # получаем все UID имеющихся писем от ВСЕХ отправителей
    # dv_all_result, dv_all_data = mail.uid('search', None, f'(SENTSINCE {dv_date_start})')
    #
    # mail.logout()
    #
    # формируем список из идентификаторов писем
    dv_mail_list = dv_mail_unseen[0].decode(settings.CONST_email_encoding).split(" ")
    #
    # если есть новые письма, то будем пытаться их обработать
    if dv_mail_list != ['']:
        #
        # получаем из ini данные для подключения к телеграм
        dv_tlg_bot_token = settings.CONST_sender_telegram
        # подключаем телеграм-бота
        dv_bot_telegram = telebot.TeleBot(dv_tlg_bot_token)
        #
        for dv_i_mail_list in range(0, len(dv_mail_list)):
            # Открываем самое первое непрочитанное письмо и сразу помечаем прочитанным
            dv_email_uid_first = dv_mail_list[dv_i_mail_list]
            dv_mail_result, dv_mail_data = mail.uid('fetch', dv_email_uid_first, '(RFC822)')
            # print(dv_mail_result)
            #
            # конвертируем письмо в адекватный формат
            raw_email = dv_mail_data[0][1].decode("utf-8")
            email_message = email.message_from_string(raw_email)
            # raw_email = dv_mail_data[0][1]
            # email_message = email.message_from_bytes(raw_email)
            # email_message.items()
            # получаем отправителя
            dv_mail_from = str(email.header.make_header(email.header.decode_header(email_message['From'])))
            # если любой элемент листа CONST_white_list_email_sender входит в значение текущего dv_mail_from, то идем дальше
            if any(ext in dv_mail_from for ext in settings.CONST_white_list_email_sender):
                # str(email.header.make_header(email.header.decode_header(email_message['Date'])))
                dv_mail_subj = {}
                try:
                    dv_mail_subj = json.loads(str(email.header.make_header(email.header.decode_header(email_message['Subject']))))
                except:
                    pass
                # print(dv_mail_subj)
                #
                # парсим dv_mail_subj, чтобы понять куда и во сколько кидать сообщение
                # title - Заголовок сообщения
                dv_4send_title = ''
                if "title" in dv_mail_subj:
                    dv_4send_title = dv_mail_subj['title']
                # print(f"{dv_4send_title = }")
                logger.debug(f'{dv_email_uid_first} - {dv_4send_title = }')
                # send - что отправлять
                dv_4send_send = 't'
                if "send" in dv_mail_subj:
                    dv_4send_send = dv_mail_subj['send']
                # print(f"{dv_4send_send = }")
                logger.debug(f'{dv_email_uid_first} - {dv_4send_send = }')
                #
                dv_4send_date = ''
                if "date" in dv_mail_subj:
                    dv_4send_date = dv_mail_subj['date']
                dv_4send_time = '2000-01-01'
                if "time" in dv_mail_subj:
                    dv_4send_time = dv_mail_subj['time']
                else:
                    dv_4send_time = '00:00'
                # print(f"{dv_4send_date = }")
                logger.debug(f'{dv_email_uid_first} - {dv_4send_date = }')
                # print(f"{dv_4send_time = }")
                logger.debug(f'{dv_email_uid_first} - {dv_4send_time = }')
                #
                # Проверяем наступила ли дата и время из email-а (если они там указаны)
                dv_4send_check = 0
                if dv_4send_date == '2000-01-01':
                    if dv_4send_time <= get_now(format='%H:%M'):
                        dv_4send_check = 1
                elif f"{dv_4send_date} {dv_4send_time}" <= get_now(format='%Y-%m-%d %H:%M'):
                    dv_4send_check = 1
                # print(f"{dv_4send_check = }")
                logger.debug(f'{dv_email_uid_first} - {dv_4send_check = }')
                #
                if dv_4send_check == 1:
                    #
                    dv_4send_telegram = ''
                    if "telegram" in dv_mail_subj:
                        dv_4send_telegram = dv_mail_subj['telegram']
                    #
                    dv_4send_bitrix24 = ''
                    if "bitrix24" in dv_mail_subj:
                        dv_4send_bitrix24 = dv_mail_subj['bitrix24']
                    #
                    # если нужно отправлять title, то отправим
                    if dv_4send_title != '' and re.search(r't', dv_4send_send.lower()):
                        #
                        if dv_4send_telegram != '':
                            try:
                                dv_bot_telegram.send_message(dv_4send_telegram, dv_4send_title)
                            except Exception as error:
                                # print(f'dv_4send_telegram - ERROR: {error = }')
                                logger.error(f'{dv_email_uid_first} - dv_4send_telegram - ERROR: {error = }')
                        #
                        if dv_4send_bitrix24 != '':
                            try:
                                dv_bitrix24_title = {
                                    'DIALOG_ID': dv_4send_bitrix24,
                                    'MESSAGE': dv_4send_title,
                                }
                                response = requests.get(settings.CONST_sender_bitrix24, dv_bitrix24_title)
                            except Exception as error:
                                # print(f'dv_4send_bitrix24 - ERROR: {error = }')
                                logger.error(f'{dv_email_uid_first} - dv_4send_bitrix24 - ERROR: {error = }')
                    #
                    if email_message.is_multipart():
                        for part in email_message.walk():
                            # print('***')
                            dv_row_content_type = part.get_content_type()
                            # print(f"{dv_row_content_type=}")
                            dv_row_content_disposition = str(part.get("Content-Disposition"))
                            # print(f"{dv_row_content_disposition=}")
                            #
                            # Достаем текст из строки письма
                            try:
                                dv_email_text = part.get_payload(decode=True).decode()
                                # если текст слишком длинный, то обрезаем его
                                if len(dv_email_text) > 3999:
                                    dv_email_text = dv_email_text[:3999]
                            except:
                                dv_email_text = ''
                            #
                            # Разбираем письмо и отправляем
                            if dv_row_content_type == 'text/plain' and dv_email_text != '' and dv_row_content_disposition == 'None':
                                # тип текст, не пусто, не вложение
                                # print(dv_email_text)
                                logger.debug(f'{dv_email_uid_first} - {dv_email_text = }')
                                # если нужно отправлять message, то отправим
                                if dv_email_text != '' and re.search(r'm', dv_4send_send.lower()):
                                    if dv_4send_telegram != '':
                                        try:
                                            dv_bot_telegram.send_message(dv_4send_telegram, dv_email_text)
                                        except Exception as error:
                                            # print(f'dv_4send_telegram - ERROR: {error = }')
                                            logger.error(f'{dv_email_uid_first} - dv_4send_telegram - ERROR: {error = }')
                                    if dv_4send_bitrix24 != '':
                                        try:
                                            dv_bitrix24_title = {
                                                'DIALOG_ID': dv_4send_bitrix24,
                                                'MESSAGE': dv_email_text,
                                            }
                                            response = requests.get(settings.CONST_sender_bitrix24, dv_bitrix24_title)
                                        except Exception as error:
                                            # print(f'dv_4send_bitrix24 - ERROR: {error = }')
                                            logger.error(f'{dv_email_uid_first} - dv_4send_bitrix24 - ERROR: {error = }')
                            else:
                                # если дошли до этого момента, то пробуем извлечь картинку
                                filename = part.get_filename()
                                if filename:  # обрабатываем файлы
                                    # если название файла заканчивается на "\.png$|\.jpg$|\.jpeg$", то отправляем в телеграм
                                    if re.search(r'\.png$|\.jpg$|\.jpeg$', filename.lower()):
                                        # print(filename)
                                        logger.debug(f'{dv_email_uid_first} - {filename = }')
                                        # если нужно отправлять pictures, то отправим
                                        if re.search(r'p', dv_4send_send.lower()):
                                            if dv_4send_telegram != '':
                                                try:
                                                    dv_bot_telegram.send_photo(dv_4send_telegram, part.get_payload(decode=True))
                                                except Exception as error:
                                                    # print(f'dv_4send_telegram - ERROR: {error = }')
                                                    logger.error(f'{dv_email_uid_first} - dv_4send_telegram - ERROR: {error = }')
                                            if dv_4send_bitrix24 != '':
                                                try:
                                                    dv_bitrix24_title = {
                                                        'DIALOG_ID': dv_4send_bitrix24,
                                                        'MESSAGE': f'Внимание! в обрабатываемом письме есть картинка "{filename}", но я пока не умею их отправлять в bitrix24',
                                                    }
                                                    # dv_bitrix24_title = {
                                                    #     'DIALOG_ID': dv_4send_bitrix24,
                                                    #     'MESSAGE': 'Message from bot',
                                                    #     'ATTACH': [
                                                    #         {'IMAGE': {
                                                    #             'NAME': 'image_name',
                                                    #             'LINK': 'https://chatapp.online/images/2021/12/1/HzHsxITl27qqaDl31l52ztbgWg73XeNJR9QjUlxA.png',
                                                    #         }}
                                                    #     ]
                                                    # }
                                                    response = requests.get(settings.CONST_sender_bitrix24, dv_bitrix24_title)
                                                except Exception as error:
                                                    # print(f'dv_4send_bitrix24 - ERROR: {error = }')
                                                    logger.error(f'{dv_email_uid_first} - dv_4send_bitrix24 - ERROR: {error = }')
                    else:
                        dv_row_content_type = email_message.get_content_type()
                        if dv_row_content_type == "text/plain":
                            # Достаем текст из письма
                            try:
                                dv_email_text = email_message.get_payload(decode=True).decode()
                                # если текст слишком длинный, то обрезаем его
                                if len(dv_email_text) > 3999:
                                    dv_email_text = dv_email_text[:3999]
                            except:
                                dv_email_text = ''
                            # print(dv_email_text)
                            logger.debug(f'{dv_email_uid_first} - {dv_email_text = }')
                            # если нужно отправлять message, то отправим
                            if dv_email_text != '' and re.search(r'm', dv_4send_send.lower()):
                                if dv_email_text != '':
                                    if dv_4send_telegram != '':
                                        try:
                                            dv_bot_telegram.send_message(dv_4send_telegram, dv_email_text)
                                        except Exception as error:
                                            # print(f'dv_4send_telegram - ERROR: {error = }')
                                            logger.error(f'{dv_email_uid_first} - dv_4send_telegram - ERROR: {error = }')
                                if dv_4send_bitrix24 != '':
                                    try:
                                        dv_bitrix24_title = {
                                            'DIALOG_ID': dv_4send_bitrix24,
                                            'MESSAGE': dv_email_text,
                                        }
                                        response = requests.get(settings.CONST_sender_bitrix24, dv_bitrix24_title)
                                    except Exception as error:
                                        # print(f'dv_4send_bitrix24 - ERROR: {error = }')
                                        logger.error(f'{dv_email_uid_first} - dv_4send_bitrix24 - ERROR: {error = }')
                else:
                    # принудительно меняем статус письма "прочитано": (-) означает УДАЛИТЬ флаг (станет НЕпрочитано), а (+) означает ДОБАВИТЬ флаг (станет ПРОЧИТАНО)
                    mail.uid('STORE', dv_mail_list[0], '-FLAGS', '\SEEN')  # Отметить как непрочитанное
                    # mail.uid('STORE', dv_mail_list[0], '+FLAGS', '\SEEN')  # Отметить как прочитанное
            else:
                # отправитель не из списка разрешенных
                logger.warning(f'{dv_email_uid_first} - Отправитель не из списка settings.CONST_white_list_email_sender - {dv_mail_from}')


if __name__ == '__main__':
    dv_time_begin = time.time()
    #
    logger.info(f"{datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f')}")
    dv_lib_path_ini = ''
    try:
        # читаем значения из конфига
        dv_lib_path_ini = f"{settings.PATH_TO_LIB}/email2forward.cfg"
        dv_cfg = configparser.ConfigParser()
        if os.path.exists(dv_lib_path_ini):
            with open(dv_lib_path_ini, mode="r", encoding='utf-8') as fp:
                dv_cfg.read_file(fp)
        # читаем значения
        dv_cfg_last_send_tlg_success = dv_cfg.get('DEFAULT', 'last_send_tlg_success', fallback='2000-01-01 00:00:00')
    except:
        pass
    #
    try:
        dv_file_lib_path = f"{settings.PATH_TO_LIB}/email2forward.dat"
        if os.path.exists(dv_file_lib_path):
            dv_file_lib_open = open(dv_file_lib_path, mode="r", encoding='utf-8')
            dv_file_lib_time = next(dv_file_lib_open).strip()
            dv_file_lib_open.close()
            dv_file_old_start = datetime.datetime.strptime(dv_file_lib_time, '%Y-%m-%d %H:%M:%S')
            tmp_now = datetime.datetime.strptime(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
            tmp_seconds = int((tmp_now - dv_file_old_start).total_seconds())
            if tmp_seconds < settings.CONST_max_minutes_work * 2 * 60:
                raise Exception(f"Уже выполняется c {dv_file_lib_time} - перед запуском дождитесь завершения предыдущего процесса!")
        else:
            dv_file_lib_open = open(dv_file_lib_path, mode="w", encoding='utf-8')
            dv_file_lib_time = f"{datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')}"
            dv_file_lib_open.write(f"{dv_file_lib_time}")
            dv_file_lib_open.close()
        #
        # ОСНОВНАЯ ФУНКЦИЯ
        # пока скрипт работает меньше отведенного времени будем обрабатывать письма
        while round(int('{:.0f}'.format(1000 * (time.time() - dv_time_begin))) / (1000 * 60)) < settings.CONST_max_minutes_work:
            check_email()
            # делаем небольшую паузу (чтобы почтовый ящик не сильно задолбать проверкой): time.sleep(30) = пауза 30 секунд
            time.sleep(30)
        #
    except Exception as error:
        logger.error(f'ERROR - python.version: {error = }')
    #
    logger.info(f"{datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f')}")
    work_time_ms = int('{:.0f}'.format(1000 * (time.time() - dv_time_begin)))
    logger.info(f"{work_time_ms = }")
    #
    logger.info(f'END')
