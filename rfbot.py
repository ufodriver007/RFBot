"""
 RFBot v1.01 (relaxed fishing bot)
 simple bot for WoW fishing
"""

import threading
import os
import pyautogui
import cv2
import pyscreenshot as ImageGrab
import numpy as np
import time
import psutil
import tkinter
from tkinter import messagebox
import pyaudio
import audioop
import math
from collections import deque


try_to_stop = False                 # флаг для выхода из бесконечного цикла

screen_size = None                  # значение равное четверти разрешения
screen_start_point = None           # начальная точка области сканироания
screen_end_point = None             # конечная точка области сканироания

w = 0                               # ширина шаблона
h = 0                               # высота шаблона
tries = 0                           # попытки

deactivity = 0                      # счётчик не найденных поплавков
starttime = time.time()
starttime2 = time.time()

buff_interval = 603                             # использовать бафф каждые X сек.
buff2_interval = 3603                           # использовать бафф2 каждые X сек.
wow_process = "Wow-64_NoFileCheck.exe"          # название процесса для запуска скрипта
threshold = 0.6                                 # порог соответствия шаблона(0.6-0.8)
minpic_diff = 2.0                               # порог срабатывания подсекания (1-3)
is_buff_on = 0                                  # должен ли быть бафф
button_buff = '2'                               # кнопка баффа
button_buff2 = '3'                              # кнопка второго баффа
button_fishing = '1'                            # кнопка рыбалки
max_tries = 1000                                # макс. кол-во попыток до конца скрипта
deactive = 20                                   # кол-во необнаружений поплавка до выхода
minpic_size = 20                                # #отступ(размер) маленького скриншота(~20-25)
minpic_show = 1                                 # показывать маленький скриншот
algorithm = 'visual'                            # алгоритм, используемый для подсекания


def check_process() -> bool:
    """Проверка существования процесса игры"""
    write_to_log('Проверка процесса игры..')
    wow_process_names = [wow_process]
    running = False
    for pid in psutil.pids():
        p = psutil.Process(pid)
        if any(p.name() in s for s in wow_process_names):
            running = True
            return running
    if not running:
        write_to_log('WoW не запущен')
        return False
    else:
        write_to_log('WoW запущен')
        return True


def check_screen_size():
    """Проверить размер экрана и задать область для большого скриншота"""
    global screen_size
    global screen_start_point
    global screen_end_point

    write_to_log("Проверка размеров экрана")
    img = ImageGrab.grab()

    screen_size = [img.size[0] / 2, img.size[1] / 2]                     # screen_size = 960, 540
    screen_start_point = [screen_size[0] * 0.35, screen_size[1] * 0.35]  # 336, 189
    screen_end_point = [screen_size[0] * 0.65, screen_size[1] * 0.65]    # 624, 324

    write_to_log("Область сканирования определена")


def send_float():
    """Закинуть удочку"""
    write_to_log('Ловим...')
    pyautogui.press(button_fishing)
    time.sleep(2)


def make_screenshot() -> str:
    """Сделать большой скриншот"""
    global window
    global lbl_scan

    write_to_log('Захват экрана...')
    screenshot = ImageGrab.grab(bbox=(int(screen_start_point[0]), int(screen_start_point[1]), int(screen_end_point[0]), int(screen_end_point[1]))) # (0, 710, 410, 1010)
    screenshot_name = 'var/fishing_session.png'
    try:
        screenshot.save(screenshot_name)
    except Exception:
        tkinter.messagebox.showerror("Ошибка!", "Невозможно сохранить скриншот! Возможно нет папки var, или нет доступа к ней.")
        exit()

    # код обновления картинки
    scan = load_big_screenshot()
    lbl_scan.configure(image=scan)

    return screenshot_name


