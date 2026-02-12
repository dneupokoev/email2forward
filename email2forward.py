# -*- coding: utf-8 -*-
# email2forward
# https://github.com/dneupokoev/email2forward
#
# Email to Forward: получает email, парсит его и отправляет содержимое письма в мессенджеры.
#
dv_file_version = '260212.01'
#
# 260212.01:
# - добавлена отправка изображений в Bitrix24 напрямую в папку чата
# - добавлено отслеживание уже отправленных изображений в рамках одного письма (если в письме 2 одинаковых файла, то отправится только один из них)
#
# 260129.01:
# - добавлено извлечение json из темы письма перед обработкой (это необходимо когда отправляющая система добавляет к вашему json-у еще какой-то текст)
#
# 230522.01:
# - добавлено распознавание текста с картинки и преобразования его в json (сохранение и прочее пока не сделано, пока только тестировать можно)
#
# 230414.01:
# - добавлено распознавание "цветного пятна" на картинках: если есть пятно/пятна указанного цвета (включая оттенки), то данная картинка будет отправлена. Возможные значения: black, white, red, green, blue, yellow, purple, orange, gray
#
# 230411.01:
# - добавлено распознавание текста на картинках и если есть "нужный" текст, то данная картинка будет отправлена
#
# 230331.01:
# - базовая стабильная версия (полностью протестированная и отлаженная)
#
import os
import re
import sys
import numpy as np
import platform
import configparser
import imaplib
import email
import telebot
import datetime
import time
import json
import ast
import pytesseract
import cv2
import hashlib
from io import BytesIO

import settings
from bitrix24_sender import Bitrix24ChatSafeSender

#
#
# Диапазон HSV для цветов
CONST_color_dict_HSV = {'black': [[180, 255, 30], [0, 0, 0]],
                        'white': [[180, 18, 255], [0, 0, 231]],
                        'red': [[9, 255, 255], [0, 50, 70]],
                        'red1': [[180, 255, 255], [159, 50, 70]],
                        'red2': [[9, 255, 255], [0, 50, 70]],
                        'green': [[89, 255, 255], [36, 50, 70]],
                        'blue': [[128, 255, 255], [90, 50, 70]],
                        'yellow': [[35, 255, 255], [25, 50, 70]],
                        'purple': [[158, 255, 255], [129, 50, 70]],
                        'orange': [[24, 255, 255], [10, 50, 70]],
                        'gray': [[180, 18, 230], [0, 0, 40]]}
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
if settings.LOG_DEBUG is True:
    logger.add(settings.PATH_TO_LOG + dv_file_name + ".log", level="DEBUG", rotation="00:00", retention='30 days', compression="gz", encoding="utf-8")
    logger.add(sys.stderr, level="DEBUG")
else:
    logger.add(settings.PATH_TO_LOG + dv_file_name + ".log", level="INFO", rotation="00:00", retention='30 days', compression="gz", encoding="utf-8")
    logger.add(sys.stderr, level="INFO")
logger.enable(dv_file_name)  # даем имя логированию


#
#
#
#
def get_now(format='%Y-%m-%d %H:%M:%S'):
    """
    Функция вернет текущую дату и время в заданном формате
    """
    dv_created = f"{datetime.datetime.fromtimestamp(time.time()).strftime(format)}"
    # dv_created = f"{datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f')}"
    return dv_created


def generate_unique_filename(filename=None, content_type=None):
    """
    Генерирует уникальное имя файла с временной меткой.
    Если filename не указан, генерирует имя на основе content_type или по умолчанию.
    """
    timestamp = datetime.datetime.now().strftime('%y%m%d%H%M%S')

    if filename:
        # Разделяем имя файла и расширение
        name, ext = os.path.splitext(filename)
        # Если расширение уже есть, используем его
        if ext:
            unique_filename = f"{timestamp}_{name}{ext}"
        else:
            # Если расширения нет, определяем по content_type
            if content_type:
                ext_map = {
                    'image/jpeg': '.jpg',
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'image/bmp': '.bmp',
                    'image/webp': '.webp',
                    'image/tiff': '.tiff'
                }
                ext = ext_map.get(content_type, '.bin')
            else:
                ext = '.bin'
            unique_filename = f"{timestamp}_{name}{ext}"
    else:
        # Генерируем имя файла на основе content_type или по умолчанию
        if content_type:
            ext_map = {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/bmp': '.bmp',
                'image/webp': '.webp',
                'image/tiff': '.tiff'
            }
            ext = ext_map.get(content_type, '.bin')
            name = 'inline_image'
        else:
            ext = '.png'
            name = 'image'
        unique_filename = f"{timestamp}_{name}{ext}"

    logger.debug(f"Сгенерировано уникальное имя файла: {unique_filename} (было: {filename})")
    return unique_filename


def is_image_content_type(content_type):
    """
    Проверяет, является ли Content-Type изображением
    """
    if not content_type:
        return False
    return content_type.lower().startswith('image/')


