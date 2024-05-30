import machine
import time
import onewire
import ds18x20
import utime
from machine import Pin
from machine import I2C
import ssd1306
import network
import uMQTT
# --- Инициализация пинов ---
# Вайфай и boot.py - считаем, что уже реализовано
# Датчики температуры DS18B20
onewire_bus = machine.Pin(4)  # Подключение к пину 4
ds = ds18x20.DS18X20(onewire.OneWire(onewire_bus))
roms = ds.scan()  # Считываем все адреса датчиков
# Матричная клавиатура 4x5
row_pins = [machine.Pin(12), machine.Pin(14), machine.Pin(27), machine.Pin(32), machine.Pin(33)]  # 5 строк
col_pins = [machine.Pin(26), machine.Pin(25), machine.Pin(35), machine.Pin(39)]  # 4 столбца
# Реле для клапана охлаждения
cool_valve_pin = machine.Pin(13, machine.Pin.OUT)
# Реле для клапана отбора
takeoff_valve_pin = machine.Pin(15, machine.Pin.OUT)
# Дисплей I2C
i2c = I2C(sda=machine.Pin(21), scl=machine.Pin(22))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)
# --- Параметры MQTT ---
MQTT_SERVER = "mqtt.example.com"  # Замените на ваш MQTT-сервер
MQTT_USER = "ваш_пользователь"  # Замените на ваш логин
MQTT_PASS = "ваш_пароль"  # Замените на ваш пароль
MQTT_TOPIC = "distillation_data"  # Замените на ваш топик
# --- Клиент MQTT ---
client = uMQTT.MQTTClient("ESP32", MQTT_SERVER, user=MQTT_USER, password=MQTT_PASS)
# --- Функции ---
def read_temp(rom):
    ds.convert_temp()
    time.sleep(0.75)
    return ds.read_temp(rom)
def read_matrix():
    key = 0
    for row in range(5):  # 5 строк
        row_pins[row].value(0)
        for col in range(4):
            if col_pins[col].value() == 0:
                key = (row * 4) + col + 1
        row_pins[row].value(1)
    return key
def display_info():
    oled.fill(0)
    oled.text("Cube:", 0, 0)
    oled.text(str(round(read_temp(roms[0]), 1)) + " C", 0, 10)
    oled.text("Defleg:", 0, 20)
    oled.text(str(round(read_temp(roms[1]), 1)) + " C", 0, 30)
    oled.text("Other:", 0, 40) 
    oled.text(str(round(read_temp(roms[2]), 1)) + " C", 0, 50) 
    oled.show()
def control_cool_valve(temp_threshold):
    if read_temp(roms[0]) >= temp_threshold:
        cool_valve_pin.value(1)  # Открываем клапан
    else:
        cool_valve_pin.value(0)  # Закрываем клапан
def control_takeoff_valve(temp_threshold):
    if read_temp(roms[1]) >= temp_threshold:
        takeoff_valve_pin.value(0)  # Закрываем клапан
    else:
        takeoff_valve_pin.value(1)  # Открываем клапан
def send_mqtt_data():
    cube_temp = read_temp(roms[0])
    defleg_temp = read_temp(roms[1])
    other_temp = read_temp(roms[2]) 
    data = f"Cube: {cube_temp:.1f} C, Defleg: {defleg_temp:.1f} C, Other: {other_temp:.1f} C" 
    client.publish(MQTT_TOPIC, data)
# --- Основной цикл ---
keys = [
    ['F1', 'F2', '#', '*'],
    ['1',  '2',  '3', '^'],
    ['4',  '5',  '6', 'v'],
    ['7',  '8',  '9', 'Esc'],
    ['<',  '0',  '>', 'Ent']
]
cool_valve_threshold = 80
takeoff_valve_threshold = 75
menu_mode = False
menu_item = 0
submenu_item = 0
while True:
    key = read_matrix()
    display_info()    # Обработка ключей
    # Входим в меню настроек при нажатии клавиши 'F1'
    if keys[0][0] == 'F1' and not menu_mode:
        menu_mode = True
        menu_item = 0
        submenu_item = 0
    # Выход из меню настроек
    elif keys[3][3] == 'Esc' and menu_mode:
        menu_mode = False
    # Навигация по пунктам меню
    elif menu_mode and keys[1][3] == '^':
        menu_item -= 1
        menu_item %= 2
    elif menu_mode and keys[3][3] == 'v':
        menu_item += 1
        menu_item %= 2
    # Навигация по подпунктам меню
    elif menu_mode and menu_item == 0 and keys[3][2] == '>':
        submenu_item += 1
        submenu_item %= 3
    elif menu_mode and menu_item == 0 and keys[3][0] == '<':
        submenu_item -= 1
        submenu_item %= 3
    elif menu_mode and menu_item == 1 and keys[3][2] == '>':
        submenu_item += 1
        submenu_item %= 2
    elif menu_mode and menu_item == 1 and keys[3][0] == '<':
        submenu_item -= 1
        submenu_item %= 2
    # Задаём значения порогов температур для клапанов
    elif menu_mode and menu_item == 0 and submenu_item == 0 and keys[0][3] == '*':
        cool_valve_threshold = 80  # Пример
        control_cool_valve(cool_valve_threshold)
    elif menu_mode and menu_item == 0 and submenu_item == 1 and keys[0][3] == '*':
        takeoff_valve_threshold = 75  # Пример
        control_takeoff_valve(takeoff_valve_threshold)
    # Запуск процесса дистилляции при нажатии 'Ent'
    elif keys[4][3] == 'Ent':
        # Запуск процесса дистилляции
        if menu_mode:
            # Проверяем, в каком пункте меню мы находимся:
            if menu_item == 0 and submenu_item == 0:
                # Настройка клапана охлаждения
                control_cool_valve(cool_valve_threshold)
            elif menu_item == 0 and submenu_item == 1:
                # Настройка клапана отвода
                control_takeoff_valve(takeoff_valve_threshold)
            elif menu_item == 1 and submenu_item == 0:
                # ... (Добавьте настройку 1)
            elif menu_item == 1 and submenu_item == 1:
                # ... (Добавьте настройку 2)
            menu_mode = False  # Выход из меню после настройки
        else:
            # Запускаем процесс дистилляции
            start_distillation()
    # Мониторинг (отправка данных в приложение)
    elif not menu_mode:
        send_mqtt_data()
    utime.sleep_ms(100) 
