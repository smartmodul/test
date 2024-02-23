import uasyncio as asyncio
from led_handler import LedHandler
import ulogging

from ntptime import settime
from asyn import Lock
from gc import mem_free, collect, mem_alloc
from machine import Pin, WDT, RTC
from main.web_server_app import WebServerApp
from main import wattmeter
from main import evse
from main import rfid

from main.uart1 import Interface
from main.__config__ import Config
from main.modbus_slave import ModbusSlave
from main.history import History

collect()

EVSE_ERR: int = 1
WATTMETER_ERR: int = 2
RFID_ERR: int = 3
WEBSERVER_CANCELATION_ERR: int = 4
WIFI_HANDLER_ERR: int = 8
TIME_SYNC_ERR: int = 16

AP: int = 1
WIFI: int = 2


class TaskHandler:
    def __init__(self, wifi):
        uart1_interface = Interface(9600, lock=Lock(200))
        self.config = Config()
        self.rfid = rfid.Rfid(uart1_interface, self.config)
        self.wattmeter = wattmeter.Wattmeter(uart1_interface, self.config)

        self.inverter = None
        if int(self.config.flash['btn,INVERTER-TYPE']) == 1:
            from main.inverters.goodwe import Goodwe
            self.inverter = Goodwe(wifi, self.config, wattmeter=self.wattmeter)
        elif int(self.config.flash['btn,INVERTER-TYPE']) == 2:
            from main.inverters.solax import Solax
            self.inverter = Solax(wifi, self.config)
        elif int(self.config.flash['btn,INVERTER-TYPE']) == 3:
            from main.inverters.victron import Victron
            self.inverter = Victron(wifi, self.config, wattmeter=self.wattmeter)
        elif int(self.config.flash['btn,INVERTER-TYPE']) == 4:
            from main.inverters.huawei import Huawei
            self.inverter = Huawei(wifi, self.config)
        elif int(self.config.flash['btn,INVERTER-TYPE']) == 5:
            from main.inverters.infigy import Infigy
            self.inverter = Infigy(wifi, self.config)
        elif int(self.config.flash['btn,INVERTER-TYPE']) == 6:
            from main.inverters.rs485_tcp import RS485_Tcp
            self.inverter = RS485_Tcp(wifi, self.config)

        self.evse = evse.Evse(self.wattmeter, uart1_interface, self.config, self.inverter, self.rfid)
        self.history = History(wattmeter=self.wattmeter, evse=self.evse, rfid=self.rfid, config=self.config)

        self.web_server_app = WebServerApp(wifi, self.wattmeter, self.evse, uart1_interface,
                                           self.config, self.rfid, self.inverter, self.history)

        self.setting_after_new_connection: bool = False
        self.wdt: WDT = WDT(timeout=60000)

        self.wifi_manager = wifi
        self.led_error_handler: LedHandler = LedHandler(21, 1, 2, 40)
        self.led_wifi_handler: LedHandler = LedHandler(22, 1, 2, 20)
        self.errors: int = 0
        self.try_off_connections: int = 0
        self.wifi_manager.turnONAp()
        self.ap_timeout: int = 600
        self.mem_logger_cnt: int = 0

        if int(self.config.flash['sw,EXTERNAL REGULATION']) == 1:
            self.modbus_slave = ModbusSlave(9600, self.wattmeter, self.evse, self.rfid, self.config)

        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def mem_free(self) -> None:
        self.mem_logger_cnt += 1
        if self.mem_logger_cnt > 10:
            self.logger.debug(f"RAM free: {mem_free()} alloc: {mem_alloc()}")
            self.mem_logger_cnt = 0
        collect()

    async def led_handler(self) -> None:
        while True:
            await self.led_wifi_handler.led_handler()
            await self.led_error_handler.led_handler()
            await asyncio.sleep(0.1)

    async def time_handler(self) -> None:
        while True:
            if self.wifi_manager.is_connected() and self.wattmeter.time_init is False:
                try:
                    self.logger.info("Setting time")
                    settime()
                    rtc = RTC()
                    import utime
                    tampon1 = utime.time()
                    tampon2 = tampon1 + int(self.config.get_config()["in,TIME-ZONE"]) * 3600
                    (year, month, mday, hour, minute, second, weekday, yearday) = utime.localtime(tampon2)
                    rtc.datetime((year, month, mday, 0, hour, minute, second, 0))
                    self.wattmeter.time_init = True
                    self.led_error_handler.remove_state(TIME_SYNC_ERR)
                    self.errors &= ~TIME_SYNC_ERR
                except Exception as e:
                    self.led_error_handler.add_state(TIME_SYNC_ERR)
                    self.errors |= TIME_SYNC_ERR
                    self.logger.error("Error during time setting: {}".format(e))

            await asyncio.sleep(10)
            self.mem_free()

    async def wifi_handler(self) -> None:
        while True:
            try:
                self.led_wifi_handler.add_state(AP)
                if self.wifi_manager.is_connected():
                    if self.ap_timeout > 0:
                        self.ap_timeout -= 1
                    elif (int(self.config.flash['sw,Wi-Fi AP']) == 0) and self.ap_timeout == 0:
                        self.wifi_manager.turnOffAp()
                        self.led_wifi_handler.remove_state(AP)
                    elif int(self.config.flash['sw,Wi-Fi AP']) == 1:
                        self.wifi_manager.turnONAp()
                    self.led_wifi_handler.add_state(WIFI)
                    if not self.setting_after_new_connection:
                        self.setting_after_new_connection = True
                else:
                    self.led_wifi_handler.remove_state(WIFI)
                    if len(self.wifi_manager.read_profiles()) != 0:
                        if self.try_off_connections > 30:
                            self.try_off_connections = 0
                            result = await self.wifi_manager.get_connection()
                            if result:
                                self.setting_after_new_connection = False
                        self.try_off_connections = self.try_off_connections + 1
                self.led_error_handler.remove_state(WIFI_HANDLER_ERR)
                self.errors &= ~WIFI_HANDLER_ERR
            except Exception as e:
                self.led_error_handler.add_state(WIFI_HANDLER_ERR)
                self.errors |= WIFI_HANDLER_ERR
                self.logger.error("wifiHandler exception : {}".format(e))
            self.mem_free()
            await asyncio.sleep(2)

    async def interface_handler(self) -> None:
        while True:

            try:
                await self.evse.evse_handler()
                self.led_error_handler.remove_state(EVSE_ERR)
                self.errors &= ~EVSE_ERR
            except Exception as e:
                self.led_error_handler.add_state(EVSE_ERR)
                self.errors |= EVSE_ERR
                self.logger.debug("EVSE error: {}".format(e))
            self.mem_free()

            try:
                await self.wattmeter.wattmeter_handler()
                self.led_error_handler.remove_state(WATTMETER_ERR)
                self.errors &= ~WATTMETER_ERR
            except Exception as e:
                self.led_error_handler.add_state(WATTMETER_ERR)
                self.errors |= WATTMETER_ERR
                self.logger.debug("WATTMETER error: {}".format(e))

            try:
                await self.rfid.rfid_handler()
            except Exception as e:
                self.logger.error("RFID error: {}".format(e))

            try:
                self.history.run_history_handler()
            except Exception as e:
                self.logger.error("History error: {}".format(e))

            self.mem_free()
            self.config.flash['ERRORS'] = str(self.errors)
            self.wdt.feed()
            await asyncio.sleep(3)

    async def inverter_handler(self) -> None:
        while True:
            if self.wifi_manager.is_connected():
                if self.inverter is not None and self.inverter.connection_status == 0:
                    await self.inverter.scann()
                if self.inverter is not None:
                    await self.inverter.run()
            await asyncio.sleep(3)

    def main_task_handler_run(self) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(self.wifi_handler())
        loop.create_task(self.time_handler())
        loop.create_task(self.led_handler())
        loop.create_task(self.web_server_app.web_server_run())
        if int(self.config.flash['sw,EXTERNAL REGULATION']) == 1:
            self.logger.info("External modbus  slave is running!")
            loop.create_task(self.modbus_slave.run())
        loop.create_task(self.inverter_handler())
        loop.create_task(self.interface_handler())
        loop.run_forever()
