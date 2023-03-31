#!/bin/bash
#cd .\

#pipenv run jupyter notebook --generate-config
pipenv run jupyter notebook --ip 0.0.0.0 --port 8882

# Инструкция по установке и запуску Jupiter
# Допустим, у вас уже есть правильная среда Python в вашей системе, и теперь вы хотите создать конкретную среду для проекта.
#   Во-первых, создайте среду Pipenv.
#   Обязательно перейдите в правильный каталог.
#   pipenv install <packages> - чтобы установить все нужные пакеты.
#   pipenv shell - активировать вашу оболочку.
#   pipenv install jupyter - чтобы инсталлировать юпитер и после этого pipenv run jupyter notebook,
# Теперь сервер Jupyter запущен, и у вашего ноутбука будет доступ к правильной среде.
#
# Чтобы узнать токены уже запущенных jupyter-ов в каталоге проекта выполняем команды: 
#  pipenv shell
#  jupyter notebook list

