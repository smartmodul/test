import uselect as select
import modbus
from machine import UART
import uasyncio as asyncio
from machine import Pin
import ulogging


class ModbusSlave:

    def __init__(self, baudrate: int, wattmeter, evse, rfid, config):
        self.de = Pin(15, Pin.OUT)
        self.uart = UART(2, baudrate)
        self.uart.init(baudrate, bits=8, parity=None, stop=1)  # init with given parameters
        self.modbus_client = modbus.Modbus()
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.wattmeter = wattmeter
        self.evse = evse
        self.rfid = rfid
        self.config = config

        poll = select.poll()
        poll.register(self.uart, select.POLLIN)
        poll.poll(1)

        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    async def run(self):
        self.logger.debug("Start reading")
        while True:
            self.de.on()
            res = []
            if self.uart.any():
                res = self.uart.read()
            else:
                await asyncio.sleep_ms(10)
            try:
                if len(res) < 8:
                    continue
                self.logger.debug("Received data: {}".format(res))
                result = self.modbus_check_process(res)
                self.logger.debug("Sended data: {}".format(result))

                self.de.off()
                await self.swriter.awrite(result)
                await asyncio.sleep_ms(60)
            except Exception as e:
                self.logger.error("run client modbus slave exception: {}".format(e))

    def modbus_check_process(self, receive_data: bytearray) -> bytearray:

        modbus_id: int = receive_data[0]
        fce: int = receive_data[1]
        reg: int = int((receive_data[2] << 8) | receive_data[3])
        length: int = int((receive_data[4] << 8) | receive_data[5])

        if length > 20:
            raise BadDataLengthError("MODBUS exception - unsupported data length")

        if (fce != 3) and (fce != 16):
            raise BadFceError("MODBUS exception - unsupported function")

        if modbus_id != int(self.config.flash['in,MODBUS-ID']):
            raise BadIdError("MODBUS exception - unsupported id")

        if fce == 16 and len(receive_data) != (9 + length * 2):
            raise BadIdError("MODBUS exception - data is to short")

        ud = list()
        if (reg >= 1000) and ((reg + length - 1) < 1008):
            ud = self.process_evse_data(fce, length, reg)

        if (reg >= 2000) and ((reg + length - 1) < 2008):
            ud = self.process_rfid_data(fce, length, reg)

        if (reg >= 3000) and ((reg + length - 1) < 3011):
            ud = self.process_esp_flash_data(fce, length, reg, receive_data[7:2 * length + 7])

        if (reg >= 3100) and ((reg + length - 1) < 3102):
            ud = self.process_esp_ram_data(fce, length, reg, receive_data[7:2 * length + 7])

        if (reg >= 4000) and ((reg + length - 1) < 4023):
            ud = self.process_wattmeter_data(fce, length, reg)

        if (reg == 5000) and ((reg + length - 1) < 5012):
            ud = self.process_opt_data(fce)

        send_data = list()
        send_data.append(chr(int(self.config.flash['in,MODBUS-ID'])))
        send_data.append(chr(fce))

        if fce == 3:
            send_data.append(chr(length * 2))
            if ud is not None:
                send_data += ud
            else:
                send_data[3] = chr(0)
                send_data[4] = chr(0)

        elif fce == 16:
            if ud is not None:
                send_data += ud
                send_data.append(chr(length >> 8))
                send_data.append(chr(length & 0xff))
            else:
                send_data[5] = 0
                send_data[6] = 0

        crc = self.modbus_client.calcCRC(send_data)
        send_data.append(chr(crc & 0xff))
        send_data.append(chr(crc >> 8))

        red = bytearray()
        for i in send_data:
            red += bytes([ord(i)])

        return red

    def process_wattmeter_data(self, fce: int, length: int, reg: int) -> list:

        reg = reg - 4000
        if fce == 3:
            cnt = 0
            data = list()
            for key in self.wattmeter.data_layer.data:
                if reg <= cnt < reg + length:
                    data.append(chr(int(self.wattmeter.data_layer.data[key]) >> 8))
                    data.append(chr(int(self.wattmeter.data_layer.data[key]) & 0xFF))
                cnt += 1
            return data

        if fce == 16:
            raise BadFceError("MODBUS exception - wattmeter unsupported function 0x10")

    def process_evse_data(self, fce: int, length: int, reg: int) -> list:
        reg = reg - 1000
        if fce == 3:
            cnt = 0
            data = list()
            for key in self.evse.data_layer.data:
                if reg <= cnt < reg + length:
                    data.append(chr(int(self.evse.data_layer.data[key]) >> 8))
                    data.append(chr(int(self.evse.data_layer.data[key]) & 0xFF))
                cnt += 1
            return data

        if fce == 16:
            if reg == 4:
                self.evse.clear_bits = 1
                data = list()
                data.append(chr(int(reg) >> 8))
                data.append(chr(int(reg) & 0xFF))
                return data
            else:
                raise BadFceError("MODBUS exception - evse unsupported function 0x10")

    def process_rfid_data(self, fce: int, length: int, reg: int) -> list:
        reg = reg - 2000
        if fce == 3:
            cnt = 0
            data = list()
            for key in self.rfid.data_layer.data:
                if reg <= cnt < reg + length:
                    data.append(chr(int(self.rfid.data_layer.data[key]) >> 8))
                    data.append(chr(int(self.rfid.data_layer.data[key]) & 0xFF))
                cnt += 1
            return data

        if fce == 16:
            raise BadFceError("MODBUS exception - rfid unsupported function 0x10")

    def process_esp_flash_data(self, fce: int, length: int, reg: int, receive_data=None) -> list:

        esp_data = self.config.flash
        reg -= 3000

        if fce == 3:
            new_esp_reg = list(i for i in esp_data.keys())
            data = list()
            for i in range(reg, (reg + length)):
                variable = int(esp_data[new_esp_reg[i]].replace(".", ""))
                data.append(chr(int(variable) >> 8))
                data.append(chr(int(variable) & 0xFF))
            return data

        if fce == 16:
            values = list(receive_data[i] for i in range(0, length * 2))
            cnt = 0
            for k in range(reg, (reg + length)):
                if cnt < length:
                    list_data = list(esp_data)
                    self.config.handle_configure(variable=list_data[reg + cnt],
                                                 value=int((values[cnt * 2] << 8) | values[(cnt * 2) + 1]))
                    cnt = cnt + 1
                else:
                    break
            reg += 3000
            data = list()
            data.append(chr(int(reg) >> 8))
            data.append(chr(int(reg) & 0xFF))
            return data

    def process_esp_ram_data(self, fce: int, length: int, reg: int, receive_data=None) -> list:

        esp_data = self.config.ram
        reg -= 3100
        # modbus function 0x03
        if fce == 3:
            new_esp_reg = list(i for i in esp_data.keys())
            data = list()
            for i in range(reg, (reg + length)):
                variable = int(esp_data[new_esp_reg[i]])
                data.append(chr(int(variable) >> 8))
                data.append(chr(int(variable) & 0xFF))
            return data

        if fce == 16:
            values = list(receive_data[i] for i in range(0, length * 2))
            cnt = 0
            for k in range(reg, (reg + length)):
                if cnt < length:
                    list_data = list(esp_data)
                    if list_data[reg + cnt] in self.config.ram:
                        self.config.ram[list_data[reg + cnt]] = int((values[cnt * 2] << 8) | values[(cnt * 2) + 1])
                    cnt = cnt + 1
                else:
                    break
            reg += 3100
            data = list()
            data.append(chr(int(reg) >> 8))
            data.append(chr(int(reg) & 0xFF))
            return data

    def process_opt_data(self, fce: int) -> list:
        if fce == 3:
            data = list()
            data.append(chr(int(self.evse.data_layer.data["EV_STATE"]) >> 8))
            data.append(chr(int(self.evse.data_layer.data["EV_STATE"]) & 0xFF))

            data.append(chr(int(self.wattmeter.data_layer.data["P1"]) >> 8))
            data.append(chr(int(self.wattmeter.data_layer.data["P1"]) & 0xFF))
            data.append(chr(int(self.wattmeter.data_layer.data["P2"]) >> 8))
            data.append(chr(int(self.wattmeter.data_layer.data["P2"]) & 0xFF))
            data.append(chr(int(self.wattmeter.data_layer.data["P3"]) >> 8))
            data.append(chr(int(self.wattmeter.data_layer.data["P3"]) & 0xFF))

            data.append(chr(int(self.rfid.data_layer.data["CNT"]) >> 8))
            data.append(chr(int(self.rfid.data_layer.data["CNT"]) & 0xFF))
            data.append(chr(int(self.rfid.data_layer.data["LEN"]) >> 8))
            data.append(chr(int(self.rfid.data_layer.data["LEN"]) & 0xFF))
            data.append(chr(int(self.rfid.data_layer.data["ID-1"]) >> 8))
            data.append(chr(int(self.rfid.data_layer.data["ID-1"]) & 0xFF))
            data.append(chr(int(self.rfid.data_layer.data["ID-2"]) >> 8))
            data.append(chr(int(self.rfid.data_layer.data["ID-2"]) & 0xFF))
            data.append(chr(int(self.rfid.data_layer.data["ID-3"]) >> 8))
            data.append(chr(int(self.rfid.data_layer.data["ID-3"]) & 0xFF))
            data.append(chr(int(self.rfid.data_layer.data["ID-4"]) >> 8))
            data.append(chr(int(self.rfid.data_layer.data["ID-4"]) & 0xFF))
            data.append(chr(int(self.rfid.data_layer.data["ID-5"]) >> 8))
            data.append(chr(int(self.rfid.data_layer.data["ID-5"]) & 0xFF))

            data.append(chr(int(self.config.flash['in,EVSE-MAX-CURRENT-A']) >> 8))
            data.append(chr(int(self.config.flash['in,EVSE-MAX-CURRENT-A']) & 0xFF))

            return data

        if fce == 16:
            raise BadFceError("MODBUS exception - rfid unsupported function 0x10")


class BadDataLengthError(ValueError):
    pass


class BadFceError(ValueError):
    pass


class BadIdError(ValueError):
    pass