def find_float(img_name) -> tuple:
    """Найти маленький скриншот на большом"""
    global w
    global h
    # todo: сделать универсальный поплавок без фона?
    for x in range(0, 7):
        # загружаем шаблон
        template = cv2.imread('var/fishing_float_' + str(x) + '.png', 0)

        # загружаем скриншот и изменяем его на чернобелый
        # т.е. переводим в формат, который понимает opencv
        img_rgb = cv2.imread(img_name)
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

        # берем ширину и высоту шаблона
        # находим высоту и ширину скриншота
        try:
            w, h = template.shape[::-1]
        except Exception:
            tkinter.messagebox.showerror("Ошибка", "Невозможно прочитать шаблоны!")
            tkinter.messagebox.showinfo("Шаблоны", "Необходимо иметь в папке var - 8 файлов шаблонов. От fishing_float_0.png до fishing_float_7.png")

        # магия OpenCV, которая и находит наш темплейт на картинке
        res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)

        # понижаем порог соответствия нашего шаблона с 0.8 до 0.6, ибо поплавок шатается
        # и освещение в локациях иногда изменяет его цвета, но не советую ставить ниже,
        # а то и рыба будет похожа на поплавок

        # координаты где находится шаблон на базовом скриншоте
        loc = np.where(res >= threshold)

        # выводим результаты на картинку
        for pt in zip(*loc[::-1]):
            cv2.rectangle(img_rgb, pt, (pt[0] + w, pt[1] + h), (0, 0, 255), 2)

        # и если результаты всё же есть, то возвращаем координаты и сохраняем картинку
        if loc[0].any():
            return loc[1][0] + w / 2, loc[0][0] + h / 2


def move_mouse(place):
    """Переместить мышь на поплавок"""
    x, y = place[0], place[1]
    write_to_log("Перемещаем мышь " + str(place))
    pyautogui.moveTo(int(screen_start_point[0]) + x, int(screen_start_point[1]) + y)


def waiting(place):
    """Алгоритм определения момента для подсекания"""
    global w
    global h
    x = place[0]
    y = place[1]
    collect = []
    collect.clear()
    write_to_log('Отслеживаем движение поплавка...')

    #цикл определённое кол-во секунд
    t_end = time.time() + 17
    while time.time() < t_end:
        # маленький скриншот именно поплавка
        screenshot = ImageGrab.grab(bbox=(int(screen_start_point[0]) + int(x) - minpic_size, int(screen_start_point[1]) + int(y) - minpic_size, int(screen_start_point[0]) + int(x) + minpic_size, int(screen_start_point[1]) + int(y) + minpic_size))
        if minpic_show == 1:
            screenshot.save('var/float.png')

            # код обновления картинки на форме
            scan = load_big_screenshot()
            lbl_scan.configure(image=scan)
            floater = load_little_screenshot()
            lbl_floater.configure(image=floater)

        #извлечение признаков
        mean = np.mean(screenshot)

        #добавляем значение скриншота в лист
        collect.append(mean)

        #вычисляем разницу между средним листа и элементом
        difference = np.mean(collect) - mean

        # порог срабатывания подсекания
        if abs(difference) > minpic_diff:
            snatch()
            break

        # если после 10ти мини скриншотов
        # максимум и минимум коллекции слишком мал (нет разницы в мини скринах)
        if len(collect) > 10:
            slist = sorted(collect)
            slist_diff = abs(slist[-1]) - abs(slist[0])
            if slist_diff < 1:
                write_to_log('Похоже шаблон сопоставлен ошибочно...')
                break


def listening():
    write_to_log("Слушаем звук всплеска...")
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 2
    RATE = 18000  # битрейт звука, который мы хотим слушать
    THRESHOLD = 1200  # порог интенсивности звука, если интенсивность ниже, значит звук по нашим меркам слишком тихий
    SILENCE_LIMIT = 1  # длительность тишины, если мы не слышим ничего это время, то начинаем слушать заново

    # открываем стрим
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    # output=True,
                    input=True,
                    frames_per_buffer=CHUNK)
    rel = RATE / CHUNK
    slid_win = deque(maxlen=int(SILENCE_LIMIT * rel))

    # начинаем слушать и по истечении 20 секунд (столько максимум длится каждый заброс поплавка), отменяем
    listening_start_time = time.time()
    while True:
        try:
            cur_data = stream.read(CHUNK)
            slid_win.append(math.sqrt(abs(audioop.avg(cur_data, 4))))
            if sum([x > THRESHOLD for x in slid_win]) > 0:
                write_to_log("Всплеск был услышан...")
                snatch()
                break
            if time.time() - listening_start_time > 20:
                write_to_log("Ничего не было слышно...")
                break
        except IOError:
            break
    stream.close()
    p.terminate()


