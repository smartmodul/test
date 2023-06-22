import modbus
from machine import UART
import uasyncio as asyncio
from machine import Pin


class Interface:

    def __init__(self, baudrate: int, lock):
        self.lock = lock
        self.de = Pin(23, Pin.OUT)
        self.uart = UART(1, baudrate)
        self.uart.init(baudrate, bits=8, parity=None, stop=1, timeout=10, rx=26, tx=27)
        self.modbus_client = modbus.Modbus()

    async def __aenter__(self):
        await self.lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.de.off()
        self.lock.release()

    async def write_register(self, reg: int, data: bytearray, modbus_id: int):

        write_regs = self.modbus_client.write_regs(reg, data, modbus_id)
        self.uart.write(write_regs)
        # self.uart.flush()
        self.de.on()

        if modbus_id == 100:
            await asyncio.sleep_ms(80)
        elif modbus_id == 101:
            await asyncio.sleep_ms(10)
        else:
            await asyncio.sleep_ms(70)

        self.de.off()
        receive_data = self.uart.read()
        if 0 == self.modbus_client.mbrtu_data_processing(receive_data, modbus_id):
            return bytearray([receive_data[2], receive_data[3]])
        else:
            return None

    async def read_register(self, reg: int, length: int, modbus_id: int):
        read_regs = self.modbus_client.read_regs(reg, length, modbus_id)
        self.uart.write(read_regs)
        # self.uart.flush()
        self.de.on()

        if modbus_id == 100:
            await asyncio.sleep_ms(80)
        elif modbus_id == 101:
            await asyncio.sleep_ms(50)
        else:
            await asyncio.sleep_ms(90)

        receive_data = self.uart.read()

        if receive_data and (0 == self.modbus_client.mbrtu_data_processing(receive_data, modbus_id)):
            return bytearray(receive_data[i + 3] for i in range(0, (length * 2)))
        else:
            return None
