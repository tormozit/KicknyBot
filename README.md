Этот Telegram бот на русском языке позволяет наказывать пользователя временным запретом писать или баном навсегда через голосование с возможностью отмены.
Ответьте на сообщение пользователя строкой @KicknyBot для начала голосования за его наказание.

![изображение](https://github.com/user-attachments/assets/97306939-1176-4352-9332-c4c5decb25bb)

Написан через ИИ DeepSeek V3 примерным запросом:

Телеграм бот на языке python для голосования за бан пользователя с возможность отменить голосование и вариантами "Читатель 24ч", "Бан навегда", "Простить".
Голосование начинается путем ответа на сообщение пользователя с указанием @<ИмяБота>. Если принятое решение не "Простить", то сообщение, ответом на которое начато голосование, удаляется.
В сообщении о результате голосования должны быть перечислены через запятую все проголосовавшие за принятое решение участники и их количество.
Каждое упоминание пользователя должно быть обозначено гиперссылкой с текстом его полного имени и ссылкой на его профиль.
Отменить голосование может только инициатор. Пользователю запрещено начинать голосование против себя и принимать участие в голосовании, начатого против него.
Должен иметь команду администратора "VotesLimit" для установки числа голосов для принятия решения. 
Должен иметь команду администратора "VotesMonoLimit" для установки числа голосов для принятия решения единогласно.
Должен иметь команду администратора "TimeLimit" для установки максимальной длительности в минутах сбора голосов.
Должен иметь команду "Help" для вывода справки по командам.
При нажатии кнопки голосования вставь в начало ее текста символ "+", а у других кнопок удали его.
Число голосов по каждому варианту отображалось в формате: если нет голосов за другие варианты, то "<Голосов>/<Необходимо голосов единогласно>", иначе "<Голосов>/<Необходимо голосов>".

Для запуска скрипта требуется 
1. Установить python 3.7+
2. Установить библиотеку интеграции с Telegram командой "pip install python-telegram-bot"
3. Запустить бота (Run.Bat на ОС Windows)