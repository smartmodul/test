import modbus
from machine import UART
import uasyncio as asyncio
from machine import Pin

class Interface:

    def __init__(self,baudrate,lock):
        self.lock = lock
        self.DE = Pin(23, Pin.OUT) 
        self.uart =  UART(1,baudrate)
        self.uart.init(baudrate, bits=8, parity=None, stop=1,timeout=10,rx=26, tx=27) # init with given parameters
        self.modbusClient = modbus.Modbus()
        #self.swriter = asyncio.StreamWriter(self.uart, {})
        #self.sreader = asyncio.StreamReader(self.uart, {})

    async def __aenter__(self):
        await self.lock.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.DE.off()
        self.lock.release()

        
    async def writeRegister(self,reg,data,ID):

        writeRegs = self.modbusClient.write_regs(reg, data,ID)
        self.uart.write(writeRegs)
        self.uart.flush()
        self.DE.on()
            
        if ID == 100:
            await asyncio.sleep_ms(80)
        elif ID == 101:
            await asyncio.sleep_ms(10)
        else:
            await asyncio.sleep_ms(70)
        
        self.DE.off()
        receiveData = self.uart.read()
        if 0 == self.modbusClient.mbrtu_data_processing(receiveData, ID):
            return bytearray([receiveData[2],receiveData[3]])
        else:
            return None


    async def readRegister(self,reg,length,ID):
        readRegs = self.modbusClient.read_regs(reg, length,ID)
        self.uart.write(readRegs)
        self.uart.flush()
        self.DE.on()
            
        if ID == 100:
            await asyncio.sleep_ms(80)
        elif ID == 101:
            await asyncio.sleep_ms(50)
        else:
            await asyncio.sleep_ms(90)
            
        receiveData = self.uart.read()
            
        if receiveData  and  (0 == self.modbusClient.mbrtu_data_processing(receiveData, ID)):
            return bytearray(receiveData[i+3] for i in range(0,(length*2)))
        else:
            return None