def snatch():
    """Поймать рыбу"""
    pyautogui.keyDown('shift')
    pyautogui.click()
    pyautogui.keyUp('shift')


def logout():
    """Выход из ВоВа"""
    pyautogui.press('enter')
    time.sleep(0.1)
    for c in u'/logout':
        time.sleep(0.1)
        pyautogui.press(c)
    time.sleep(0.1)

    pyautogui.press('enter')


def buff():
    """Бафф №1"""
    window.after(1000, pyautogui.press(button_buff))
    window.after(3000, write_to_log('Прожимаем бафф..'))


def buff2():
    """Бафф №2"""
    window.after(1000, pyautogui.press(button_buff2))
    window.after(3000, write_to_log('Прожимаем второй бафф..'))


def load_config():
    """Загрузка конфигурации"""
    global buff_interval
    global buff2_interval
    global wow_process
    global threshold
    global minpic_diff
    global is_buff_on
    global button_buff
    global button_buff2
    global button_fishing
    global max_tries
    global deactive
    global minpic_size
    global minpic_show
    global algorithm

    config = {}
    try:
        f = open('config.ini')
        for line in f:
            line = line[:-1]                   # удаляем 2 символа с конца /n
            li = list(line.split(' '))
            config[li[0]] = li[1]
        f.close()
    except Exception:
        tkinter.messagebox.showerror("Ошибка", "Невозможно прочитать файл настроек! Восстановлены значеня по умолчанию.")

    buff_interval = int(config['buff_interval'])
    buff2_interval = int(config['buff2_interval'])
    wow_process = config['wow_process']
    threshold = float(config['threshold'])
    minpic_diff = float(config['minpic_diff'])
    is_buff_on = int(config['is_buff_on'])
    button_buff = config['button_buff']
    button_buff2 = config['button_buff2']
    button_fishing = config['button_fishing']
    max_tries = int(config['max_tries'])
    deactive = int(config['deactive'])
    minpic_size = int(config['minpic_size'])
    minpic_show = int(config['minpic_show'])
    algorithm = config['algorithm']


def load_default_config():
    """Загрузка дефолтной конфигурации"""
    global buff_interval
    global buff2_interval
    global wow_process
    global threshold
    global minpic_diff
    global is_buff_on
    global button_buff
    global button_buff2
    global button_fishing
    global max_tries
    global deactive
    global minpic_size
    global minpic_show
    global algorithm

    buff_interval = 603
    buff2_interval = 3603
    wow_process = "Wow-64_NoFileCheck.exe"
    threshold = 0.6
    minpic_diff = 2.0
    is_buff_on = 0
    button_buff = '2'
    button_buff2 = '3'
    button_fishing = '1'
    max_tries = 2500
    deactive = 20
    minpic_size = 20
    minpic_show = 1
    algorithm = 'visual'


def save_config():
    """Сохранение конфигурации"""
    global buff_interval
    global buff2_interval
    global wow_process
    global threshold
    global minpic_diff
    global is_buff_on
    global button_buff
    global button_buff2
    global button_fishing
    global max_tries
    global deactive
    global minpic_size
    global minpic_show
    global algorithm

    try:
        buff_interval = int(buff_intr.get())
        buff2_interval = int(buff2_intr.get())
        threshold = float(threshold_txt.get())
        minpic_diff = minpic_diff_txt.get()
        is_buff_on = str(check_buff.get())
        button_buff = b_btn.get()
        button_buff2 = b2_btn.get()
        button_fishing = btn_f.get()
        max_tries = int(max_tries_int.get())
        deactive = int(deactive_txt.get())
        minpic_size = int(fl_size.get())
        algorithm = algorithm_tk.get()
        #minpic_show = str(show_fl.get())
    except Exception:
        messagebox.showerror("Ошибка", "Неверно получены данные!")
        return

    try:
        f = open('config.ini', 'w')
        f.write(f"buff_interval {buff_interval}" + '\n')
        f.write(f"buff2_interval {buff2_interval}" + '\n')
        f.write(f"wow_process {wow_process}" + '\n')
        f.write(f"threshold {threshold}" + '\n')
        f.write(f"minpic_diff {minpic_diff}" + '\n')
        f.write(f"is_buff_on {is_buff_on}" + '\n')
        f.write(f"button_buff {button_buff}" + '\n')
        f.write(f"button_buff2 {button_buff2}" + '\n')
        f.write(f"button_fishing {button_fishing}" + '\n')
        f.write(f"max_tries {max_tries}" + '\n')
        f.write(f"deactive {deactive}" + '\n')
        f.write(f"minpic_size {minpic_size}" + '\n')
        f.write(f"minpic_show {minpic_show}" + '\n')
        f.write(f"algorithm {algorithm}" + '\n')
        f.close()
    except Exception:
        messagebox.showerror("Ошибка", "Невозможно записать файл!")
    write_to_log('Конфигурация успешно сохранена')
    reload_config()