def extract_image_from_part(part):
    """
    Универсальное извлечение изображения из части письма
    Возвращает (image_bytes, filename, content_type, content_id, content_hash) или (None, None, None, None, None)
    """
    try:
        # Получаем Content-Type
        content_type = part.get_content_type()

        # Проверяем, является ли часть изображением
        if not is_image_content_type(content_type):
            return None, None, None, None, None

        # Получаем имя файла (если есть)
        filename = part.get_filename()

        # Получаем Content-ID (CID) - это уникальный идентификатор для встроенных изображений
        content_id = part.get("Content-ID")
        if content_id:
            # Очищаем Content-ID от угловых скобок
            content_id = content_id.strip('<>')
            logger.debug(f"Изображение: Content-ID={content_id}")

        # Получаем Content-Disposition для отладки
        content_disposition = part.get("Content-Disposition", "")
        # logger.debug(f"Изображение: Content-Type={content_type}, filename={filename}, Content-Disposition={content_disposition}")
        logger.debug(f"Изображение: Content-Type={content_type}, filename={filename}")

        # Получаем payload (содержимое)
        payload = part.get_payload(decode=True)
        if not payload:
            logger.debug("Пустой payload в изображении")
            return None, None, None, None, None

        # Вычисляем хэш содержимого для дедупликации
        content_hash = hashlib.md5(payload).hexdigest()
        logger.debug(f"Изображение: хэш MD5={content_hash}")

        # Создаем BytesIO из payload
        image_bytes = BytesIO(payload)

        return image_bytes, filename, content_type, content_id, content_hash

    except Exception as e:
        logger.error(f"Ошибка при извлечении изображения: {e}")
        return None, None, None, None, None


def extract_json_from_string(text):
    """
    Функция для извлечения JSON из строки, которая может содержать дополнительный текст
    """
    if not text:
        return None
    logger.debug(f"Попытка извлечь JSON из строки: '{text[:100]}...'")
    # Сначала попробуем обработать как чистый JSON
    try:
        json_data = json.loads(text)
        logger.debug(f"Строка является чистым JSON")
        return json_data
    except json.JSONDecodeError:
        logger.debug(f"Строка не является чистым JSON, ищем JSON внутри текста")
        # Ищем JSON в строке (ищем фигурные скобки)
        json_patterns = [
            r'\{[^{}]*\}',  # Простой JSON без вложенных объектов
            r'\{.*\}',  # JSON с вложенными объектами
        ]
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json_data = json.loads(match)
                    logger.debug(f"Найден JSON в строке: {match[:100]}...")
                    return json_data
                except json.JSONDecodeError:
                    continue
        # Если не нашли стандартный JSON, попробуем найти более сложные случаи
        # Ищем подстроку, начинающуюся с { и заканчивающуюся }
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx + 1]
            try:
                json_data = json.loads(json_str)
                logger.debug(f"Извлечен JSON из подстроки: {json_str[:100]}...")
                return json_data
            except json.JSONDecodeError as e:
                logger.debug(f"Не удалось распарсить JSON: {e}")
        logger.debug(f"JSON не найден в строке")
        return None


def connect_to_email():
    """
    Функция для подключения к почтовому ящику с установленными таймаутами
    """
    try:
        # подключаем почтовый ящик
        logger.debug(f"Попытка подключения к почтовому ящику: {settings.CONST_email_imap}")
        logger.debug(f"Логин: {settings.CONST_email_login}")
        mail = imaplib.IMAP4_SSL(settings.CONST_email_imap, 993)
        # Устанавливаем таймауты для ускорения операций
        mail.socket().settimeout(30)  # Таймаут на операции сокета
        mail.login(settings.CONST_email_login, settings.CONST_email_password)
        logger.info(f"Успешное подключение к почтовому ящику")
        return mail
    except Exception as error:
        logger.error(f"Ошибка подключения к почтовому ящику: {error}")
        return None


def disconnect_from_email(mail):
    """
    Функция для корректного и быстрого отключения от почтового ящика
    """
    if mail is None:
        return
    try:
        # Используем logout() с таймаутом
        mail.logout()
        logger.debug("Успешное отключение от почтового ящика")
    except Exception as error:
        logger.debug(f"Ошибка при отключении от почтового ящика (может быть нормальным): {error}")
        # Принудительно закрываем сокет в случае ошибки
        try:
            mail.shutdown()
        except:
            pass


def process_single_email(mail, email_uid, bot_telegram):
    """
    Обработка одного письма для лучшей модульности
    """
    try:
        # Получаем письмо с замером времени
        start_time = time.time()
        dv_mail_result, dv_mail_data = mail.uid('fetch', email_uid, '(RFC822)')
        logger.debug(f"Письмо {email_uid} получено за {time.time() - start_time:.2f} сек, статус: {dv_mail_result}")
        # конвертируем письмо в адекватный формат
        try:
            raw_email = dv_mail_data[0][1].decode("utf-8")
            email_message = email.message_from_string(raw_email)
        except:
            try:
                raw_email = dv_mail_data[0][1].decode(settings.CONST_email_encoding)
                email_message = email.message_from_string(raw_email)
            except Exception as error:
                logger.error(f'{email_uid} - Ошибка декодирования письма: {error}')
                return None, None
        return email_message, dv_mail_data
    except Exception as error:
        logger.error(f'{email_uid} - Ошибка при получении письма: {error}')
        return None, None


