import os
import uasyncio as asyncio
import ulogging
from machine import Pin, UART
from collections import OrderedDict
from gc import collect

USERS_LIMIT: int = 20

OK: int = 1
ID_EXIST: int = 2
NAME_EXIST: int = 3
FULL: int = 4

MODE_TIMEOUT: int = 50


class Rfid:
    RFID_ID: int = 101
    NEW: int = 1
    NEW_SAME: int = 2

    NORMAL: int = 0
    ADD_USER: int = 1
    DELETE_USER: int = 2
    ERASE_ENERGY: int = 3

    def __init__(self, comm_interface, config):
        # self.commInterface = commInterface
        self.rfid_interface = comm_interface
        self.config = config
        self.data_layer = DataLayer()
        self.user = User()  # uzivatel ktereho edituje apka
        self.last_loaded_user = User()  # aktualne nabijejici/autorizovany uzivatel

        self.data_layer.users["DATABASE"] = [
            self.user]  # databaze v RAM ta se zrcadli do FLASH "rfid.dat" pri kazde zmene

        self.file_path: str = "rfid.dat"
        self.create_file(self.file_path)
        self.data_layer.users["DATABASE"] = self.read_file(self.file_path)

        self.mode: int = 0  # ADD = 1
        self.status: int = 0
        self.last_id: str = "0"
        self.last_cnt_state = 0

        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def handle_request(self, rfid_mode, user=None, id=None):
        # print(f"Rfid mode: {rfid_mode}, User: {user}, ID: {id}")

        self.user.user["NAME"] = str(user)
        self.user.user["ID"] = str(id)
        self.mode = rfid_mode

        return 20

    async def rfid_handler(self):
        status: int = 0
        if self.mode == Rfid.DELETE_USER:  # k odstraneni se pouzije ID z apky
            self.delete_user(self.user.user["ID"])
            self.mode = Rfid.NORMAL

        if self.mode == Rfid.ERASE_ENERGY:  # k nulovani se pouzije ID z apky
            self.erase_user_energy(self.user.user["ID"])
            self.mode = Rfid.NORMAL

        try:
            await self.__read_rfid_data(2000, 7)
            if self.data_layer.data["CNT"] != self.last_cnt_state:
                self.logger.info(f"New rfid card read {self.get_rfid_id()}")
                self.last_cnt_state = self.data_layer.data["CNT"]
                new_ID = self.get_rfid_id()
                user = self.get_user_from_ID(new_ID)
                # pokud je nacetla karta jina nez posledne
                if new_ID != self.last_id:
                    self.last_id = new_ID
                    if user:  # pokud je ID v databazi poznamenej uzivatele pro tuto seassion
                        self.last_loaded_user.user["NAME"] = user
                        self.last_loaded_user.user["ID"] = new_ID
                        self.status = Rfid.NEW
                    else:
                        self.status = 0  # v databazi uzivatel neni
                else:
                    self.status = Rfid.NEW_SAME  # stejna karta jako posledne

                if self.mode == Rfid.ADD_USER:  # k pridani se pouzije ID ze ctecky
                    status = self.add_user(self.user.user["NAME"], new_ID)
                    if status == 1:
                        self.logger.debug(f"User: {self.user.user['NAME']} added")
                    self.mode = Rfid.NORMAL
            print(str(self.status) + " status")
        except Exception as error:
            self.logger.debug(f"rfid_handler fce error: {error}")

    async def __read_rfid_data(self, reg: int, length: int) -> None:
        try:
            async with self.rfid_interface as r:
                receive_data = await r.read_register(reg, length, Rfid.RFID_ID)
                if receive_data is None:
                    raise Exception("RFID data is None")

            if reg == 2000 and (receive_data is not None):
                self.data_layer.data["CNT"] = int(((receive_data[0]) << 8) | receive_data[1])
                self.data_layer.data["LEN"] = int(((receive_data[2]) << 8) | receive_data[3])

                if 4 == self.data_layer.data["LEN"]:
                    self.data_layer.data["ID-1"] = int(((receive_data[5]) << 8) | receive_data[4])
                    self.data_layer.data["ID-2"] = int(((receive_data[7]) << 8) | receive_data[6])
                    self.data_layer.data["ID-3"] = 0
                    self.data_layer.data["ID-4"] = 0
                    self.data_layer.data["ID-5"] = 0

                if 7 == self.data_layer.data["LEN"]:
                    self.data_layer.data["ID-1"] = int(((receive_data[5]) << 8) | receive_data[4])
                    self.data_layer.data["ID-2"] = int(((receive_data[7]) << 8) | receive_data[6])
                    self.data_layer.data["ID-3"] = int(((receive_data[9]) << 8) | receive_data[8])
                    self.data_layer.data["ID-4"] = int(((receive_data[11]) << 8) | receive_data[10])
                    self.data_layer.data["ID-5"] = int(((receive_data[13]) << 8) | receive_data[12])

                if 10 == self.data_layer.data["LEN"]:
                    self.data_layer.data["ID-1"] = int(((receive_data[5]) << 8) | receive_data[4])
                    self.data_layer.data["ID-2"] = int(((receive_data[7]) << 8) | receive_data[6])
                    self.data_layer.data["ID-3"] = int(((receive_data[9]) << 8) | receive_data[8])
                    self.data_layer.data["ID-4"] = int(((receive_data[11]) << 8) | receive_data[10])
                    self.data_layer.data["ID-5"] = int(((receive_data[13]) << 8) | receive_data[12])

        except Exception as error:
            raise Exception(f"Reading error -> {error}")

    def get_rfid_id(self):
        if self.data_layer.data["LEN"] == 4:
            return (f"{self.data_layer.data['ID-1']:04X}" +
                    f"{self.data_layer.data['ID-2']:04X}")

        elif self.data_layer.data["LEN"] == 7:
            return (f"{self.data_layer.data['ID-1']:04X}" +
                    f"{self.data_layer.data['ID-2']:04X}" +
                    f"{self.data_layer.data['ID-3']:04X}" +
                    f"{(self.data_layer.data['ID-4'] & 0xFF):02X}")

        elif self.data_layer.data["LEN"] == 10:
            return (f"{self.data_layer.data['ID-1']:04X}" +
                    f"{self.data_layer.data['ID-2']:04X}" +
                    f"{self.data_layer.data['ID-3']:04X}" +
                    f"{self.data_layer.data['ID-4']:04X}" +
                    f"{self.data_layer.data['ID-5']:04X}")

    def get_user_from_ID(self, ID:str):
        for user in self.data_layer.users["DATABASE"]:
            if user.get("ID") == ID:
                print("v databazi uz je cip " + ID)  # (f"ID cipu {ID} nalezi uzivateli {self.user['NAME']}")
                return user.get("NAME")
        return False

    def check_name(self, name: str):
        for user_data in self.data_layer.users["DATABASE"]:
            if user_data.get("NAME") == name:
                print("v databazi uz je jmeno " + name)
                return True
        return False

        # pridani uzivatele

    def add_user(self, name: str, ID):
        if self.get_user_from_ID(ID) == False:
            if self.check_name(name) == False:
                if len(self.data_layer.users["DATABASE"]) >= USERS_LIMIT:
                    return FULL
                else:
                    new_user = OrderedDict()
                    new_user["NAME"] = name
                    new_user["ID"] = ID
                    new_user["TOTAL_ENERGY"] = 0
                    new_user["ERASEBLE_ENERGY"] = 0
                    # zapis do RAM
                    self.data_layer.users["DATABASE"].append(new_user)
                    # zapis do FLASH
                    self.write_file(self.file_path)
                    return OK
            else:
                return NAME_EXIST
        else:
            return ID_EXIST

    def add_user_energy(self, name: str, session_energy: int):
        for user in self.data_layer.users["DATABASE"]:
            if user.get("NAME") == name:
                energy = int(user.get("TOTAL_ENERGY"))
                new_energy = energy + int(session_energy)
                user["TOTAL_ENERGY"] = str(new_energy)
                self.write_file(self.file_path)
                return OK
        return False

    def delete_user(self, ID):
        for user in self.data_layer.users["DATABASE"]:
            if user.get("ID") == ID:
                self.data_layer.users["DATABASE"].remove(user)
                self.write_file(self.file_path)
                return True
        return False

    def create_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                pass
        except OSError:
            with open(self.file_path, 'w') as file:
                pass

    def write_file(self, file_path):
        with open(file_path, 'w') as file:
            for user in self.data_layer.users["DATABASE"]:
                file.write(self.format_user_row(user) + "\n")

    def format_user_row(self, user):
        return "{};{};{};{}".format(user["NAME"], user["ID"], user["TOTAL_ENERGY"], user["ERASEBLE_ENERGY"])

    def read_file(self, file):
        try:
            row_count = 0
            data = []

            for row in open(file, "r"):
                collect()
                row_count += 1
            cnt = 0
            for i in open(file, "r"):
                cnt += 1
                if cnt > row_count - USERS_LIMIT:
                    splited_row = i.strip().split(";")
                    data_dict = dict()
                    data_dict["NAME"] = splited_row[0]
                    data_dict["ID"] = splited_row[1]
                    data_dict["TOTAL_ENERGY"] = int(splited_row[2])
                    data_dict["ERASEBLE_ENERGY"] = splited_row[3]

                    data.append(data_dict)

                collect()
            return data
        except Exception as e:
            print("erorr", e)
            return []


class DataLayer:
    def __str__(self):
        return str(self.data)

    def __init__(self):
        self.data = OrderedDict()
        self.data["CNT"] = 0
        self.data["LEN"] = 0
        self.data["ID-1"] = 0
        self.data["ID-2"] = 0
        self.data["ID-3"] = 0
        self.data["ID-4"] = 0
        self.data["ID-5"] = 0
        self.data["USER"] = "Anonym"

        self.users = OrderedDict()
        self.users["DATABASE"]: list = []


class User:
    def __str__(self):
        return str(self.user)

    def __init__(self):
        self.user = OrderedDict()
        self.user["NAME"] = "Anonym"
        self.user["ID"] = "0x0000"
        self.user["TOTAL_ENERGY"] = 0
        self.user["ERASEBLE_ENERGY"] = 0
