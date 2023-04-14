# email2forward

Email to Forward: получает email, парсит его и отправляет содержимое письма в мессенджеры.


### Кратко о том как устроена работа email2forward

email2forward запускается по настроенному графику и подключается к указанному почтовому ящику, читает еще непрочитанные письма, парсит их и переотправляет в указанные мессенджеры.

Поддерживаются мессенджеры:
- telegram
- bitrix24 (только текст)


### Правила формирования письма, которое нужно переотправить

В ТЕМЕ письма указать json (до 80 символов точно сработает, если больше, то проверяйте не обрежет ли ваш почтовый ящик):

```
{"date":"2023-03-14","time":"09:00","send":"tmp","telegram":"id_группы","bitrix24":"id_группы","title":"Заголовок сообщения ТЕСТОВЫЙ","only_with_word_in_pic":"warning","only_with_color_in_pic":"red"}

Примеры:
{"time":"09:00","send":"p","telegram":"id_группы"}
{"telegram":"id_группы","title":"Заголовок сообщения ТЕСТОВЫЙ"}
{"telegram":"id_группы","only_with_word_in_pic":"warning"}
{"telegram":"id_группы","only_with_color_in_pic":"red"}
```

- date и time можно использовать для отложенной отправки
- date - ДАТА (год-месяц-число), начиная с которой можно отправлять (если не указано, то в любую дату)
- time - ВРЕМЯ (час:мин), начиная с которого можно отправлять (если не указано, то в любое время)
```
Примеры:
* если не указаны date и time, то будет отправлено в любое время при первой обработке скриптом
* "date":"2023-03-14","time":"09:00" - будет отправлено после наступления 2023-03-14 09:00
* "date":"2023-03-14" - будет отправлено в любое время, но не раньше 2023-03-14
* "time":"09:00" - будет отправлено в любую дату, но не раньше 09:00
```

- send - что отправлять:
  - t = title (заголовок из поля "title")
  - m = message (весь текст из письма)
  - p = pictures (все картинки из письма)
  - пусто или нет параметра = только title (если он заполнен)
  - порядок и значения любые (примеры: "send":"mp", "send":"tmp", "send":"", "send":"m")
- telegram - id группы, в которую должно быть отправлено
  - Как узнать идентификатор группы telegram:
    - Добавить бота в нужную группу;
    - Написать хотя бы одно сообщение в неё (от любого пользователя);
    - Отправить GET-запрос по следующему адресу: https://api.telegram.org/bot<your_bot_token>/getUpdates
    - Взять значение "id" из объекта "chat". Это и есть идентификатор чата. Для групповых чатов он отрицательный, для личных переписок положительный. 
- bitrix24 - id группы, в которую должно быть отправлено
  - Как узнать идентификатор группы bitrix24:
    - /getDialogId – написать это в чат и получим идентификатор данного чата для внешних интеграций
- only_with_word_in_pic - будут отправлены картинки, на которых изображено указанное в этом поле слово (только ЛАТИНСКИЕ буквы + обратите внимание на РЕГИСТР!)
  - для лучшего распознавания слово должно быть написано контрастным цветом (черным по белому), не очень мелко, читабельным шрифтом (arial)
  - написано может быть в любой части картинки
- only_with_color_in_pic - будут отправлены картинки, на которых есть цветное пятно/пятна указанного цвета (включая оттенки)
  - удобно использовать при выделении "отклонений" цветом
  - возможные значения: black, white, red, green, blue, yellow, purple, orange, gray



В ТЕЛЕ письма можно разместить текст:

```
Текст из тела письма будет отправлен в указанный мессенджер 
```

*ВНИМАНИЕ! Текст перед отправкой будет обрезан до 3000 символов!*

В письмо можно добавить КАРТИНКИ (прямо в теле письма или приложением) в формате png/jpg/jpeg - они будут отправлены

*ВНИМАНИЕ! Всё остальное содержимое письма будет проигнорировано.*



### Установка email2forward (выполняем пошагово)

- Для работы потребуется Linux (тестирование проводилось на ubuntu 22.04.01). При необходимости переписать под windows, вероятно, вам не составит большого труда.

*ВНИМАНИЕ! Пути до каталогов и файлов везде указывайте свои!*

- Устанавливаем python (тестирование данной инструкции проводилось на 3.10, на остальных версиях работу не гарантирую, но должно работать на версиях 3.9+, если
  вам потребуется, то без особенного труда сможете переписать даже под 2.7)
- Устанавливаем pip:

```sudo apt install python3-pip```

- Далее устанавливаем pipenv (на linux):

```pip3 install pipenv```

- Создаем нужный каталог в нужном нам месте
- Копируем в этот каталог файлы проекта https://github.com/dneupokoev/email2forward
- Заходим в созданный каталог и создаем в нем пустой каталог .venv
- В каталоге проекта выполняем команды (либо иным способом устанавливаем пакеты из requirements.txt):

```pipenv shell```

```pipenv sync```

- Редактируем и переименовываем файл _settings.py (описание внутри файла)
- Настраиваем регулярное выполнение (например, через cron) скрипта ```email2forward.py``` или запускать вручную ```email2forward_start.sh```


### Дополнительно

- Обратите внимание на описание внутри _settings.py - там все настройки
- Если работает экземпляр программы, то второй экземпляр запускаться не будет (отслеживается через создание и проверку наличия файла)
- Записывается лог ошибок (настраивается в settings, рекомендуется сюда: /var/log/email2forward/)



### Добавления задания в cron

Смотрим какие задания уже созданы для данного пользователя:

```crontab -l```

Открываем файл для создания задания:

```crontab -e```

Каждая задача формируется следующим образом (для любого значения нужно использовать звездочку "*"):

```минута(0-59) час(0-23) день(1-31) месяц(1-12) день_недели(0-7) /полный/путь/к/команде```

Чтобы email2forward запускался каждый час ровно в 7 минут, создаем строку и сохраняем файл:

```7 */1 * * * /opt/dix/email2forward/email2forward_cron.sh```

ВНИМАНИЕ!!! отредактируйте содержимое файла email2forward_cron.sh и сделайте его исполняемым



### Возможные проблемы и их решение

- Для распознавания текста на картинках используется библиотека Tesseract https://github.com/tesseract-ocr/tesseract, здесь описано как ее установить: https://tesseract-ocr.github.io/tessdoc/Installation.html
- Письма могут попадать в спам! Имейте это ввиду и обеспечьте, чтобы с нужных адресов письма не попадали в спам.
- Картинки в bitrix24 пока отправлять НЕ УМЕЕТ!!!



### Версии

230414.01:
- добавлено распознавание "цветного пятна" на картинках: если пятно/пятна указанного цвета (включая оттенки), то данная картинка будет отправлена. Возможные значения: black, white, red, green, blue, yellow, purple, orange, gray

230411.01:
- добавлено распознавание текста на картинках и если есть "нужное" слово (только ЛАТИНСКИЕ буквы), то данная картинка будет отправлена.

230331.01:
- базовая стабильная версия (полностью протестированная и отлаженная)