def parse_email_subject(email_uid, email_message):
    """
    Парсинг темы письма и извлечение JSON параметров
    """
    dv_mail_subj = {}
    try:
        # Получаем тему письма
        dv_mail_subj_raw = str(email.header.make_header(email.header.decode_header(email_message['Subject'])))
        logger.debug(f'{email_uid} - Тема письма (raw): {dv_mail_subj_raw}')
        # Пытаемся извлечь JSON из темы письма
        dv_mail_subj = extract_json_from_string(dv_mail_subj_raw)
        if dv_mail_subj is not None:
            logger.debug(f'{email_uid} - Тема письма (JSON извлечен): {dv_mail_subj}')
        else:
            logger.debug(f'{email_uid} - Тема письма не содержит JSON')
    except Exception as error:
        logger.error(f'{email_uid} - Ошибка при обработке темы письма: {error}')
    return dv_mail_subj


def process_text_content(email_uid, email_text, send, telegram_id, bitrix24_id, bot_telegram, tlg_bot_token, bitrix_sender):
    """
    Обработка и отправка текстового содержимого
    """
    if email_text and re.search(r'm', send.lower()):
        #
        if bitrix24_id and bitrix_sender:
            try:
                logger.info(f'{email_uid} - Отправка текста в Bitrix24: {len(email_text)} символов')
                success = bitrix_sender.send_message(bitrix24_id, email_text)
                if success:
                    logger.debug(f'{email_uid} - Bitrix24: текстовое сообщение отправлено успешно')
                else:
                    logger.warning(f'{email_uid} - Bitrix24: не удалось отправить текстовое сообщение')
            except Exception as error:
                logger.error(f'{email_uid} - dv_4send_bitrix24 - ERROR: {error}')
        #
        if telegram_id and bot_telegram:
            try:
                logger.info(f'{email_uid} - Отправка текста в Telegram чат {telegram_id}: {len(email_text)} символов')
                message_info = bot_telegram.send_message(telegram_id, email_text)
                logger.debug(f'{email_uid} - Telegram: текстовое сообщение отправлено успешно, ID: {message_info.message_id}')
            except Exception as error:
                logger.error(f'{email_uid} - dv_4send_telegram - ERROR: {error}')
                logger.error(f'{email_uid} - Токен бота: {tlg_bot_token[:10]}..., Чат ID: {telegram_id}, Текст: {email_text[:100]}...')
        else:
            logger.debug(f'{email_uid} - Пропуск отправки текста в Telegram: ID чата не указан')
        #
    else:
        logger.debug(f'{email_uid} - Пропуск отправки текста: email_text пуст или флаг "m" не установлен')