def main():
    if not check_process():
        btn_start.configure(state=tkinter.NORMAL)
        return

    write_to_log("Ждём 2 секунды, можно переключиться на WoW")
    window.after(2000, check_screen_size())
    write_to_log(f"Подсекание по {algorithm} алгоритму")

    # начальный бафф
    if is_buff_on == True:
        buff()
        buff2()

    # запускаем отдельным потоком main_loop()
    thr = threading.Thread(target=main_loop, name="loop")
    thr.start()


def main_loop():
    """Основной цикл рыбалки"""
    global try_to_stop
    global starttime
    global starttime2
    global deactivity
    global tries
    global algorithm

    while True:
        # Если флаг в True, останавливаем цикл
        if try_to_stop:
            write_to_log('Бот остановлен')
            try_to_stop = False
            btn_start.configure(state=tkinter.NORMAL)
            return

        # Если достигнуто максимальное число забросов
        if tries == max_tries:
            write_to_log('Максимальное число забросов')
            write_to_log('Бот остановлен')
            logout()
            exit()

        # Если не нашёл 20 раз подряд поплавок - выходим
        if deactivity == deactive:
            write_to_log(f'Поплавок не найден {deactivity} раз подряд')
            write_to_log('Бот остановлен')
            logout()
            btn_start.configure(state=tkinter.NORMAL)
            break

        # Если подошло время баффа - баффаем и обнуляем переменную времени
        if time.time() - starttime > buff_interval and is_buff_on:
            buff()
            starttime = time.time()

        # Если подошло время баффа 2 - баффаем и обнуляем переменную времени
        if time.time() - starttime2 > buff2_interval and is_buff_on:
            buff2()
            starttime2 = time.time()

        send_float()
        im = make_screenshot()
        place = find_float(im)
        tries += 1
        write_to_log(f'Попытка {tries}')

        # Если не пришли координаты поплавка
        if not place:
            write_to_log('Поплавок не найден, следующая попытка через 1 секунду...')
            deactivity += 1
            time.sleep(1)
            continue

        write_to_log('Поплавок найден на ' + str(place))
        deactivity = 0
        move_mouse(place)

        # условие, КОГДА нужно подсекать
        if algorithm == 'visual':
            waiting(place)
        else:
            listening()


def reload_config():
    """Прочитать конфигурацию"""
    try:
        load_config()
        write_to_log('Конфигурация загружена')
    except Exception:
        load_default_config()
        write_to_log('Не прочитан файл конфигурации')
        write_to_log('Все значения по умолчанию')


def start():
    """Начало рыбалки"""
    global tries
    global deactivity
    global starttime
    global starttime2

    btn_start.configure(state=tkinter.DISABLED)

    starttime = time.time()
    starttime2 = time.time()
    deactivity = 0
    tries = 0
    reload_config()
    main()


def stop():
    """Остановка второго потока(с основным циклом)"""
    global try_to_stop
    write_to_log('Попытка остановить поток...')
    try_to_stop = True


def write_to_log(msg):
    """Запись в окно лога"""
    numlines = int(log.index('end - 1 line').split('.')[0])
    log['state'] = 'normal'
    if numlines == 8:
        log.delete(1.0, 2.0)
    if log.index('end-1c') != '1.0':
        log.insert('end', '\n')
    log.insert('end', msg)
    log['state'] = 'disabled'


