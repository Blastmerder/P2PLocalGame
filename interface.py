import curses
import time

# Имитация CRUD функций API
class ObjectAPI:
    @staticmethod
    def init_object(name):
        # API: Создание объекта (Create)
        return {"name": name, "status": "Active", "value": 0}

    @staticmethod
    def get_update(obj):
        # API: Получение свежих данных (Read/Update)
        obj["value"] += 1  # Просто меняем данные для видимости работы
        return obj

def main(stdscr):
    # Начальные настройки curses
    curses.curs_set(1)          # Показывать курсор при вводе
    stdscr.nodelay(True)        # Не блокировать программу в ожидании кнопок
    curses.cbreak()
    
    # Список наших объектов
    objects = [
        {"name": "Server_A", "status": "Active", "value": 10},
        {"name": "Server_B", "status": "Active", "value": 20}
    ]
    
    input_text = ""             # Здесь хранится вводимый текст
    last_update_time = time.time()

    while True:
        # 1. Получаем размеры терминала
        max_y, max_x = stdscr.getmaxyx()
        
        # Полностью очищаем экран перед перерисовкой
        stdscr.clear()
        
        # 2. Логика API: Обновление данных объектов раз в 1 секунду (GET/UPDATE)
        current_time = time.time()
        if current_time - last_update_time > 1.0:
            for obj in objects:
                obj = ObjectAPI.get_update(obj)
            last_update_time = current_time

        # 3. ОТРИСОВКА: Окна объектов (Верхняя часть)
        win_w = 25  # Ширина одного окошка
        win_h = 5   # Высота окошка
        
        for i, obj in enumerate(objects):
            # Считаем позицию для сетки окон
            cols = max(1, max_x // (win_w + 2))
            row = i // cols
            col = i % cols
            
            start_y = row * (win_h + 1)
            start_x = col * (win_w + 2)
            
            # Проверяем, влезает ли окно на экран
            if start_y + win_h < max_y - 4:
                # Создаем окно под объект
                win = curses.newwin(win_h, win_w, start_y, start_x)
                win.box()
                # Выводим поля объекта
                win.addstr(1, 2, f"Name: {obj['name']}")
                win.addstr(2, 2, f"Status: {obj['status']}")
                win.addstr(3, 2, f"Value: {obj['value']}")
                win.refresh()

        # 4. ОТРИСОВКА: Нижняя панель создания (Поле ввода)
        input_win_y = max_y - 3
        stdscr.hline(input_win_y - 1, 0, "-", max_x) # Разделительная линия
        stdscr.addstr(input_win_y, 2, f"Create new object (Enter name): {input_text}")
        stdscr.addstr(input_win_y + 1, 2, "[Press Enter to Save / Esc to Exit]")
        stdscr.refresh()

        # 5. ОБРАБОТКА ВВОДА (Чтение клавиатуры)
        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        if key == 27: # Клавиша Esc — выход из программы
            break
            
        elif key in (curses.KEY_ENTER, 10, 13): # Клавиша Enter — создание
            if input_text.strip():
                # Вызываем API функцию создания (INIT)
                new_obj = ObjectAPI.init_object(input_text.strip())
                objects.append(new_obj)
                input_text = "" # Очищаем поле ввода
                
        elif key in (curses.KEY_BACKSPACE, 127, 8): # Стирание символа
            input_text = input_text[:-1]
            
        elif 32 <= key <= 126: # Обычные печатные символы
            input_text += chr(key)

        # Небольшая пауза, чтобы не перегружать процессор
        time.sleep(0.05)

# Запуск приложения
curses.wrapper(main)

