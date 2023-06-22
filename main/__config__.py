import bootloader
from collections import OrderedDict
import os
import ulogging


class Config:

    def __init__(self):
        """
        Variable saved in flash, description here:
        https://docs.google.com/spreadsheets/d/1o7jqMIgZLB4vze_WgeTATcNXEana7cYTyqURknLsaP0/edit#gid=0
        """
        self.boot = bootloader.Bootloader('https://github.com/smartmodul/production', "")
        self.flash = OrderedDict()
        self.flash['sw,AUTOMATIC UPDATE'] = '1'
        self.flash['txt,ACTUAL SW VERSION'] = '0'
        self.flash['sw,RFID VERIFICATION'] = '0'
        self.flash['in,EVSE-MAX-CURRENT-A'] = '25'
        self.flash['sw,WHEN AC IN: CHARGING'] = '0'
        self.flash['in,TIME-ZONE'] = '2'
        self.flash['sw,AC IN ACTIVE: HIGH'] = '0'
        self.flash['sw,TESTING SOFTWARE'] = '0'
        self.flash['sw,Wi-Fi AP'] = '1'
        self.flash['sw,EXTERNAL REGULATION'] = '0'
        self.flash['in,MODBUS-ID'] = '1'
        self.flash['ERRORS'] = '0'
        self.flash['bt,RESET'] = 0
        self.flash['TYPE'] = '2'
        self.flash['ID'] = '0'

        self.setting_profile = 'setting.dat'
        self.handle_configure('txt,ACTUAL SW VERSION', self.boot.get_version(""))
        self.get_config()
        self.ram = OrderedDict()
        self.ram['RFID_VERIFY'] = 0
        self.ram['EVSE_CURRENT'] = int(self.flash['in,EVSE-MAX-CURRENT-A'])

        self.logger = ulogging.getLogger(__name__)
        if int(self.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def get_config(self) -> OrderedDict[str, str | int]:
        try:
            setting = self.read_setting()
        except OSError:
            setting = {}

        if len(setting) != len(self.flash):
            with open(self.setting_profile, 'w') as file:
                file.write('')
                file.close()

            for i in self.flash:
                if i in setting and self.flash[i] != setting[i]:
                    self.flash[i] = setting[i]
            setting = {}

        for i in self.flash:
            if i in setting:
                if self.flash[i] != setting[i]:
                    self.flash[i] = setting[i]
            else:
                setting[i] = self.flash[i]
                self.write_setting(setting)

        if self.flash['ID'] == '0':
            _id = bytearray(os.urandom(4))
            rand_id = ''
            for i in range(0, len(_id)):
                rand_id += str((int(_id[i])))
            self.flash['ID'] = rand_id[-5:]
            self.handle_configure('ID', self.flash['ID'])

        return self.flash

    def handle_configure(self, variable: str, value: str) -> bool:
        try:
            if variable == 'bt,RESET PV-ROUTER':
                from machine import reset
                reset()

            if len(variable) > 0:
                try:
                    setting = self.read_setting()
                except OSError:
                    setting = {}

                if setting[variable] != value:
                    setting[variable] = value
                    self.write_setting(setting)
                    self.get_config()
                    return True
            else:
                return False
        except Exception as e:
            self.logger.error("handle_configure exception: {}.".format(e))
            return False

    def read_setting(self) -> OrderedDict[str, str | int]:
        with open(self.setting_profile) as f:
            lines: list[str] = f.readlines()
        setting: OrderedDict = OrderedDict()
        try:
            for line in lines:
                variable, value = line.strip("\n").split(";")
                setting[variable] = value
            return setting

        except Exception as e:
            self.logger.error("read_setting exception: {}.".format(e))
            self.write_setting(self.flash)
            return self.flash

    def write_setting(self, setting: OrderedDict[str, str]) -> None:
        lines: list[str] = []
        for variable, value in setting.items():
            lines.append("%s;%s\n" % (variable, value))
        with open(self.setting_profile, "w") as f:
            f.write(''.join(lines))
