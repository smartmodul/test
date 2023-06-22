import json
from collections import OrderedDict
import ulogging

CONNECTED: int = 2
CHARGING: int = 3


class Evse:

    def __init__(self, wattmeter, evse, config):
        self.evse_interface = evse
        self.data_layer = DataLayer()
        self.config = config
        self.wattmeter = wattmeter
        self.evse_id: int = 1
        self.clear_bits: int = 0

        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    async def evse_handler(self, verify=False, user="Unknown") -> None:

        if int(self.config.ram["EVSE_CURRENT"]) > int(self.config.flash["in,EVSE-MAX-CURRENT-A"]):
            self.config.ram["EVSE_CURRENT"] = self.config.flash["in,EVSE-MAX-CURRENT-A"]

        current = int(self.config.flash["in,EVSE-MAX-CURRENT-A"])

        if self.config.flash["sw,EXTERNAL REGULATION"] is '1':
            current = int(self.config.ram["EVSE_CURRENT"])

        if self.clear_bits == 1:
            async with self.evse_interface as e:
                await e.write_register(1004, [0], modbus_id=1)
            self.clear_bits = 0

        status = await self.__read_evse_data(1000, 8, modbus_id=1)
        if status == -1:
            raise Exception("reading error.")
        try:
            if status == 0:
                if self.config.flash["sw,RFID VERIFICATION"] is '0':
                    if self.config.flash["sw,WHEN AC IN: CHARGING"] is '1':
                        if self.wattmeter.data_layer.data["A"] == 1:
                            async with self.evse_interface as e:
                                await e.write_register(1000, [current], modbus_id=1)
                        else:
                            async with self.evse_interface as e:
                                await e.write_register(1000, [0], modbus_id=1)
                    else:
                        async with self.evse_interface as e:
                            await e.write_register(1000, [current], modbus_id=1)

                elif self.config.flash["sw,RFID VERIFICATION"] is '1':
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
            self.logger.debug("evse_handler error: {}".format(e))
            raise Exception("evse_handler error: {}".format(e))

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

        except Exception as e:
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

    def verify_rfid(self):
        pass

    def check_ev_is_connected(self) -> bool:
        if self.data_layer.data["EV_STATE"] == CONNECTED:
            return True
        return False

    def check_ev_is_charging(self) -> bool:
        if self.data_layer.data["EV_STATE"] == CHARGING:
            return True
        return False


class DataLayer:
    def __str__(self):
        return json.dumps(self.data)

    def __init__(self):
        self.data = OrderedDict()
        self.data["ACTUAL_CONFIG_CURRENT"] = 0
        self.data["ACTUAL_OUTPUT_CURRENT"] = 0
        self.data["EV_STATE"] = 0
        self.data["OPT"] = 0
        self.data["CLEAR_CMD"] = 0
        self.data["FW_VERSION"] = 0
        self.data["EVSE_STATE"] = 0
        self.data["EVSE_STATUS"] = 0
        self.data["EV_COMM_ERR"] = 0
        self.data["DURATION"] = 0
        self.data["USER"] = "Uknown"