def load_big_screenshot() -> str:
    """Сохранить большой скриншот"""
    try:
        scan = tkinter.PhotoImage(file='var/fishing_session.png')
    except Exception:
        scan = tkinter.PhotoImage(file='')
    finally:
        return scan


def load_little_screenshot() -> str:
    """Сохранить маленький скриншот"""
    try:
        floater = tkinter.PhotoImage(file='var/float.png')
    except Exception:
        floater = tkinter.PhotoImage(file='')
    finally:
        return floater


def options():
    '''Справка по настройкам'''
    top = tkinter.Toplevel(window)

    top.title("Справка по настройкам")
    top.geometry('800x620+550+250')
    top.resizable(0, 0)

    opt = tkinter.PhotoImage(file='icon.png')
    top.iconphoto(False, photo)

    lb = tkinter.Label(top, text='''
    -=КРАТКАЯ ИНСТРУКЦИЯ=-
    1.Создаём шаблон поплавка под своё место рыбалки.
    2.Помещаем шаблон в папку var и именуем fishing_float_0.png с нумерацией от 0 до 7
    3.Запускаем ВоВ в окне 800x600 или около того. Помещаем окно в левый верхний угол.
    4.Подводим персонажа к месту рыбалки. Вид от первого лица, максимальный зум на поплавок.
    5.Запускаем программу бота. Нажимаем "Запустить" и сразу же переходим в окно игры.
    6.Программа перехватит управление и будет методами компьютерного зрения пытаться 
       обнаружить в области сканирования поплавок по вашему шаблону.

    -=ШАБЛОН=-
    Создаётся очень просто и легко. Запускаете ВоВ в подготовленном окне. Находите место
    для рыбалки. Максимальный зум на поплавок. Делаете скриншот. Далее потребуется Photoshop
    или другой редактор изображений. Создаём новый документ из буфера обмена -> 
    тыкаем по холсту и Ctrl + V -> инструмент выделения прямоугольная область ->
    выделяем поплавок, стараясь не трогать лишнего, Ctrl + X -> Файл-Создать-Из 
    буфера обмена -> тыкаем по холсту и Ctrl + V -> Файл-Экспортировать-быстрый
    экспорт в PNG. Называем в соответственно(fishing_float_0.png и т.д.) 

    -=НАСТРОЙКИ=-
    Настройки по умолчанию достаточно хороши и хорошая работа программы в основном
    зависит только от места рыбалки(желательно однообразное без посторонних объектов)
     и качества шаблона.

     Размер картинки - размер мини скриншотов конкретно поплавка. Делаем максимально
          малый размер ~20px
     Использовать итем - будет ли бот использовать какую-то вещь или заклинание
     Кнопка итема - собственно кнопка, по которй он будет прожимать
     Прожимать каждые(сек) - интервал применения итема/заклинания
     Имя процесса - Имя exe'шника ВоВ, которое бот будет искать в процессах
     Кнопка рыбалки - кнопка, на которую в ВоВ назначена рыбалка
     Порог нахождения поплавка - коэффициент сравнения области сканирования и шаблона.
          Задаётся в пределах 0.6 - 0.8.
     Порог подсекания - Значение, определяющее на сколько отличается колыхнувшийся
          поплавок от спокойного. Задаётся в пределах 1.6 - 3
     Максимум забросов - Максимальное количество забросов, после чего выйдет из игры и 
          завершит программу
     Ненахождений поплавка до выхода - Сколько раз подряд бот не найдёт поплавок, после
          чего выйдет из игры и завершит программу
     Алгоритм подсекания - выбор одного из двух алгоритмов для определния момента
          подсекания. Визуальный(методами компьютерного зрения) или аудиальный(по звуку)
    ''', font=('Consolas', 9), bg='gray', justify=tkinter.LEFT)
    lb.pack(expand=True, fill=tkinter.BOTH)

    top.transient(window)
    # мы передаем поток данному виджету т.е. делаем его модальным
    top.grab_set()
    # фокусируем наше приложение на окне top
    top.focus_set()
    # мы задаем приложению команду, что пока не будет закрыто окно top пользоваться другим окном будет нельзя
    top.wait_window()


window = tkinter.Tk()
window.title("RFBot v1.00")
window.geometry("440x570+850+250")
window.resizable(0, 0)
photo = tkinter.PhotoImage(file='icon.png')
window.iconphoto(False, photo)