def process_image_attachment(
        email_uid, image_bytes_io, filename, content_type, content_id, content_hash, send, telegram_id, bitrix24_id,
        only_with_word_in_pic, only_with_color_in_pic, bot_telegram, tlg_bot_token, bitrix_sender):
    """
    Обработка и отправка изображения (универсальная функция)
    """
    logger.debug(f'{email_uid} - Обработка изображения: filename={filename}, content_type={content_type}, content_id={content_id}, hash={content_hash}')

    # Создаем копии BytesIO для разных назначений
    image_for_telegram = BytesIO(image_bytes_io.getvalue())
    image_for_bitrix = BytesIO(image_bytes_io.getvalue())
    image_for_analysis = BytesIO(image_bytes_io.getvalue())

    # Генерируем уникальное имя файла, если его нет
    if not filename:
        filename = generate_unique_filename(content_type=content_type)
        logger.debug(f'{email_uid} - Сгенерировано имя файла для изображения без имени: {filename}')

    # Если нужно на картинке распознать json и отправить:
    if re.search(r'j', send.lower()):
        try:
            logger.info(f'{email_uid} - Попытка распознать JSON из изображения')
            # конвертируем bytes в изображение
            dv_in_bytes = np.asarray(bytearray(image_for_analysis.read()), dtype=np.uint8)
            dv_etl_img = cv2.imdecode(dv_in_bytes, cv2.IMREAD_GRAYSCALE)
            # распознаем текст
            dv_json = pytesseract.image_to_string(dv_etl_img)
            # Удаляем переносы строки в распознанном тексте (разворачиваем в одну строку)
            dv_json = dv_json.replace('\n', '')
            dv_dict = ast.literal_eval(dv_json)
            dv_json = json.dumps(dv_dict)
            if telegram_id and bot_telegram:
                message_info1 = bot_telegram.send_message(telegram_id, dv_dict)
                message_info2 = bot_telegram.send_message(telegram_id, dv_json)
                logger.debug(f'{email_uid} - Telegram: JSON сообщения отправлены успешно, ID: {message_info1.message_id}, {message_info2.message_id}')
            # печатаем в лог
            logger.debug(f'{email_uid} - Распознанный JSON: {dv_json}')
        except Exception as error:
            logger.error(f'{email_uid} - dv_parse_json - ERROR: {error}')

    # если нужно отправлять pictures, то отправим
    if re.search(r'p', send.lower()):

        # --- АНАЛИЗ ИЗОБРАЖЕНИЯ (поиск слова и цвета) ---
        dv_is_pic_for_send = 1  # По умолчанию отправляем

        # если на картинке нужно искать слово, то будем искать
        if only_with_word_in_pic != '':
            dv_is_pic_for_send = 0
            logger.debug(f'{email_uid} - Поиск слова "{only_with_word_in_pic}" на изображении')
            try:
                # читаем изображение с помощью OpenCV
                dv_in_bytes = np.asarray(bytearray(BytesIO(image_bytes_io.getvalue()).read()), dtype=np.uint8)
                dv_etl_img = cv2.imdecode(dv_in_bytes, cv2.IMREAD_COLOR)
                # получаем больше информации, включая слова с соответствующими им шириной, высотой и координатами x, y
                dv_image_data = pytesseract.image_to_data(dv_etl_img, output_type=pytesseract.Output.DICT)
                logger.debug(f'{email_uid} - Распознанный текст: {dv_image_data["text"]}')
                # получаем все вхождения нужного слова
                dv_word_occurences = [i for i, word in enumerate(dv_image_data["text"]) if word == only_with_word_in_pic]
                # если слово нашли, то картинку будем отправлять
                if len(dv_word_occurences) > 0:
                    logger.debug(f'{email_uid} - Найдено вхождений слова: {dv_word_occurences}')
                    dv_is_pic_for_send = 1
                else:
                    logger.debug(f'{email_uid} - Слово не найдено на изображении')
            except Exception as e:
                logger.error(f'{email_uid} - Ошибка при поиске слова на изображении: {e}')

        # если нужно искать цветное пятно (и слово найдено или поиск слова отключен)
        if dv_is_pic_for_send == 1 and only_with_color_in_pic != '':
            dv_is_pic_for_send = 0
            logger.debug(f'{email_uid} - Поиск цвета "{only_with_color_in_pic}" на изображении')
            try:
                # читаем изображение с помощью OpenCV
                dv_in_bytes = np.asarray(bytearray(BytesIO(image_bytes_io.getvalue()).read()), dtype=np.uint8)
                dv_etl_img = cv2.imdecode(dv_in_bytes, cv2.IMREAD_COLOR)
                dv_img_hsv = cv2.cvtColor(dv_etl_img, cv2.COLOR_BGR2HSV)
                #
                # HSV фильтр для объектов, которые будем искать на картинке (диапазон цветов)
                dv_hsv_min = np.array(CONST_color_dict_HSV[only_with_color_in_pic][1], np.uint8)
                dv_hsv_max = np.array(CONST_color_dict_HSV[only_with_color_in_pic][0], np.uint8)
                #
                # применяем цветовой фильтр
                dv_thresh = cv2.inRange(dv_img_hsv, dv_hsv_min, dv_hsv_max)
                #
                # Удаляем слишком мелкие элементы
                dv_img_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                dv_thresh = cv2.morphologyEx(dv_thresh, cv2.MORPH_OPEN, dv_img_kernel)
                #
                # вычисляем моменты изображения
                dv_img_moments = cv2.moments(dv_thresh, 1)
                dv_m_00 = dv_img_moments['m00']
                logger.debug(f'{email_uid} - Цвет {only_with_color_in_pic} - dv_m_00 = {dv_m_00}')
                #
                # будем реагировать только на те моменты, которые содержат больше X пикселей
                if dv_m_00 > 100:
                    dv_is_pic_for_send = 1
                    logger.debug(f'{email_uid} - Цветное пятно найдено (dv_m_00 = {dv_m_00})')
                else:
                    logger.debug(f'{email_uid} - Цветное пятно не найдено (dv_m_00 = {dv_m_00})')
            except Exception as e:
                logger.error(f'{email_uid} - Ошибка при поиске цвета на изображении: {e}')
        # --- КОНЕЦ АНАЛИЗА ---

        if dv_is_pic_for_send == 1:
            # Отправляем только если изображение прошло все фильтры!

            # Отправка в Bitrix24
            if bitrix24_id and bitrix_sender:
                try:
                    logger.info(f'{email_uid} - Отправка изображения в Bitrix24 чат {bitrix24_id}')
                    # Убеждаемся, что имя файла уникальное
                    unique_filename = generate_unique_filename(filename, content_type)
                    # Отправляем изображение в чат
                    success = bitrix_sender.send_image_to_chat(
                        bitrix24_id,
                        BytesIO(image_for_bitrix.getvalue()),
                        unique_filename,
                        caption=''
                    )
                    if success:
                        logger.info(f'{email_uid} - Bitrix24: изображение успешно отправлено, файл: {unique_filename}')
                    else:
                        logger.warning(f'{email_uid} - Bitrix24: не удалось отправить изображение')
                except Exception as error:
                    logger.error(f'{email_uid} - Bitrix24 send_image - ERROR: {error}')

            # Отправка в Telegram
            if telegram_id and bot_telegram:
                try:
                    logger.info(f'{email_uid} - Отправка изображения в Telegram чат {telegram_id}')
                    message_info = bot_telegram.send_photo(
                        telegram_id,
                        BytesIO(image_for_telegram.getvalue()),
                        caption=''
                    )
                    logger.debug(f'{email_uid} - Telegram: изображение отправлено успешно, ID: {message_info.message_id}')
                except Exception as error:
                    logger.error(f'{email_uid} - Telegram send_photo - ERROR: {error}')
            else:
                logger.debug(f'{email_uid} - Пропуск отправки изображения в Telegram: ID чата не указан')
        else:
            logger.info(f'{email_uid} - Изображение НЕ ОТПРАВЛЕНО (не прошло фильтры: слово="{only_with_word_in_pic}", цвет="{only_with_color_in_pic}")')


