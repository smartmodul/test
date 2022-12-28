from time import sleep
import uselect as select
import uasyncio as asyncio
import modbus
from machine import UART
import uasyncio as asyncio
from machine import Pin
import ulogging as  logging

class ModbusSlave:
    
    def __init__(self,baudrate,wattmeter, evse, rfid, config, debug=True):
        self.DE = Pin(15, Pin.OUT) 
        self.uart =  UART(2,baudrate)
        self.uart.init(baudrate, bits=8, parity=None,timeout=1, stop=1) # init with given parameters
        self.modbusClient = modbus.Modbus()
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.sreader = asyncio.StreamReader(self.uart)
        self.wattmeter = wattmeter
        self.evse = evse
        self.rfid = rfid
        self.config = config
        if debug:        
            logging.basicConfig(logging.DEBUG)
        self.LOGGER = logging.getLogger(__name__)
        #self.LOGGER.setLevel('DEBUG')

    async def run(self):
        while True:
            self.DE.on()
            res = await self.sreader.read(-1)
            try:
                if(len(res)<8):
                    continue
                self.LOGGER.debug(" Received Data: {}".format(res))
                result = self.modbusCheckProccess(res)
                self.LOGGER.debug("Sended Data: {}".format(result))
                
                self.DE.off()
                await self.swriter.awrite(result)
                await asyncio.sleep_ms(60)
            except Exception as e:
                self.LOGGER.error("run client modbus slave exception: {}".format(e))


            
    def modbusCheckProccess(self, receiveData):

        ID = receiveData[0]
        FCE = receiveData[1]
        REG = int((receiveData[2]<<8) | receiveData[3])
        LEN = int((receiveData[4]<<8) | receiveData[5])

        if LEN > 20:
            raise badDataLengthError("MODBUS exception - unsuported data length")

        if (FCE != 3) and (FCE != 16):
            raise badFceError("MODBUS exception - unsupported function")

        if ID != int(self.config.flash['in,MODBUS-ID']):
            raise badIDError("MODBUS exception - unsupported id")
        
        if FCE == 16:
            if len(receiveData) != 9+LEN*2:
                raise badIDError("MODBUS exception - data is to short")

        UD = list()
        if (REG >= 1000) and ((REG+LEN-1) < (1008)):
            UD = self.proccessEvseData(FCE,LEN,REG)
                
        if (REG >= 2000) and ((REG+LEN-1) < (2008)):
            UD = self.proccessRfidData(FCE,LEN,REG)

        if (REG >= 3000) and ((REG+LEN-1) < (3011)):
            UD = self.proccessEspFlashData(FCE,LEN,REG,receiveData[7:2*LEN+7])

        if (REG >= 3100) and ((REG+LEN-1) < (3102)):
            UD = self.proccessEspRamData(FCE,LEN,REG,receiveData[7:2*LEN+7])
    
        if (REG >= 4000) and ((REG+LEN-1) < (4023)):
            UD = self.proccessWattmeterData(FCE,LEN,REG)

        if (REG == 5000) and ((REG+LEN-1) < (5012)):
            UD = self.proccessOptData(FCE,LEN,REG)            

        sendData = list()
        sendData.append(chr(int(self.config.flash['in,MODBUS-ID'])))
        sendData.append(chr(FCE))
            
        if FCE == 3:
            sendData.append(chr(LEN*2))
            if UD != None:
                sendData += UD
            else:
                sendData[3] = chr(0)
                sendData[4] = chr(0)
        
        elif FCE == 16:
            if UD != None:
                sendData+= UD
                sendData.append(chr(LEN>>8))
                sendData.append(chr(LEN&0xff))
            else:
                sendData[5] = 0
                sendData[6] = 0

        crc = self.modbusClient.calcCRC(sendData)
        sendData.append(chr(crc & 0xff))
        sendData.append(chr(crc >> 8))
        
        RED = bytearray()
        for i in sendData:
            RED += bytes([ord(i)])

        return RED
        
    def proccessWattmeterData(self,fce,length,reg):

        reg = reg - 4000
        if fce == 3:
            cnt = 0
            data = list()
            for key in self.wattmeter.dataLayer.data:
                if cnt >= reg and cnt < reg+length:
                    data.append(chr(int(self.wattmeter.dataLayer.data[key]) >> 8))
                    data.append(chr(int(self.wattmeter.dataLayer.data[key]) & 0xFF))
                cnt +=1
            return data
       
        if fce == 16:
            raise badFceError("MODBUS exception - wattmeter unsupported function 0x10")               
   
    def proccessEvseData(self,fce,length,reg):
        reg = reg - 1000
        if fce == 3:
            cnt = 0
            data = list()
            for key in self.evse.dataLayer.data:
                if cnt >= reg and cnt < reg+length:
                    data.append(chr(int(self.evse.dataLayer.data[key]) >> 8))
                    data.append(chr(int(self.evse.dataLayer.data[key]) & 0xFF))
                cnt +=1
            return data
       
        if fce == 16:
            if reg == 4:
                self.evse.clearBits = 1
                data = list()
                data.append(chr(int(reg) >> 8))
                data.append(chr(int(reg) & 0xFF))
                return data
            else:
                raise badFceError("MODBUS exception - evse unsupported function 0x10")  

    def proccessRfidData(self,fce,length,reg):
        reg = reg - 2000
        if fce == 3:
            cnt = 0
            data = list()
            for key in self.rfid.dataLayer.data:
                if cnt >= reg and cnt < reg+length:
                    data.append(chr(int(self.rfid.dataLayer.data[key]) >> 8))
                    data.append(chr(int(self.rfid.dataLayer.data[key]) & 0xFF))
                cnt +=1
            return data
       
        if fce == 16:
            raise badFceError("MODBUS exception - rfid unsupported function 0x10")               
    
    
    def proccessEspFlashData(self,fce,length,reg,receiveData=None):

        espData = self.config.flash
        reg -= 3000

        if fce == 3:
            newESPReg = list(i for i in espData.keys())
            data = list()
            for i in range(reg,(reg+length)):
                hodnota = int(espData[newESPReg[i]].replace(".",""))
                data.append(chr(int(hodnota) >> 8))
                data.append(chr(int(hodnota) & 0xFF))
            return data
                    
        if fce == 16:
            values = list(receiveData[i] for i in range(0,length*2))
            cnt = 0
            for k in range(reg,(reg+length)):
                if cnt<length:
                    listData = list(espData)
                    self.config.handle_configure(variable=listData[reg+cnt],value=int((values[cnt*2]<<8) | values[(cnt*2)+1]))
                    cnt = cnt + 1
                else:
                    break
            reg += 3000
            data = list()
            data.append(chr(int(reg) >> 8))
            data.append(chr(int(reg) & 0xFF))
            return data
        

    def proccessEspRamData(self,fce,length,reg,receiveData=None):

        espData = self.config.ram
        reg -= 3100
        #modbus function 0x03
        if fce == 3:
            newESPReg = list(i for i in espData.keys())
            data = list()
            for i in range(reg,(reg+length)):
                hodnota = int(espData[newESPReg[i]])
                data.append(chr(int(hodnota) >> 8))
                data.append(chr(int(hodnota) & 0xFF))
            return data
                    
        if fce == 16:
            values = list(receiveData[i] for i in range(0,length*2))
            cnt = 0
            for k in range(reg,(reg+length)):
                if cnt<length:
                    listData = list(espData)
                    if listData[reg+cnt] in self.config.ram:
                        self.config.ram[listData[reg+cnt]] = int((values[cnt*2]<<8) | values[(cnt*2)+1])
                    cnt = cnt + 1
                else:
                    break
            reg += 3100
            data = list()
            data.append(chr(int(reg) >> 8))
            data.append(chr(int(reg) & 0xFF))
            return data        

    def proccessOptData(self,fce,length,reg):
        if fce == 3:
            data = list()
            data.append(chr(int(self.evse.dataLayer.data["EV_STATE"]) >> 8))
            data.append(chr(int(self.evse.dataLayer.data["EV_STATE"]) & 0xFF))
            
            data.append(chr(int(self.wattmeter.dataLayer.data["P1"]) >> 8))
            data.append(chr(int(self.wattmeter.dataLayer.data["P1"]) & 0xFF))
            data.append(chr(int(self.wattmeter.dataLayer.data["P2"]) >> 8))
            data.append(chr(int(self.wattmeter.dataLayer.data["P2"]) & 0xFF))
            data.append(chr(int(self.wattmeter.dataLayer.data["P3"]) >> 8))
            data.append(chr(int(self.wattmeter.dataLayer.data["P3"]) & 0xFF))

            data.append(chr(int(self.rfid.dataLayer.data["CNT"]) >> 8))
            data.append(chr(int(self.rfid.dataLayer.data["CNT"]) & 0xFF))
            data.append(chr(int(self.rfid.dataLayer.data["LEN"]) >> 8))
            data.append(chr(int(self.rfid.dataLayer.data["LEN"]) & 0xFF))            
            data.append(chr(int(self.rfid.dataLayer.data["ID-1"]) >> 8))
            data.append(chr(int(self.rfid.dataLayer.data["ID-1"]) & 0xFF))
            data.append(chr(int(self.rfid.dataLayer.data["ID-2"]) >> 8))
            data.append(chr(int(self.rfid.dataLayer.data["ID-2"]) & 0xFF))
            data.append(chr(int(self.rfid.dataLayer.data["ID-3"]) >> 8))
            data.append(chr(int(self.rfid.dataLayer.data["ID-3"]) & 0xFF))
            data.append(chr(int(self.rfid.dataLayer.data["ID-4"]) >> 8))
            data.append(chr(int(self.rfid.dataLayer.data["ID-4"]) & 0xFF))
            data.append(chr(int(self.rfid.dataLayer.data["ID-5"]) >> 8))
            data.append(chr(int(self.rfid.dataLayer.data["ID-5"]) & 0xFF))            

            data.append(chr(int(self.config.flash['in,EVSE-MAX-CURRENT-A']) >> 8))
            data.append(chr(int(self.config.flash['in,EVSE-MAX-CURRENT-A']) & 0xFF))
                                                
            return data
       
        if fce == 16:
            raise badFceError("MODBUS exception - rfid unsupported function 0x10") 
class badDataLengthError(ValueError):
    pass
class badFceError(ValueError):
    pass
class badIDError(ValueError):
    pass        