log = tkinter.Text(window, state='disabled', height=8, width=52, bg='gray', wrap='none', font=("Consolas", 10))
log.place(x=10, y=420)

check_buff = tkinter.IntVar()
b_btn = tkinter.StringVar()
b2_btn = tkinter.StringVar()
buff_intr = tkinter.StringVar()
buff2_intr = tkinter.StringVar()
# show_fl = tkinter.IntVar()
fl_size = tkinter.StringVar()
prc_name = tkinter.StringVar()
btn_f = tkinter.StringVar()
threshold_txt = tkinter.StringVar()
minpic_diff_txt = tkinter.StringVar()
max_tries_int = tkinter.StringVar()
deactive_txt = tkinter.StringVar()
algorithm_tk = tkinter.StringVar()


# начальная загрузка значений в форму
try:
    load_config()
except Exception:
    load_default_config()

# проверка шаблонов
try:
    dirname = "var/"
    files = os.listdir(dirname)
    tmplts = ['fishing_float_0.png', 'fishing_float_1.png', 'fishing_float_2.png', 'fishing_float_3.png', 'fishing_float_4.png', 'fishing_float_5.png', 'fishing_float_6.png', 'fishing_float_7.png']
    if not (all(x in files for x in tmplts)):
        tkinter.messagebox.showerror("Ошибка", "Не хватает шаблонов!")
        tkinter.messagebox.showinfo("Шаблоны", "Необходимо иметь в папке var - 8 файлов шаблонов. От fishing_float_0.png до fishing_float_7.png")
        exit()
except Exception:
    tkinter.messagebox.showerror("Ошибка", "Невозможно прочитать шаблоны!")
    tkinter.messagebox.showinfo("Шаблоны", "Необходимо иметь в папке var - 8 файлов шаблонов. От fishing_float_0.png до fishing_float_7.png")
    exit()

btn_start = tkinter.Button(window, text=" Запустить ", font=("Consolas", 10), command=start)
btn_start.place(x=10, y=5)
btn_stop = tkinter.Button(window, text="   Стоп    ", font=("Consolas", 10), command=stop)
btn_stop.place(x=10, y=40)
btn_save = tkinter.Button(window, text=" Сохранить ", font=("Consolas", 10), command=save_config)
btn_save.place(x=10, y=75)


# начальная загрузка картинок в форму
scan = load_big_screenshot()
if int(minpic_show) == 1:
    floater = load_little_screenshot()
else:
    floater = tkinter.PhotoImage(file='')


lbl_floater = tkinter.Label(window, text="", image=floater)
lbl_floater.place(x=45, y=125)
lbl_scan = tkinter.Label(window, text="", image=scan)
lbl_scan.place(x=140, y=25)

lbl_scan_text = tkinter.Label(window, text="Область сканирования")
lbl_scan_text.place(x=210, y=5)


lbl_scan_text = tkinter.Label(window, text="Размер картинки", font=('Consolas', 9))
lbl_scan_text.place(x=5, y=175)
fl_sz = tkinter.Entry(textvariable=fl_size, width=3, font=('Consolas', 9))
fl_sz.place(x=110, y=175)
fl_sz.insert(0, minpic_size)

#chFl = Checkbutton(window, text="Показать картинку", variable=show_fl)
#chFl.place(x=5, y=210)
#show_fl.set(minpic_show)

chBuff = tkinter.Checkbutton(window, text="Использовать итем", font=('Consolas', 9), variable=check_buff)
chBuff.place(x=5, y=205)
check_buff.set(is_buff_on)

lbl_item_btn = tkinter.Label(window, text="Кнопка итема", font=('Consolas', 9))
lbl_item_btn.place(x=5, y=225)
entr_item_btn = tkinter.Entry(textvariable=b_btn, width=4, font=('Consolas', 9))
entr_item_btn.place(x=175, y=225)
entr_item_btn.insert(0, button_buff)

lbl_item_interval = tkinter.Label(window, text="Прожимать каждые(сек)", font=('Consolas', 9))
lbl_item_interval.place(x=5, y=255)
entr_item_interval = tkinter.Entry(textvariable=buff_intr, width=4, font=('Consolas', 9))
entr_item_interval.place(x=175, y=255)
entr_item_interval.insert(0, buff_interval)

