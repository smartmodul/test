import time
from machine import Pin, UART
from gc import collect, mem_free
from collections import OrderedDict
import ulogging

collect()

class Wattmeter:

    def __init__(self, comm_interface, config):

        self.relay = Pin(25, Pin.OUT)
        self.relay.off()
        self.wattmeter_interface = comm_interface
        self.data_layer = DataLayer()
        self.file_handler = FileHandler()
        self.daily_consumption: str = 'daily_consumption.dat'
        self.time_init: bool = False
        self.time_offset: bool = False
        self.last_minute: int = 0
        self.last_hour: int = 0
        self.last_day: int = 0
        self.last_month: int = 0
        self.last_year: int = 0
        self.start_up_time: int = 0
        self.config = config
        self.data_layer.data['ID'] = self.config.flash['ID']
        self.wattmeter_id: int = 100
        self.init_daily_energy: bool = False
        self.e1_offset: int = 0
        self.e2_offset: int = 0
        self.e3_offset: int = 0

        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    async def wattmeter_handler(self):
        if (self.time_offset is False) and self.time_init:
            self.start_up_time = time.time()
            self.last_minute = int(time.localtime()[4])
            self.last_day = int(time.localtime()[2])
            self.last_month = int(time.localtime()[1])
            self.last_year = int(time.localtime()[0])
            self.data_layer.data['D'] = self.file_handler.read_data(self.daily_consumption)
            self.data_layer.data["M"] = self.file_handler.get_monthly_energy(self.daily_consumption)
            self.time_offset = True

        self.data_layer.data['RUN_TIME'] = time.time() - self.start_up_time
        current_year: str = str(time.localtime()[0])[-2:]
        self.data_layer.data['WATTMETER_TIME'] = (
            "{0:02}.{1:02}.{2}  {3:02}:{4:02}:{5:02}".format(time.localtime()[2], time.localtime()[1], current_year,
                                                             time.localtime()[3], time.localtime()[4],
                                                             time.localtime()[5]))

        await self.__read_wattmeter_data(6000, 22)

        if (self.last_minute != int(time.localtime()[4])) and self.time_init:
            async with self.wattmeter_interface as w:
                await w.write_register(100, [1], self.wattmeter_id)
            self.last_minute = int(time.localtime()[4])

        if self.time_init and (self.last_hour != int(time.localtime()[3])):
            async with self.wattmeter_interface as w:
                await w.write_register(101, [1], self.wattmeter_id)
            self.last_hour = int(time.localtime()[3])

        if (self.last_day != int(time.localtime()[2])) and self.time_init and self.time_offset:
            self.e1_offset = self.data_layer.data["E1tP"]
            self.e2_offset = self.data_layer.data["E2tP"]
            self.e3_offset = self.data_layer.data["E3tP"]
            day: dict = {("{0:02}/{1:02}/{2}".format(self.last_month, self.last_day, str(self.last_year)[-2:])): [
                self.data_layer.data["E1dP"] + self.data_layer.data["E2dP"] + self.data_layer.data["E3dP"]]}
            async with self.wattmeter_interface as w:
                await w.write_register(102, [1], self.wattmeter_id)

            self.last_year = int(time.localtime()[0])
            self.last_month = int(time.localtime()[1])
            self.last_day = int(time.localtime()[2])
            self.file_handler.write_data(self.daily_consumption, day)
            self.data_layer.data["D"] = self.file_handler.read_data(self.daily_consumption, 31)
            self.data_layer.data["M"] = self.file_handler.get_monthly_energy(self.daily_consumption)

    async def __read_wattmeter_data(self, reg, length):
        async with self.wattmeter_interface as w:
            receive_data = await w.read_register(reg, length, self.wattmeter_id)
        try:
            if (receive_data != "Null") and (reg == 6000):
                self.data_layer.data['I1'] = int(((receive_data[0]) << 8) | (receive_data[1]))
                self.data_layer.data['I2'] = int(((receive_data[2]) << 8) | (receive_data[3]))
                self.data_layer.data['I3'] = int(((receive_data[4]) << 8) | (receive_data[5]))
                self.data_layer.data['U1'] = int(((receive_data[6]) << 8) | (receive_data[7]))
                self.data_layer.data['U2'] = int(((receive_data[8]) << 8) | (receive_data[9]))
                self.data_layer.data['U3'] = int(((receive_data[10]) << 8) | (receive_data[11]))
                self.data_layer.data['P1'] = int(((receive_data[12]) << 8) | (receive_data[13]))
                self.data_layer.data['P2'] = int(((receive_data[14]) << 8) | (receive_data[15]))
                self.data_layer.data['P3'] = int(((receive_data[16]) << 8) | (receive_data[17]))
                hdo = int((receive_data[18] << 8) | receive_data[19])
                if hdo == 1 and '1' == self.config.flash['sw,AC IN ACTIVE: HIGH']:
                    self.data_layer.data['A'] = 1
                elif hdo == 0 and '0' == self.config.flash['sw,AC IN ACTIVE: HIGH']:
                    self.data_layer.data['A'] = 1
                else:
                    self.data_layer.data['A'] = 0

                self.data_layer.data["E1tP"] = int(
                    (receive_data[34] << 24) | (receive_data[35] << 16) | (receive_data[32] << 8) | receive_data[33])
                self.data_layer.data["E2tP"] = int(
                    (receive_data[38] << 24) | (receive_data[39] << 16) | (receive_data[36] << 8) | receive_data[37])
                self.data_layer.data["E3tP"] = int(
                    (receive_data[42] << 24) | (receive_data[43] << 16) | (receive_data[40] << 8) | receive_data[41])

                if self.init_daily_energy:
                    self.data_layer.data["E1dP"] = self.data_layer.data["E1tP"] - self.e1_offset
                    self.data_layer.data["E2dP"] = self.data_layer.data["E2tP"] - self.e2_offset
                    self.data_layer.data["E3dP"] = self.data_layer.data["E3tP"] - self.e3_offset
                else:
                    self.init_daily_energy = True
                    self.e1_offset = self.data_layer.data["E1tP"]
                    self.e2_offset = self.data_layer.data["E2tP"]
                    self.e3_offset = self.data_layer.data["E3tP"]

                return 0

            else:
                return 1

        except Exception as e:
            self.logger.debug(e)
            return -1