def check_email():
    """
    Основная функция: читаем данные в почтовом ящике, парсит и отправляет
    """
    # Используем новую функцию подключения
    mail = connect_to_email()
    if mail is None:
        logger.error("Не удалось подключиться к почтовому ящику")
        return

    try:
        # print(mail.list()) # Отображаем список папок в почтовом ящике
        dv_mail_status, dv_mail_folder = mail.select("INBOX")  # Подключаемся к папке "входящие"
        logger.debug(f"Статус выбора папки INBOX: {dv_mail_status}")
        # dv_mail_status, dv_messages = mail.select("INBOX", readonly=False)
        #
        #
        # Открываем письма:
        # - аргумент "UNSEEN" - все uid-ы непросмотренных писем,
        # - аргумент "ALL" - с разрезе всех писем (если без all, то будет просто порядковый номер и не получится пометить прочитанным)
        dv_mail_status, dv_mail_unseen = mail.uid("search", "UNSEEN", "ALL")
        logger.debug(f"Статус поиска непрочитанных писем: {dv_mail_status}")
        # # Ограничение по дате (смотрим письма за 3 последних дня)
        # dv_date_start = (datetime.date.today() - datetime.timedelta(3)).strftime("%d-%b-%Y")
        # # получаем все UID имеющихся писем от ВСЕХ отправителей
        # dv_all_result, dv_all_data = mail.uid('search', None, f'(SENTSINCE {dv_date_start})')
        #
        # mail.logout()
        #
        # формируем список из идентификаторов писем
        dv_mail_list = dv_mail_unseen[0].decode(settings.CONST_email_encoding).split(" ")
        logger.debug(f"Найдено непрочитанных писем: {len(dv_mail_list) if dv_mail_list != [''] else 0}")
        #
        # если есть новые письма, то будем пытаться их обработать
        if dv_mail_list != ['']:
            #
            # получаем из ini данные для подключения к телеграм
            dv_tlg_bot_token = settings.CONST_sender_telegram
            # подключаем телеграм-бота
            dv_bot_telegram = telebot.TeleBot(dv_tlg_bot_token)
            logger.debug(f"Бот Telegram инициализирован, токен: {dv_tlg_bot_token[:10]}...")
            #
            # ИНИЦИАЛИЗАЦИЯ: создаем экземпляр Bitrix24ChatSafeSender
            dv_bitrix_sender = None
            if hasattr(settings, 'CONST_sender_bitrix24') and settings.CONST_sender_bitrix24:
                try:
                    dv_bitrix_sender = Bitrix24ChatSafeSender(settings.CONST_sender_bitrix24)
                    logger.debug(f"Bitrix24 sender инициализирован, вебхук: {settings.CONST_sender_bitrix24[:50]}...")
                except Exception as error:
                    logger.error(f"Ошибка инициализации Bitrix24 sender: {error}")
            #
            for dv_i_mail_list in range(0, len(dv_mail_list)):
                # Открываем самое первое непрочитанное письмо
                dv_email_uid_first = dv_mail_list[dv_i_mail_list]
                logger.info(f"Обработка письма с UID: {dv_email_uid_first}")
                # Используем новую функцию для обработки одного письма
                email_message, dv_mail_data = process_single_email(mail, dv_email_uid_first, dv_bot_telegram)
                if email_message is None:
                    continue
                # получаем отправителя
                dv_mail_from = str(email.header.make_header(email.header.decode_header(email_message['From'])))
                logger.debug(f'{dv_email_uid_first} - Отправитель: {dv_mail_from}')
                # если любой элемент листа CONST_white_list_email_sender входит в значение текущего dv_mail_from, то идем дальше
                if any(ext in dv_mail_from for ext in settings.CONST_white_list_email_sender):
                    logger.debug(f'{dv_email_uid_first} - Отправитель найден в белом списке')
                    # str(email.header.make_header(email.header.decode_header(email_message['Date'])))
                    # Используем новую функцию для парсинга темы
                    dv_mail_subj = parse_email_subject(dv_email_uid_first, email_message)
                    # Проверяем, что удалось извлечь JSON из темы письма
                    if dv_mail_subj is None:
                        logger.warning(f'{dv_email_uid_first} - Не удалось извлечь JSON из темы письма, пропускаем обработку')
                        # Помечаем письмо как прочитанное, если нет JSON
                        try:
                            mail.uid('STORE', dv_email_uid_first, '+FLAGS', '\\SEEN')  # Отметить как прочитанное
                            logger.debug(f'{dv_email_uid_first} - Письмо помечено как прочитанное (нет JSON в теме)')
                        except Exception as error:
                            logger.error(f'{dv_email_uid_first} - Ошибка при пометке письма как прочитанного: {error}')
                        continue

                    # --- ИЗВЛЕКАЕМ ПАРАМЕТРЫ ИЗ JSON ---
                    # title - Заголовок сообщения
                    dv_4send_title = ''
                    if "title" in dv_mail_subj:
                        dv_4send_title = dv_mail_subj['title']
                    logger.debug(f'{dv_email_uid_first} - dv_4send_title = {dv_4send_title}')

                    # send - что отправлять
                    dv_4send_send = 't'
                    if "send" in dv_mail_subj:
                        dv_4send_send = dv_mail_subj['send']
                    logger.debug(f'{dv_email_uid_first} - dv_4send_send = {dv_4send_send}')

                    # date/time - когда отправлять
                    dv_4send_date = ''
                    if "date" in dv_mail_subj:
                        dv_4send_date = dv_mail_subj['date']
                    dv_4send_time = '2000-01-01'
                    if "time" in dv_mail_subj:
                        dv_4send_time = dv_mail_subj['time']
                    else:
                        dv_4send_time = '00:00'
                    logger.debug(f'{dv_email_uid_first} - dv_4send_date = {dv_4send_date}, dv_4send_time = {dv_4send_time}')

                    # Проверяем наступила ли дата и время из email-а
                    dv_4send_check = 0
                    if dv_4send_date == '2000-01-01':
                        if dv_4send_time <= get_now(format='%H:%M'):
                            dv_4send_check = 1
                    elif f"{dv_4send_date} {dv_4send_time}" <= get_now(format='%Y-%m-%d %H:%M'):
                        dv_4send_check = 1
                    logger.debug(f'{dv_email_uid_first} - dv_4send_check = {dv_4send_check}')

                    # ID получателей
                    dv_4send_telegram = ''
                    if "telegram" in dv_mail_subj:
                        dv_4send_telegram = dv_mail_subj['telegram']
                        logger.debug(f'{dv_email_uid_first} - ID Telegram чата: {dv_4send_telegram}')

                    dv_4send_bitrix24 = ''
                    if "bitrix24" in dv_mail_subj:
                        dv_4send_bitrix24 = dv_mail_subj['bitrix24']
                        logger.debug(f'{dv_email_uid_first} - ID Bitrix24 чата: {dv_4send_bitrix24}')

                    # Фильтры для изображений
                    dv_4send_only_with_word_in_pic = ''
                    if "only_with_word_in_pic" in dv_mail_subj:
                        dv_4send_only_with_word_in_pic = dv_mail_subj['only_with_word_in_pic']

                    dv_4send_only_with_color_in_pic = ''
                    if "only_with_color_in_pic" in dv_mail_subj:
                        dv_4send_only_with_color_in_pic = dv_mail_subj['only_with_color_in_pic']
                        if dv_4send_only_with_color_in_pic not in CONST_color_dict_HSV:
                            dv_4send_only_with_color_in_pic = ''
                    # --- КОНЕЦ ИЗВЛЕЧЕНИЯ ПАРАМЕТРОВ ---

                    if dv_4send_check == 1:
                        # если нужно отправлять title, то отправим
                        if dv_4send_title != '' and re.search(r't', dv_4send_send.lower()):
                            # Отправка в Telegram
                            if dv_4send_telegram != '':
                                try:
                                    logger.info(f'{dv_email_uid_first} - Отправка заголовка в Telegram чат {dv_4send_telegram}: "{dv_4send_title}"')
                                    message_info = dv_bot_telegram.send_message(dv_4send_telegram, dv_4send_title)
                                    logger.debug(f'{dv_email_uid_first} - Telegram: сообщение отправлено успешно, ID: {message_info.message_id}')
                                except Exception as error:
                                    logger.error(f'{dv_email_uid_first} - dv_4send_telegram - ERROR: {error}')
                            # Отправка в Bitrix24
                            if dv_4send_bitrix24 != '' and dv_bitrix_sender:
                                try:
                                    logger.info(f'{dv_email_uid_first} - Отправка заголовка в Bitrix24: {dv_4send_bitrix24}')
                                    success = dv_bitrix_sender.send_message(dv_4send_bitrix24, dv_4send_title)
                                    if success:
                                        logger.debug(f'{dv_email_uid_first} - Bitrix24: заголовок отправлен успешно')
                                    else:
                                        logger.warning(f'{dv_email_uid_first} - Bitrix24: не удалось отправить заголовок')
                                except Exception as error:
                                    logger.error(f'{dv_email_uid_first} - dv_4send_bitrix24 - ERROR: {error}')
                        else:
                            logger.debug(f'{dv_email_uid_first} - Пропуск отправки заголовка: dv_4send_title пуст или флаг "t" не установлен')

                        # --- ОБРАБОТКА СОДЕРЖИМОГО ПИСЬМА ---
                        # Множество для отслеживания уже отправленных изображений в рамках этого письма
                        # ИСПРАВЛЕНО: Используем ТОЛЬКО хэш как ключ дедупликации
                        sent_images_hashes = set()

                        # Сначала обрабатываем multipart письма
                        if email_message.is_multipart():
                            for part in email_message.walk():
                                # Достаем текст из строки письма
                                try:
                                    dv_email_text = part.get_payload(decode=True).decode()
                                    # если текст слишком длинный, то обрезаем его
                                    if len(dv_email_text) > 3999:
                                        dv_email_text = dv_email_text[:3999]
                                except:
                                    dv_email_text = ''

                                # Получаем Content-Type и Content-Disposition
                                dv_row_content_type = part.get_content_type()
                                dv_row_content_disposition = str(part.get("Content-Disposition"))

                                # --- ОБРАБОТКА ТЕКСТА ---
                                if dv_row_content_type == 'text/plain' and dv_email_text != '' and dv_row_content_disposition == 'None':
                                    logger.debug(f'{dv_email_uid_first} - Найден текст: {len(dv_email_text)} символов')
                                    process_text_content(
                                        dv_email_uid_first, dv_email_text, dv_4send_send,
                                        dv_4send_telegram, dv_4send_bitrix24, dv_bot_telegram, dv_tlg_bot_token, dv_bitrix_sender
                                    )

                                # --- ОБРАБОТКА ИЗОБРАЖЕНИЙ С ДЕДУПЛИКАЦИЕЙ ---
                                # Проверяем, является ли часть изображением
                                image_bytes, filename, content_type, content_id, content_hash = extract_image_from_part(part)
                                if image_bytes is not None and content_hash:
                                    # ИСПРАВЛЕНО: Всегда используем хэш как единственный ключ для дедупликации
                                    if content_hash not in sent_images_hashes:
                                        logger.debug(f'{dv_email_uid_first} - Новое изображение (hash={content_hash}), добавляем в набор отправленных')
                                        sent_images_hashes.add(content_hash)

                                        # Это изображение! Отправляем его.
                                        logger.debug(
                                            f'{dv_email_uid_first} - Найдено изображение: Content-Type={content_type}, filename={filename}, content_id={content_id}')
                                        process_image_attachment(
                                            dv_email_uid_first,
                                            image_bytes,
                                            filename,
                                            content_type,
                                            content_id,
                                            content_hash,
                                            dv_4send_send,
                                            dv_4send_telegram,
                                            dv_4send_bitrix24,
                                            dv_4send_only_with_word_in_pic,
                                            dv_4send_only_with_color_in_pic,
                                            dv_bot_telegram,
                                            dv_tlg_bot_token,
                                            dv_bitrix_sender
                                        )
                                    else:
                                        logger.debug(f'{dv_email_uid_first} - Изображение уже было отправлено (hash={content_hash}), пропускаем дубликат')

                        else:
                            # Не multipart письмо (простое)
                            dv_row_content_type = email_message.get_content_type()

                            # --- ОБРАБОТКА ТЕКСТА ---
                            if dv_row_content_type == "text/plain":
                                try:
                                    dv_email_text = email_message.get_payload(decode=True).decode()
                                    if len(dv_email_text) > 3999:
                                        dv_email_text = dv_email_text[:3999]
                                except:
                                    dv_email_text = ''
                                logger.debug(f'{dv_email_uid_first} - Найден текст (простое письмо): {len(dv_email_text)} символов')
                                process_text_content(
                                    dv_email_uid_first, dv_email_text, dv_4send_send,
                                    dv_4send_telegram, dv_4send_bitrix24, dv_bot_telegram, dv_tlg_bot_token, dv_bitrix_sender
                                )

                            # --- ОБРАБОТКА ИЗОБРАЖЕНИЙ В ПРОСТОМ ПИСЬМЕ ---
                            image_bytes, filename, content_type, content_id, content_hash = extract_image_from_part(email_message)
                            if image_bytes is not None and content_hash:
                                # ИСПРАВЛЕНО: Всегда используем хэш как единственный ключ для дедупликации
                                if content_hash not in sent_images_hashes:
                                    sent_images_hashes.add(content_hash)

                                    logger.debug(
                                        f'{dv_email_uid_first} - Найдено изображение в простом письме: Content-Type={content_type}, filename={filename}')
                                    process_image_attachment(
                                        dv_email_uid_first,
                                        image_bytes,
                                        filename,
                                        content_type,
                                        content_id,
                                        content_hash,
                                        dv_4send_send,
                                        dv_4send_telegram,
                                        dv_4send_bitrix24,
                                        dv_4send_only_with_word_in_pic,
                                        dv_4send_only_with_color_in_pic,
                                        dv_bot_telegram,
                                        dv_tlg_bot_token,
                                        dv_bitrix_sender
                                    )
                    else:
                        # Дата/время еще не наступили - помечаем как непрочитанное
                        try:
                            mail.uid('STORE', dv_email_uid_first, '-FLAGS', '\\SEEN')
                            logger.debug(f'{dv_email_uid_first} - Письмо помечено как непрочитанное (дата/время еще не наступили)')
                        except Exception as error:
                            logger.error(f'{dv_email_uid_first} - Ошибка при пометке письма как непрочитанного: {error}')
                else:
                    # Отправитель не в белом списке
                    try:
                        mail.uid('STORE', dv_email_uid_first, '-FLAGS', '\\SEEN')
                        logger.debug(f'{dv_email_uid_first} - Письмо помечено как непрочитанное (отправитель не в белом списке)')
                    except Exception as error:
                        logger.error(f'{dv_email_uid_first} - Ошибка при пометке письма как непрочитанного: {error}')
        else:
            logger.debug(f"Нет новых непрочитанных писем")

    except Exception as error:
        logger.error(f"Ошибка при обработке писем: {error}")
    finally:
        # Используем новую функцию для отключения
        disconnect_from_email(mail)