lbl_item2_btn = tkinter.Label(window, text="Кнопка второго итема", font=('Consolas', 9))
lbl_item2_btn.place(x=5, y=285)
entr_item2_btn = tkinter.Entry(textvariable=b2_btn, width=4, font=('Consolas', 9))
entr_item2_btn.place(x=175, y=285)
entr_item2_btn.insert(0, button_buff2)

lbl_item2_interval = tkinter.Label(window, text="Прожимать каждые(сек)", font=('Consolas', 9))
lbl_item2_interval.place(x=5, y=315)
entr_item2_interval = tkinter.Entry(textvariable=buff2_intr, width=4, font=('Consolas', 9))
entr_item2_interval.place(x=175, y=315)
entr_item2_interval.insert(0, buff2_interval)

# основной блок

lbl_process = tkinter.Label(window, text="Имя процесса", font=('Consolas', 9))
lbl_process.place(x=220, y=195)
entr_process = tkinter.Entry(textvariable=prc_name, width=16, font=('Consolas', 9))
entr_process.place(x=310, y=195)
entr_process.insert(0, wow_process)

lbl_fishing = tkinter.Label(window, text="Кнопка рыбалки", font=('Consolas', 9))
lbl_fishing.place(x=220, y=225)
entr_fishing = tkinter.Entry(textvariable=btn_f, width=4, font=('Consolas', 9))
entr_fishing.place(x=395, y=225)
entr_fishing.insert(0, button_fishing)

lbl_threshold = tkinter.Label(window, text="Порог нахождения поплавка", font=('Consolas', 9))
lbl_threshold.place(x=220, y=255)
entr_threshold = tkinter.Entry(textvariable=threshold_txt, width=4, font=('Consolas', 9))
entr_threshold.place(x=395, y=255)
entr_threshold.insert(0, threshold)

lbl_minpic_diff = tkinter.Label(window, text="Порог подсекания", font=('Consolas', 9))
lbl_minpic_diff.place(x=220, y=285)
entr_minpic_diff = tkinter.Entry(textvariable=minpic_diff_txt, width=4, font=('Consolas', 9))
entr_minpic_diff.place(x=395, y=285)
entr_minpic_diff.insert(0, minpic_diff)

lbl_max_tries = tkinter.Label(window, text="Максимум забросов", font=('Consolas', 9))
lbl_max_tries.place(x=220, y=315)
entr_max_tries = tkinter.Entry(textvariable=max_tries_int, width=4, font=('Consolas', 9))
entr_max_tries.place(x=395, y=315)
entr_max_tries.insert(0, max_tries)

lbl_deactive = tkinter.Label(window, text="Ненахождений поплавка до выхода", font=('Consolas', 9))
lbl_deactive.place(x=5, y=345)
entr_deactive = tkinter.Entry(textvariable=deactive_txt, width=4, font=('Consolas', 9))
entr_deactive.place(x=230, y=345)
entr_deactive.insert(0, deactive)


lbl_algorithm_text = tkinter.Label(window, text="Алгоритм подсекания", font=('Consolas', 9))
lbl_algorithm_text.place(x=65, y=370)
alg_01 = tkinter.Radiobutton(window, text="Визуальный", variable=algorithm_tk, value='visual', font=('Consolas', 9))
alg_01.place(x=5, y=390)
alg_02 = tkinter.Radiobutton(window, text="Аудиальный", variable=algorithm_tk, value='audio', font=('Consolas', 9))
alg_02.place(x=150, y=390)
algorithm_tk.set(algorithm)

# Creating Menubar
menubar = tkinter.Menu(window)
# Adding File Menu and commands
file = tkinter.Menu(menubar, tearoff=0)
menubar.add_cascade(label='Справка', font=('Consolas', 9), menu=file)
file.add_command(label='Настройки', font=('Consolas', 9), command=options)

window.config(menu=menubar)

write_to_log('RFBot v1.01')
write_to_log('Готов к работе...')
write_to_log('=================>')
write_to_log('Нaжмите "Запустить" и перейдите в окно WoW...')

window.mainloop()
