import time
from collections import OrderedDict
from gc import collect

collect()

DISCONNECTED: int = 1
CONNECTED: int = 2
CHARGING: int = 3

MAX_SESSION_COUNT: int = 20


class History:
    NEW: int = 1
    NEW_SAME: int = 2

    def __init__(self, wattmeter, evse, rfid, config):
        self.wattmeter = wattmeter
        self.evse = evse
        self.rfid = rfid
        self.config = config
        self.sessions = Datalayer()
        self.last_evse_state: int = 0
        self.session = OrderedDict()
        self.session["USER"] = "0"
        self.session["energy"]: int = 0  # kWh
        self.session["time"]: str = 0  # format DD, MM, RR, HH:MM
        self.sessions.data["history"] = [self.session]  # list jednotlivich session
        self.time: dict = {"TIME": 0}
        self.session_start = OrderedDict()  # slovnik posledni session to se predela do tridy
        self.session_start["USER"]: str = "Anonym"
        self.session_start["energy"]: int = 0  # kWh
        self.session_start["time"]: str = ''  # format DD, MM, RR, HH:MM
        self.energy: int = 0
        self.evse_states: list = [0, 0, 0]  # fronta 3 poslednich stavu

        self.ready_clear_session: int = 0  # flag aby se nulovani seassion provedlo jen 1x

        self.counter: int = 0
        self.file_path: str = "charging_history.dat"
        self.create_file(self.file_path)
        self.sessions.data["history"] = self.read_data(self.file_path)

    def run_history_handler(self) -> None:
        if self.config.flash["sw,RFID VERIFICATION"] == '1':
            if self.evse.data_layer.data["EV_STATE"] == CONNECTED:
                if self.rfid.status == History.NEW or self.rfid.status == History.NEW_SAME:
                    self.config.ram['RFID_VERIFY'] = 1
                    self.evse.data_layer.data["USER"]: str = self.rfid.last_loaded_user.user["NAME"]
                    self.rfid.status = 0

            if self.evse.data_layer.data["EV_STATE"] == DISCONNECTED:
                self.config.ram['RFID_VERIFY'] = 0
                self.evse.data_layer.data["USER"] = "_"
                self.evse.data_layer.data["SESSION_ENERGY"] = 0
                self.evse.data_layer.data["DURATION"] = 0
                self.rfid.last_id = "0"
                self.rfid.status = 0

            if self.rfid.status == History.NEW_SAME and self.evse.data_layer.data["EV_STATE"] == CHARGING:
                self.config.ram['RFID_VERIFY'] = 0
                self.rfid.status = 0
        else:
            self.evse.data_layer.data["USER"]: str = "anonym"

        now: tuple = time.localtime()
        year_02: str = str(now[0])[-2:]
        self.time['TIME'] = ("{0:02}.{1:02}.{2} {3:02}:{4:02}".format(now[2], now[1], year_02, now[3], now[4]))
        energy_temp: int = self.wattmeter.data_layer.data["E1tP"] + self.wattmeter.data_layer.data["E2tP"] + self.wattmeter.data_layer.data["E3tP"]
        if energy_temp >= self.energy:
            self.energy = energy_temp
        if self.evse.data_layer.data["EV_STATE"] == CHARGING:
            self.session["energy"] = self.energy - self.session_start["energy"]
            self.evse.data_layer.data["SESSION_ENERGY"] = self.session["energy"]
            try:
                self.evse.data_layer.data["DURATION"] = self.get_duration_minutes()
            except Exception as e:
                print(f"Duration error: {e}")

        if self.evse.data_layer.data["EV_STATE"] != self.last_evse_state:
            self.last_evse_state = self.evse.data_layer.data["EV_STATE"]
            self.add_evse_state(self.evse.data_layer.data["EV_STATE"])

            disconnected1: bool = False
            charging1: bool = False
            for state in self.evse_states:
                if state == DISCONNECTED:
                    disconnected1 = True
                if state == CHARGING:
                    charging1 = True

            if self.evse.data_layer.data["EV_STATE"] == CHARGING and disconnected1:
                self.session_start["USER"] = self.evse.data_layer.data["USER"]
                self.session_start["energy"] = self.energy
                self.session_start["time"] = self.time['TIME']

            if self.evse.data_layer.data["EV_STATE"] == DISCONNECTED and charging1:
                self.session["USER"] = self.session_start["USER"]
                self.session["energy"] = self.energy - self.session_start["energy"]
                self.session["time"] = self.session_start["time"]
                self.add_session()
                self.write_file(self.file_path)
                self.rfid.add_user_energy(self.session["USER"], self.session["energy"])
                self.session_start["energy"] = self.energy

    def add_evse_state(self, state):
        if len(self.evse_states) >= 3:
            self.evse_states.pop(0)
            self.evse_states.append(state)

    def create_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                pass
        except OSError:
            with open(self.file_path, 'w') as file:
                pass

    def write_file(self, file_path):
        with open(file_path, 'w') as file:
            for session in self.sessions.data["history"]:
                file.write(self.format_session_row(session) + "\n")

    def format_session_row(self, session_user):
        return "{};{};{}".format(session_user['USER'], session_user['energy'], session_user['time'])

    def add_session(self):
        if len(self.sessions.data["history"]) >= MAX_SESSION_COUNT:
            self.sessions.data["history"].pop(0)
        new_session = OrderedDict()
        new_session["USER"] = self.session["USER"]
        new_session["energy"] = self.session["energy"]
        new_session["time"] = self.session["time"]
        self.sessions.data["history"].append(new_session)

    def read_data(self, file):
        try:
            row_count = 0
            data = []

            for row in open(file, "r"):
                collect()
                row_count += 1
            cnt = 0

            for i in open(file, "r"):
                cnt += 1
                if cnt > row_count - 20:
                    splited_row = i.strip().split(";")
                    data_dict = dict()
                    data_dict["USER"] = splited_row[0]
                    data_dict["energy"] = int(splited_row[1])
                    data_dict["time"] = splited_row[2]
                    data.append(data_dict)
                collect()
            return data
        except Exception as e:
            print("error", e)
            return []

    def get_duration_minutes(self) -> int:
        if len(self.session_start["time"]) < 1:
            return 0
        _, time_t = self.session_start["time"].split()
        hours, minutes = time_t.split(':')

        hours = int(hours)
        minutes = int(minutes)

        actual_hours: int = int(time.localtime()[3])
        actual_minutes: int = int(time.localtime()[4])

        if actual_hours < hours:
            hours_dur = (actual_hours - hours + 24) * 60
        else:
            hours_dur = (actual_hours - hours) * 60

        minutes_dur = (actual_minutes - minutes)

        return hours_dur + minutes_dur


class Datalayer:
    def __str__(self):
        return self.data

    def __init__(self):
        self.data = OrderedDict()
        self.data["history"]: list = []
