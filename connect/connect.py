import hashlib
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import threading
import json
import colorama
from colorama import init, Fore
import time
import os

init = init()

print(Fore.RED + "                        ______                          _____   _____    ____    _____  ______  _____  ")
time.sleep(0.2)
print(Fore.RED + "                        |___  /                         |  __ \ |  __ \  / __ \  / ____||  ____||  __ \ ")
time.sleep(0.2)
print(Fore.RED + "                           / /   ___    ___   _ __ ___  | |  | || |  | || |  | || (___  | |__   | |__) |")
time.sleep(0.2)
print(Fore.RED + "                          / /   / _ \  / _ \ | '_ ` _ \ | |  | || |  | || |  | | \___ \ |  __|  |  _  / ")
time.sleep(0.2)
print(Fore.RED + "                         / /__ | (_) || (_) || | | | | || |__| || |__| || |__| | ____) || |____ | | \ \ ")
time.sleep(0.2)
print(Fore.RED + "                        /_____| \___/  \___/ |_| |_| |_||_____/ |_____/  \____/ |_____/ |______||_|  \_|")
time.sleep(1.5)
print(Fore.RED + "")

leave_url = "http://localhost:3000"
default_role = 0

class ConRecord:
    def __init__(self, meet_num, meet_pass, date, time, duration, user_name, user_email):
        self.NumberMeet = meet_num
        self.PasswordMeet = meet_pass
        self.Date = date
        self.Time = time
        self.Duration = duration
        self.UserName = user_name
        self.UserEmail = user_email

    def as_sha256(self):
        data = f"{self.NumberMeet}{self.PasswordMeet}{self.Date}{self.Time}{self.Duration}{self.UserName}{self.UserEmail}"
        sha = hashlib.sha256()
        sha.update(data.encode('utf-8'))
        return sha.hexdigest()

class Config:
    def __init__(self, connections):
        self.Connections = connections

class TimeData:
    def __init__(self, hour, minute, second):
        self.hour = hour
        self.minute = minute
        self.second = second

class DateData:
    def __init__(self, day, month):
        self.day = day
        self.month = month

class JobTicker:
    def __init__(self):
        self.timer = None

    def set_timer(self, dd, td):
        now = time.localtime()
        next_tick = time.mktime(time.struct_time((now.tm_year, dd.month, dd.day, td.hour, td.minute, td.second, 0, 0, -1)))
        if next_tick <= time.mktime(now):
            raise Exception("Не удается присоединиться к совещанию в прошлом")
        diff = next_tick - time.mktime(now)
        if self.timer is None:
            self.timer = threading.Timer(diff, self._timer_callback)
            self.timer.start()
        else:
            self.timer.cancel()
            self.timer = threading.Timer(diff, self._timer_callback)
            self.timer.start()

    def _timer_callback(self):
        pass

def is_start_outdated(r):
    td, dd = parse_start_time(r.Time), parse_start_date(r.Date)
    start = time.struct_time((time.localtime().tm_year, dd.month, dd.day, td.hour, td.minute, td.second, 0, 0, -1))
    if start > time.localtime():
        return False
    print(f"Время начало конференции {r.NumberMeet} уже прошло")
    return True

def make_call_string(data):
    return f"""
        window.meetingNumber = "{data.NumberMeet}";
        window.meetingPassword = "{data.PasswordMeet}";
        window.meetingRole = {default_role};
        window.userName = "{data.UserName}";
        window.userEmail = "{data.UserEmail}";
        window.leaveUrl = "{leave_url}";
    """

def set_meeting_params_tsk(call_string):
    return [
        lambda driver: driver.execute_script(call_string)
    ]

def click_join_btn_tsk():
    return [
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "join-meeting-button"))),
        lambda driver: driver.find_element(By.ID, "join-meeting-button").click(),
        time.sleep(5)
    ]

def navigate_to_page(driver, url):
    driver.get(url)

def string_to_int(s):
    try:
        return int(s)
    except ValueError:
        print("Не удалось проанализировать временную строку.")
        return 0

def parse_start_time(time_str):
    parts = time_str.split(":")
    h = string_to_int(parts[0])
    m = string_to_int(parts[1])
    s = string_to_int(parts[2])
    return TimeData(h, m, s)

def parse_start_date(date_str):
    parts = date_str.split(".")
    d = string_to_int(parts[0])
    m = string_to_int(parts[1])
    return DateData(d, m)

def parse_duration(dur_str):
    m = string_to_int(dur_str)
    return time.timedelta(minutes=m)

def join_meeting(con_data):
    try:
        dur = parse_duration(con_data.Duration)
        s_time = parse_start_time(con_data.Time)
        s_date = parse_start_date(con_data.Date)

        print(f"{con_data.UserName} сможет зайти на {con_data.NumberMeet} в {s_time.hour}:{s_time.minute}:{s_time.second}")

        t = JobTicker()
        t.set_timer(s_date, s_time)
        t.timer.join()

        print(f"{con_data.UserName} присоединился к {con_data.NumberMeet} на {con_data.Duration} минут")

        navigate_to_page(driver, leave_url)
        call_string = make_call_string(con_data)
        driver.execute_script(call_string)
        click_join_btn_tsk()
        time.sleep(dur.total_seconds() / 60)

    except Exception as e:
        print(f"Error joining meeting {con_data.NumberMeet}: {str(e)}")

def get_cfg():
    try:
        with open('config.json') as config_file:
            data = json.load(config_file)
            return Config([ConRecord(c['NumberMeet'], c['PasswordMeet'], c['Date'], c['Time'], c['Duration'], c['UserName'], c['UserEmail']) for c in data['Connections']])
    except FileNotFoundError:
        print("Конфиг файл не найден.")
        exit(1)

def is_pending(c):
    with pending_lock:
        if c.as_sha256() in pending:
            print(f"Подключение уже ожидает (ник: {c.UserName} встреча: {c.NumberMeet})")
            return True
    return False

def init_new_cons(cfg):
    for con in cfg.Connections:
        if not is_start_outdated(con) and not is_pending(con):
            pending_lock.acquire()
            pending.add(con.as_sha256())
            pending_lock.release()
            threading.Thread(target=join_meeting, args=(con,)).start()

if __name__ == "__main__":
    pending = set()
    pending_lock = threading.Lock()
    driver = webdriver.Chrome()

    try:
        cfg = get_cfg()
        init_new_cons(cfg)
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        driver.quit()