class DataLayer:
    def __str__(self):
        return self.data

    def __init__(self):
        self.data = OrderedDict()
        self.data['I1'] = 0  # I1
        self.data['I2'] = 0  # I2
        self.data['I3'] = 0  # I3
        self.data['U1'] = 0
        self.data['U2'] = 0
        self.data['U3'] = 0
        self.data['P1'] = 0
        self.data['P2'] = 0
        self.data['P3'] = 0
        self.data['A'] = 0  # AC_IN
        self.data["E1dP"] = 0
        self.data["E2dP"] = 0
        self.data["E3dP"] = 0
        self.data["E1tP"] = 0  # positive total Energy L1
        self.data["E2tP"] = 0  # positive total Energy L1
        self.data["E3tP"] = 0  # positive total Energy L1
        self.data['ID'] = 0
        self.data['D'] = None  # Daily energy
        self.data['M'] = None  # Monthly energy
        self.data['RUN_TIME'] = 0
        self.data['WATTMETER_TIME'] = 0


class FileHandler:

    def read_data(self, file, length=None):
        data = []
        try:
            csv_gen = self.csv_reader(file)
            row_count = 0
            data = []
            for row in csv_gen:
                collect()
                row_count += 1

            csv_gen = self.csv_reader(file)
            cnt = 0
            for i in csv_gen:
                cnt += 1
                if cnt > row_count - 31:
                    data.append(i.replace("\n", ""))
                collect()
            return data
        except Exception as e:
            return []

    def csv_reader(self, file_name):
        for row in open(file_name, "r"):
            try:
                yield row
            except StopIteration:
                return

    def get_monthly_energy(self, file):
        energy = []
        last_month: int = 0
        last_year: int = 0
        positive_energy: int = 0

        try:
            csv_gen = self.csv_reader(file)
            for line in csv_gen:
                line = line.replace("\n", "").replace("/", ":").replace("[", "").replace("]", "").replace(",",
                                                                                                          ":").replace(
                    " ", "").split(":")
                if last_month == 0:
                    last_month = int(line[0])
                    last_year = int(line[2])

                if last_month != int(line[0]):
                    if len(energy) < 36:
                        energy.append("{}/{}:[{}]".format(last_month, last_year, positive_energy))
                    else:
                        energy = energy[1:]
                        energy.append("{}/{}:[{}]".format(last_month, last_year, positive_energy))
                    positive_energy = 0
                    last_month = int(line[0])
                    last_year = int(line[2])

                positive_energy += int(line[3])
                collect()

            if len(energy) < 36:
                energy.append("{}/{}:[{}]".format(last_month, last_year, positive_energy))
            else:
                energy = energy[1:]
                energy.append("{}/{}:[{}]".format(last_month, last_year, positive_energy))

            if energy is None:
                return []

            return energy

        except Exception as e:
            print("Error: ", e)

    def write_data(self, file, data):
        lines = []
        for variable, value in data.items():
            lines.append(("%s:%s\n" % (variable, value)).replace(" ", ""))

        with open(file, "a+") as f:
            f.write(''.join(lines))
