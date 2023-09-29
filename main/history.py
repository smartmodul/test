import time
from collections import OrderedDict
from gc import collect
from main import rfid

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
        self.sessions: Datalayer = Datalayer()
        self.last_evse_state: int = 0
        self.session: OrderedDict = OrderedDict()
        self.session["USER"] = "0"
        self.session["energy"]: int = 0  # kWh
        self.session["time"]: int = 0  # format DD, MM, RR, HH:MM
        self.sessions.data["history"] = [self.session]  # list jednotlivich session
        self.time: dict = {"TIME": 0}
        self.session_start: OrderedDict = OrderedDict()  # slovnik posledni session to se predela do tridy
        self.session_start["USER"]: str = "Anonym"
        self.session_start["energy"]: int = 0  # kWh
        self.session_start["time"]: str = ''  # format DD, MM, RR, HH:MM
        self.energy: int = 0
        self.evse_states = [0, 0, 0]  # fronta 3 poslednich stavu
        #self.last_loaded_user = "0"
        
        self.ready_clear_session: int = 0 # flag aby se nulovani seassion provedlo jen 1x

        self.file_path: str = "charging_history.dat"
        self.create_file(self.file_path)
        self.sessions.data["history"] = self.read_data(self.file_path)

    def run_history_handler(self):

        #pokud se neoveruje podle RFID, ukladej do anonyma
        if self.config.flash["sw,RFID VERIFICATION"] == '1':
            #pokud je nova karta a nenabiji se
            if self.rfid.status == History.NEW:
                if self.evse.data_layer.data["EV_STATE"] == CONNECTED:
                    self.config.ram['RFID_VERIFY'] = 1 
                    self.evse.data_layer.data["USER"]: str = self.rfid.last_loaded_user.user["NAME"]
                
            # pokud je odpojeno nebo pokud se nabiji a pipnuto stejnou kartou zrusit overeni
            if self.evse.data_layer.data["EV_STATE"] == DISCONNECTED:
                self.config.ram['RFID_VERIFY'] = 0
            if self.rfid.status == History.NEW_SAME and self.evse.data_layer.data["EV_STATE"] == CHARGING:
                self.config.ram['RFID_VERIFY'] = 0

        else: 
            self.evse.data_layer.data["USER"]: str = "anonym"
            
        print(self.evse.data_layer.data["USER"] + "  to je usrer")
        print(str(self.rfid.status) + "  status history")
        print(str(self.config.ram['RFID_VERIFY']) + "  verify")
        self.rfid.status = 0
        
        now: int = time.localtime()
        year_02: str = str(now[0])[-2:]
        self.time['TIME'] = ("{0:02}.{1:02}.{2} {3:02}:{4:02}".format(now[2], now[1], year_02, now[3], now[4]))

        if self.evse.data_layer.data["EV_STATE"] == CHARGING:
            self.energy = int(self.wattmeter.data_layer.data["E1tP"]) + int(
                self.wattmeter.data_layer.data["E2tP"]) + int(self.wattmeter.data_layer.data["E1tP"])
            self.session["energy"] = self.energy - int(self.session_start["energy"])
            try:
                self.evse.data["DURATION"] = self.get_duration_minutes(self.time['TIME'])
                self.svse.data["SESSION_ENERGY"] = self.session["energy"]
            except Exception as e:
                print(f"Duration error: {e}")
                    
        # pokud se zmenit stav zaloguj a handluj historii
        if self.evse.data_layer.data["EV_STATE"] != self.last_evse_state:
            self.last_evse_state = self.evse.data_layer.data["EV_STATE"]
            self.add_evse_state(self.evse.data_layer.data["EV_STATE"])

            # prohledej, jesli je v historii poslednich 3 stavu stav odpojeno.
            # muzeme promeskat prechod z disconnect do connect, takze staci kdyz je disconnected
            disconnected1: bool = False
            charging1: bool = False
            for state in self.evse_states:
                if state == DISCONNECTED:
                    disconnected1 = True
                if state == CHARGING:
                    charging1 = True
                    
            # pokud je inicializovan cas, handluj historii
            if self.wattmeter.time_init:
                # stav zmenen na nabijej a byl disconneced -> nova session: poznamenej hodnoty
                if self.evse.data_layer.data["EV_STATE"] == CHARGING and disconnected1:
                    self.session_start["USER"] = self.evse.data_layer.data["USER"]
                    self.session_start["energy"] = str(self.energy)
                    self.session_start["time"] = self.time['TIME']


                # stav zmenen na disconneced a byl charging -> konec session: poznamenej hodnoty
                if self.evse.data_layer.data["EV_STATE"] == DISCONNECTED and charging1:
                    self.session["USER"] = self.session_start["USER"]
                    self.session["energy"] = str(self.energy - int(self.session_start["energy"]))
                    self.session["time"] = self.session_start["time"]
                    self.add_session()
                    self.write_file(self.file_path)
                    self.rfid.add_user_energy(self.session["USER"], self.session["energy"])


    def add_evse_state(self, state):
        if len(self.evse_states) >= 3:
            self.evse_states.pop(0)  # Smaže nejstarší stav
            self.evse_states.append(state)  # Přidá nový stav na konec fronty

    def create_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                pass
        except OSError:
            with open(self.file_path, 'w') as file:
                pass

    def write_file(self, file_path):
        with open(file_path, 'w') as file:
            for self.session in self.sessions.data["history"]:
                file.write(self.format_session_row() + "\n")

    def format_session_row(self):
        return "{};{};{}".format(self.session['USER'], self.session['energy'], self.session['time'])

    def add_session(self):
        if len(self.sessions.data["history"]) >= MAX_SESSION_COUNT:
            self.sessions.data["history"].pop(0)
        self.sessions.data["history"].append(self.session)

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
            print("erorr", e)
            return []

    def get_duration_minutes(self, date) -> int:
        if len(self.session_start["time"]) < 1:
            return 0
        now: int = time.localtime()[3]
        time_t = self.session_start["time"].split(' ')[3]
        hours, minutes = map(int, time_t.split(':'))
        actual_hours: int = now[3]
        actual_minutes: int = now[4]

        if actual_hours < hours:
            hours_dur = (actual_hours - hours + 24) * 60
        else:
            hours_dur = (actual_hours - hours) * 60

        if actual_minutes < minutes:
            minutes_dur = (actual_minutes - minutes + 60)
        else:
            minutes_dur = (actual_minutes - minutes)

        return minutes_dur + hours_dur


class Datalayer:
    def __str__(self):
        return self.data

    def __init__(self):
        self.data = OrderedDict()
        self.data["history"]: list = []
