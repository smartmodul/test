import json
from collections import OrderedDict
import ulogging

CONNECTED: int = 2
CHARGING: int = 3


class Evse:

    def __init__(self, wattmeter, evse, config, inverter, rfid):
        self.evse_interface = evse
        self.inverter = inverter
        self.data_layer = DataLayer()
        self.config = config
        self.wattmeter = wattmeter
        self.rfid = rfid 
        self.evse_id: int = 1
        self.clear_bits: int = 0
        self.__cnt_current: int = 0
        self.__request_current: int = 0
        self.regulation_lock: bool = False
        self.lock_counter: int = 0
        self.__regulation_delay: int = 0
        self.__soc_lock: bool = False

        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    async def evse_handler(self) -> None:
        current: int = int(self.config.flash["in,EVSE-MAX-CURRENT-A"])

        if self.config.flash["sw,EXTERNAL REGULATION"] == '1':
            if int(self.config.ram["EVSE_CURRENT"]) > int(self.config.flash["in,EVSE-MAX-CURRENT-A"]):
                self.config.ram["EVSE_CURRENT"] = self.config.flash["in,EVSE-MAX-CURRENT-A"]
            current = int(self.config.ram["EVSE_CURRENT"])

        if self.clear_bits == 1:
            async with self.evse_interface as e:
                await e.write_register(1004, [0], modbus_id=1)
            self.clear_bits = 0

        status = await self.__read_evse_data(1000, 8, modbus_id=1)
        if status == -1:
            self.logger.debug("Reading error")
        try:
            if status == 0:
                if self.config.flash["sw,ENABLE BALANCING"] == '1' and self.inverter is not None:
                    current = self.balancing_evse_current()
                    if self.config.flash['in,SOC'] != '0':
                        if self.inverter.data_layer.data["soc"] < int(self.config.flash['in,SOC']):
                            current = int(self.config.flash["in,MAX-CURRENT-FROM-GRID-A"])

                self.logger.info(f"Set current: {current} A")

                if self.config.flash["sw,RFID VERIFICATION"] == '0':
                    if self.config.flash["sw,WHEN AC IN: CHARGING"] == '1':
                        if self.wattmeter.data_layer.data["A"] == 1:
                            async with self.evse_interface as e:
                                self.logger.info(f"---- EVSE current: {current} A")
                                await e.write_register(1000, [current], modbus_id=1)
                        else:
                            async with self.evse_interface as e:
                                self.logger.info(f"++++ EVSE current: {current} A")
                                await e.write_register(1000, [0], modbus_id=1)
                    else:
                        async with self.evse_interface as e:
                            self.logger.info(f"==== EVSE current: {current} A")
                            await e.write_register(1000, [current], modbus_id=1)

                elif self.config.flash["sw,RFID VERIFICATION"] == '1':
                    if self.config.ram['RFID_VERIFY'] == 1:
                        if self.config.flash["sw,WHEN AC IN: CHARGING"] == '1':
                            if self.wattmeter.data_layer.data["A"] == 1:
                                async with self.evse_interface as e:
                                    await e.write_register(1000, [current], modbus_id=1)
                            else:
                                async with self.evse_interface as e:
                                    await e.write_register(1000, [0], modbus_id=1)
                        else:
                            async with self.evse_interface as e:
                                await e.write_register(1000, [current], modbus_id=1)
                    else:
                        async with self.evse_interface as e:
                            await e.write_register(1000, [0], modbus_id=1)

        except Exception as e:
            self.logger.debug(f"{e}")

    async def __read_evse_data(self, reg: int, length: int, modbus_id: int) -> int:
        try:
            async with self.evse_interface as e:
                receive_data = await e.read_register(reg, length, modbus_id)
            if reg == 1000 and (receive_data != "Null") and receive_data:
                self.data_layer.data["ACTUAL_CONFIG_CURRENT"] = int(((receive_data[0]) << 8) | receive_data[1])
                self.data_layer.data["ACTUAL_OUTPUT_CURRENT"] = int(((receive_data[2]) << 8) | receive_data[3])
                self.data_layer.data["EV_STATE"] = int(((receive_data[4]) << 8) | receive_data[5])
                self.data_layer.data["OPT"] = int(((receive_data[6]) << 8) | receive_data[7])
                self.data_layer.data["CLEAR_CMD"] = int(((receive_data[8]) << 8) | receive_data[9])
                self.data_layer.data["FW_VERSION"] = int(((receive_data[10]) << 8) | receive_data[11])
                self.data_layer.data["EVSE_STATE"] = int(((receive_data[12]) << 8) | receive_data[13])
                self.data_layer.data["EVSE_STATUS"] = int(((receive_data[14]) << 8) | receive_data[15])

                self.data_layer.data["EV_COMM_ERR"] = 0
                return 0

            else:
                return -1

        except:
            if reg == 1000:
                self.data_layer.data["EV_COMM_ERR"] += 1
                if self.data_layer.data["EV_COMM_ERR"] > 30:
                    self.data_layer.data["ACTUAL_CONFIG_CURRENT"] = 0
                    self.data_layer.data["ACTUAL_OUTPUT_CURRENT"] = 0
                    self.data_layer.data["EV_STATE"] = 0
                    self.data_layer.data["OPT"] = 0
                    self.data_layer.data["CLEAR_CMD"] = 0
                    self.data_layer.data["FW_VERSION"] = 0
                    self.data_layer.data["EVSE_STATE"] = 0
                    self.data_layer.data["EVSE_STATUS"] = 0
                    self.data_layer.data["EV_COMM_ERR"] = 31
            return -1

    def verify_rfid(self) -> bool:
        return False

    def check_ev_is_connected(self) -> bool:
        if self.data_layer.data["EV_STATE"] == CONNECTED:
            return True
        return False

    def check_ev_is_charging(self) -> bool:
        if self.data_layer.data["EV_STATE"] == CHARGING:
            return True
        return False

    def balancing_evse_current(self):
        i1: int = 0
        i2: int = 0
        i3: int = 0
        max_current: int = 0
        delta: int = 0

        if self.inverter.data_layer.data["i1"] > 32767:
            i1 = self.inverter.data_layer.data["i1"] - 65535
        else:
            i1 = self.inverter.data_layer.data["i1"]

        if self.inverter.data_layer.data["i2"] > 32767:
            i2 = self.inverter.data_layer.data["i2"] - 65535
        else:
            i2 = self.inverter.data_layer.data["i2"]

        if self.inverter.data_layer.data["i3"] > 32767:
            i3 = self.inverter.data_layer.data["i3"] - 65535
        else:
            i3 = self.inverter.data_layer.data["i3"]

        if (i1 > i2) and (i1 > i3):
            max_current = int(round(i1 / 100.0))

        if (i2 > i1) and (i2 > i3):
            max_current = int(round(i2 / 100.0))

        if (i3 > i1) and (i3 > i2):
            max_current = int(round(i3 / 100.0))


        delta: int = int(self.config.flash["in,MAX-CURRENT-FROM-GRID-A"]) - max_current

        if max_current > int(self.config.flash["in,MAX-CURRENT-FROM-GRID-A"]):
            delta = int(self.config.flash["in,MAX-CURRENT-FROM-GRID-A"]) - max_current

        self.__cnt_current = self.__cnt_current + 1
        # Dle normy je zmena proudu EV nasledujici po zmene pracovni cyklu PWM maximalne 5s
        breaker = int(self.config.flash["in,MAX-CURRENT-FROM-GRID-A"])

        self.logger.info(f"I1: {i1}A, I2: {i2}A, I3: {i3}A, max_current: {max_current}, delta: {delta}, breaker:{breaker}")

        if (breaker * 0.5 + delta) < 0:
            self.__request_current = 0
            self.__regulation_delay = 1

        elif self.__cnt_current >= 2:
            if delta < 0:
                self.__request_current = self.__request_current + delta
                self.regulation_lock = True
                self.lock_counter = 1

            elif self.__regulation_delay > 0:
                self.__request_current = 0

            elif not self.regulation_lock:
                if (delta >= 6 and self.check_ev_is_connected()) or self.check_ev_is_charging():
                    self.__request_current = self.__request_current + 1

            self.__cnt_current = 0

        if self.lock_counter >= 30:
            self.lock_counter = 0
            self.regulation_lock = False

        if self.regulation_lock or (self.lock_counter > 0):
            self.lock_counter = self.lock_counter + 1

        if self.__regulation_delay > 0:
            self.__regulation_delay = self.__regulation_delay + 1
        if self.__regulation_delay > 60:
            self.__regulation_delay = 0

        if self.__request_current > int(self.config.flash["in,EVSE-MAX-CURRENT-A"]):
            self.__request_current = int(self.config.flash["in,EVSE-MAX-CURRENT-A"])

        if self.__request_current < 0:
            self.__request_current = 0

        self.logger.info(f"====Request_current: {self.__request_current}A")
        return self.__request_current


class DataLayer:
    def __str__(self):
        return self.data

    def __init__(self):
        self.data = OrderedDict()
        self.data["ACTUAL_CONFIG_CURRENT"]: int = 0
        self.data["ACTUAL_OUTPUT_CURRENT"]: int = 0
        self.data["EV_STATE"]: int = 0
        self.data["OPT"]: int = 0
        self.data["CLEAR_CMD"]: int = 0
        self.data["FW_VERSION"]: int = 0
        self.data["EVSE_STATE"]: int = 0
        self.data["EVSE_STATUS"]: int = 0
        self.data["EV_COMM_ERR"]: int = 0
        self.data["DURATION"]: int = 0
        self.data["SESSION_ENERGY"]: int = 0
        self.data["USER"]: str = "-"
