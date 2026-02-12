# -*- coding: utf-8 -*-
"""
Bitrix24 Chat-Safe Sender Module
Отправка изображений напрямую в папку чата с автоматическим созданием папки
Использует метод im.disk.folder.get
"""
#
dv_file_version = '260211.09'
#
import time
import requests
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import qrcode
from io import BytesIO

import settings

logger = logging.getLogger(__name__)


class Bitrix24ChatSafeSender:
    """
    Отправка изображений напрямую в папку чата
    Файлы автоматически доступны всем участникам чата
    """

    def __init__(self, webhook_url: str):
        """
        :param webhook_url: URL вебхука Bitrix24
        """
        self.webhook_url = webhook_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 15

        if not self.webhook_url.startswith(('http://', 'https://')):
            raise ValueError("Некорректный формат вебхука Bitrix24")

        logger.info(f"✅ Bitrix24ChatSafeSender инициализирован")
        logger.info(f"   Вебхук: {self.webhook_url[:50]}...")

    def _call_api(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Универсальный метод вызова REST API Bitrix24"""
        url = f"{self.webhook_url}/{method}.json"

        try:
            response = self.session.post(url, json=params, timeout=15)
            response.raise_for_status()
            result = response.json()

            if not result.get('result'):
                error_msg = result.get('error_description', result.get('error', 'Unknown error'))
                logger.error(f"❌ Bitrix24 API error ({method}): {error_msg}")
                logger.debug(f"   Полный ответ: {result}")
                return {}

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка сети при вызове Bitrix24 API ({method}): {e}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга ответа Bitrix24 ({method}): {e}")
            return {}

    def send_message(self, dialog_id: str, message: str) -> bool:
        """Отправка текстового сообщения в диалог"""
        logger.info(f"💬 Отправка текстового сообщения в диалог {dialog_id}...")

        params = {
            'DIALOG_ID': dialog_id,
            'MESSAGE': message
        }
        result = self._call_api('im.message.add', params)
        success = bool(result.get('result'))

        if success:
            msg_id = result['result']
            logger.info(f"✅✅✅ Сообщение отправлено в диалог {dialog_id}, ID: {msg_id}")
        else:
            logger.warning(f"❌ Не удалось отправить сообщение в диалог {dialog_id}")

        return success

    def get_chat_folder_id(self, dialog_id: str) -> Optional[int]:
        """
        Получение ID папки чата через im.disk.folder.get

        :param dialog_id: ID диалога (например, "chat81328")
        :return: ID папки чата на Диске или None
        """
        logger.info(f"📂 Получение папки чата для {dialog_id}...")

        params = {
            'DIALOG_ID': dialog_id
        }

        result = self._call_api('im.disk.folder.get', params)

        if result and result.get('result'):
            folder_id = result['result'].get('ID')
            if folder_id:
                logger.info(f"✅ Папка чата получена: ID={folder_id}")
                return int(folder_id)

        logger.error(f"❌ Не удалось получить папку чата для {dialog_id}")
        return None

    def upload_file_to_folder(self, folder_id: int, file_bytes: BytesIO, filename: str) -> Optional[int]:
        """
        Загрузка файла в указанную папку на Диске

        :param folder_id: ID папки на Диске
        :param file_bytes: BytesIO с содержимым файла
        :param filename: Имя файла
        :return: UPLOAD_ID файла или None
        """
        file_content = file_bytes.getvalue()
        content_size = len(file_content)

        logger.info(f"📤 Загрузка файла '{filename}' в папку {folder_id}...")
        logger.info(f"📊 Размер: {content_size} байт")

        # === Этап 1: Получение uploadUrl ===
        logger.info("➡️  ЭТАП 1/2: Запрос uploadUrl...")
        params_step1 = {
            'id': folder_id,
            'data': json.dumps({'NAME': filename, 'SIZE': content_size})
        }

        try:
            url_step1 = f"{self.webhook_url}/disk.folder.uploadfile.json"
            response1 = self.session.post(url_step1, data=params_step1, timeout=15)
            result1 = response1.json()

            if not result1.get('result') or 'uploadUrl' not in result1['result']:
                logger.error(f"❌ Ошибка получения uploadUrl: {result1}")
                return None

            upload_url = result1['result']['uploadUrl']
            logger.info("✅ Получен uploadUrl")

        except Exception as e:
            logger.error(f"❌ Ошибка этапа 1: {e}")
            return None

        # === Этап 2: Отправка файла ===
        logger.info("➡️  ЭТАП 2/2: Отправка файла...")

        try:
            # Определяем MIME-тип
            ext = Path(filename).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp',
                '.pdf': 'application/pdf',
                '.txt': 'text/plain',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }.get(ext, 'application/octet-stream')

            # Отправляем multipart/form-data
            files = {'file': (filename, file_content, mime_type)}
            response2 = self.session.post(upload_url, files=files, timeout=30)
            result2 = response2.json()

            if response2.status_code != 200:
                logger.error(f"❌ Ошибка загрузки: статус {response2.status_code}")
                if 'error' in result2:
                    logger.error(f"   Ошибка: {result2.get('error_description', result2.get('error'))}")
                return None

            # Извлекаем ID файла
            if isinstance(result2.get('result'), dict):
                upload_id = result2['result'].get('ID')
                if upload_id:
                    logger.info(f"✅✅✅ Файл успешно загружен")
                    logger.info(f"📁 UPLOAD_ID: {upload_id}")
                    return int(upload_id)

            logger.error(f"❌ Не удалось извлечь ID файла: {result2}")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка этапа 2: {e}")
            return None

    def send_file_to_chat(self, dialog_id: str, file_bytes: BytesIO, filename: str, caption: str = '') -> bool:
        """
        Отправка файла в чат с автоматическим использованием папки чата

        :param dialog_id: ID диалога (например, "chat81328")
        :param file_bytes: BytesIO с содержимым файла
        :param filename: Имя файла
        :param caption: Подпись к файлу
        :return: True при успехе, иначе False
        """
        logger.info(f"📎 Отправка файла в чат {dialog_id}...")
        logger.info(f"📄 Имя файла: {filename}")
        logger.info(f"📝 Подпись: {caption}")

        # Шаг 1: Получаем ID папки чата
        logger.info("📂 1. Получение папки чата...")
        chat_folder_id = self.get_chat_folder_id(dialog_id)

        if not chat_folder_id:
            logger.critical("❌ Не удалось получить папку чата!")
            fallback_msg = f"{caption}\n⚠️ Файл не может быть отправлен (ошибка папки чата)"
            self.send_message(dialog_id, fallback_msg)
            return False

        # Шаг 2: Загружаем файл в папку чата
        logger.info("📤 2. Загрузка файла в папку чата...")
        upload_id = self.upload_file_to_folder(chat_folder_id, file_bytes, filename)

        if not upload_id:
            logger.critical("❌ Загрузка файла не удалась!")
            fallback_msg = f"{caption}\n⚠️ Файл не может быть отправлен (ошибка загрузки)"
            self.send_message(dialog_id, fallback_msg)
            return False

        # Шаг 3: Отправляем файл в чат
        logger.info("💬 3. Отправка файла в чат...")
        params = {
            'DIALOG_ID': dialog_id,
            'MESSAGE': caption,
            'UPLOAD_ID': upload_id
        }

        result = self._call_api('im.disk.file.commit', params)
        success = bool(result.get('result'))

        if success:
            msg_id = result['result']
            logger.info(f"✅✅✅ Файл УСПЕШНО отправлен в чат {dialog_id}")
            logger.info(f"   📨 ID сообщения: {msg_id}")
            logger.info(f"   🔒 Доступ: только участники чата")
            logger.info(f"   📁 Папка чата: ID={chat_folder_id}")
            return True
        else:
            logger.error(f"❌ Не удалось отправить файл в чат {dialog_id}")
            error_msg = f"{caption}\n⚠️ Ошибка прикрепления файла"
            self.send_message(dialog_id, error_msg)
            return False

    def send_image_to_chat(self, dialog_id: str, image_bytes: BytesIO, filename: str, caption: str = '') -> bool:
        """
        Отправка изображения в чат (обёртка над send_file_to_chat)
        """
        return self.send_file_to_chat(dialog_id, image_bytes, filename, caption)


def generate_qr(data: str) -> BytesIO:
    """Генерация QR-кода в памяти для тестирования"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================
if __name__ == '__main__':
    # === НАСТРОЙКИ ===
    TEST_CHAT_ID = "chat81328"  # ID чата для тестирования

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕСТА Bitrix24ChatSafeSender v260211.09")
    print("   Использует im.disk.folder.get для получения папки чата")
    print("=" * 80 + "\n")

    # Получаем настройки из settings.py
    WEBHOOK_URL = settings.CONST_sender_bitrix24

    # Генерируем тестовое изображение
    print("🎨 Генерация тестового изображения (QR-код)...")
    image_data = generate_qr(data=f'chat-test-{int(time.time())}')
    image_size = image_data.getbuffer().nbytes
    print(f"✅ Изображение сгенерировано ({image_size} байт)")

    if image_size > 20 * 1024 * 1024:
        print("❌ Изображение превышает лимит 20 МБ")
        exit(1)

    # Создаём отправителя
    print("🔧 Создание экземпляра отправителя...")
    sender = Bitrix24ChatSafeSender(WEBHOOK_URL)
    print()

    # === ТЕСТ 1: Отправка текстового сообщения ===
    print("=" * 80)
    print("📝 ТЕСТ 1: Отправка текстового сообщения")
    print("=" * 80)

    text_success = sender.send_message(
        dialog_id=TEST_CHAT_ID,
        message="🚀 Тестовое сообщение из ChatSafeSender v260211.09\n✅ Скрипт использует im.disk.folder.get для получения папки чата"
    )

    if text_success:
        print("✅ ТЕСТ 1 ПРОЙДЕН: текстовое сообщение отправлено\n")
    else:
        print("❌ ТЕСТ 1 ПРОВАЛЕН: не удалось отправить текстовое сообщение\n")

    # === ТЕСТ 2: Получение папки чата ===
    print("=" * 80)
    print("📂 ТЕСТ 2: Получение папки чата через im.disk.folder.get")
    print("=" * 80)

    chat_folder_id = sender.get_chat_folder_id(TEST_CHAT_ID)

    if chat_folder_id:
        print(f"✅ ТЕСТ 2 ПРОЙДЕН: Папка чата получена, ID={chat_folder_id}\n")
    else:
        print("❌ ТЕСТ 2 ПРОВАЛЕН: Не удалось получить папку чата!")
        print("   Возможно, у вебхука нет прав на чтение папки чата")
        print("   Проверьте: im.disk.folder.get должен быть доступен\n")
        image_data.close()
        exit(1)

    # === ТЕСТ 3: Отправка изображения в чат ===
    print("=" * 80)
    print("🖼️  ТЕСТ 3: Отправка изображения в чат")
    print("=" * 80)

    timestamp = int(time.time())
    filename = f"chat_image_{timestamp}.png"
    caption = "✅ Изображение отправлено через im.disk.folder.get"

    success = sender.send_image_to_chat(
        dialog_id=TEST_CHAT_ID,
        image_bytes=image_data,
        filename=filename,
        caption=caption
    )

    print("\n" + "=" * 80)
    if success:
        print("✅✅✅ ТЕСТ 3 ПРОЙДЕН: Изображение успешно отправлено в чат!")
        print(f"\n   📁 Папка чата: ID={chat_folder_id}")
        print(f"   📄 Файл: {filename}")
        print(f"   👥 Доступ: Только участники чата")
        print(f"\n   🔍 Проверьте в Битрикс24:")
        print(f"      • Сообщение с изображением в чате {TEST_CHAT_ID}")
        print(f"      • Файл в разделе: Диск → Чаты → Ваш чат")
    else:
        print("❌❌❌ ТЕСТ 3 ПРОВАЛЕН: Не удалось отправить изображение")
        print("\n   🔍 Возможные причины:")
        print("      • Нет прав на запись в папку чата")
        print("      • Проблема с загрузкой файла")
        print("      • Ошибка прикрепления файла к сообщению")
    print("=" * 80 + "\n")

    # === ИТОГИ ===
    print("=" * 80)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    print(f"✅ Папка чата: {'ДОСТУПНА' if chat_folder_id else 'НЕ ДОСТУПНА'}")
    print(f"✅ Отправка текста: {'РАБОТАЕТ' if text_success else 'НЕ РАБОТАЕТ'}")
    print(f"✅ Отправка изображения: {'РАБОТАЕТ' if success else 'НЕ РАБОТАЕТ'}")
    print("\n💡 ДЛЯ ПРОДАКШЕНА:")
    print("   1. Все файлы автоматически загружаются в папку чата")
    print("   2. Права доступа управляются Битрикс24 автоматически")
    print("   3. Никакой дополнительной настройки прав не требуется")
    print("   4. Метод im.disk.folder.get РАБОТАЕТ с вебхуком")
    print("=" * 80)

    # Очистка ресурсов
    image_data.close()
    print("\n🏁 Тестирование завершено")