if __name__ == '__main__':
    dv_time_begin = time.time()
    logger.info(f'***')
    logger.info(f'BEGIN')
    try:
        # Получаем версию ОС
        logger.info(f'os.version = {platform.platform()}')
    except Exception as error:
        # Не удалось получить версию ОС
        logger.error(f'ERROR - os.version: {error}')
    try:
        # Получаем версию питона
        logger.info(f'python.version = {sys.version}')
    except Exception as error:
        # Не удалось получить версию питона
        logger.error(f'ERROR - python.version: {error}')
    logger.info(f'dv_path_main = {dv_path_main}')
    logger.info(f'dv_file_name = {dv_file_name}')
    logger.info(f'dv_file_version = {dv_file_version}')
    logger.debug(f'settings.DEBUG = {settings.LOG_DEBUG}')
    logger.debug(f'settings.PATH_TO_LIB = {settings.PATH_TO_LIB}')
    logger.debug(f'settings.PATH_TO_LOG = {settings.PATH_TO_LOG}')
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
            logger.debug(f'Конфигурационный файл прочитан: {dv_lib_path_ini}')
    except Exception as error:
        logger.error(f'Ошибка при чтении конфигурационного файла: {error}')
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
            logger.debug(f'Файл блокировки создан: {dv_file_lib_path}')
        #
        # ОСНОВНАЯ ФУНКЦИЯ
        # пока скрипт работает меньше отведенного времени будем обрабатывать письма
        logger.info(f"Начало обработки писем (максимальное время работы: {settings.CONST_max_minutes_work} минут)")
        while round(int('{:.0f}'.format(1000 * (time.time() - dv_time_begin))) / (1000 * 60)) < settings.CONST_max_minutes_work:
            start_cycle_time = time.time()  # Замер времени начала цикла
            check_email()
            cycle_time = time.time() - start_cycle_time
            logger.debug(f"Цикл обработки писем занял: {cycle_time:.2f} секунд")
            # Оптимизация: динамическая пауза в зависимости от времени выполнения
            if cycle_time < 30:
                sleep_time = 30 - cycle_time
                logger.debug(f"Пауза перед следующим циклом: {sleep_time:.2f} секунд")
                time.sleep(sleep_time)
            else:
                logger.debug(f"Цикл занял больше 30 секунд, продолжаем без паузы")
        #
        # Удаляем файл блокировки после успешного завершения
        if os.path.exists(dv_file_lib_path):
            os.remove(dv_file_lib_path)
            logger.debug(f'Файл блокировки удален: {dv_file_lib_path}')
        #
    except Exception as error:
        logger.error(f'ERROR - python.version: {error}')
        # Удаляем файл блокировки при ошибке
        try:
            if os.path.exists(dv_file_lib_path):
                os.remove(dv_file_lib_path)
                logger.debug(f'Файл блокировки удален после ошибки: {dv_file_lib_path}')
        except:
            pass
    #
    total_work_time = time.time() - dv_time_begin
    logger.info(f"{datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f')}")
    work_time_ms = int('{:.0f}'.format(1000 * total_work_time))
    logger.info(f"work_time_ms = {work_time_ms}")
    logger.info(f"Общее время работы: {total_work_time:.2f} секунд")
    #
    logger.info(f'END')