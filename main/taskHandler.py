import uasyncio as asyncio
import ledHandler
import time
from main import com_1

from ntptime import settime
from asyn import Lock
from gc import mem_free, collect
from machine import Pin,WDT, RTC
from main import webServerApp
from main import wattmeter
from main import evse
from main import rfid
from main.__config__ import Config
#from main import cloud
from main import modbusSlave


EVSE_ERR = 1
WATTMETER_ERR = 2
RFID_ERR = 3
WEBSERVER_CANCELATION_ERR = 4
WIFI_HANDLER_ERR = 8
TIME_SYNC_ERR = 16

AP = 1
WIFI = 2

class TaskHandler:
    def __init__(self,wifi):
        uart1Interface = com_1.Interface(9600,lock = Lock(200)) # UART PRO WATTMETER, EVSE a RFID
        self.setting = Config()
        self.rfid = rfid.Rfid(uart1Interface,self.setting)
        self.wattmeter = wattmeter.Wattmeter(uart1Interface,self.setting) #Create instance of Wattmeter
        self.evse = evse.Evse(self.wattmeter, uart1Interface, self.setting)
        self.webServerApp = webServerApp.WebServerApp(wifi,self.wattmeter, self.evse, uart1Interface,self.setting) #Create instance of Webserver App
        self.modbusSlave = modbusSlave.ModbusSlave(9600,self.wattmeter,self.evse, self.rfid, self.setting)
        
        
        self.settingAfterNewConnection = False
        self.wdt = WDT(timeout=60000) 

        self.wifiManager = wifi
        self.ledErrorHandler = ledHandler.ledHandler(21,1,2,40)
        self.ledWifiHandler =  ledHandler.ledHandler(22,1,2,20) # set pin high on creation
        self.errors = 0
        self.tryOfConnections = 0
        self.wifiManager.turnONAp()#povolit Access point
        self.apTimeout = 600

 

    def memFree(self):
        before = mem_free()
        collect()
        after = mem_free()
        #print("Memory before: {} & After: {}".format(before,after))
        

    async def ledWifi(self):
        while True:
            await self.ledWifiHandler.ledHandler()
            await asyncio.sleep(0.1)

    async def ledError(self):
        while True:
            await self.ledErrorHandler.ledHandler()
            await asyncio.sleep(0.1)
            
    async def timeHandler(self):
        while True:
            if self.wifiManager.isConnected() and self.wattmeter.timeInit == False:
                try:
                    print("Setting time")
                    settime()
                    rtc=RTC()
                    import utime
                    tampon1=utime.time() 
                    tampon2=tampon1+int(self.setting.getConfig()["in,TIME-ZONE"])*3600
                    (year, month, mday, hour, minute, second, weekday, yearday)=utime.localtime(tampon2)
                    rtc.datetime((year, month, mday, 0, hour, minute, second, 0))
                    self.wattmeter.timeInit = True
                    self.ledErrorHandler.removeState(TIME_SYNC_ERR)
                    self.errors &= ~TIME_SYNC_ERR
                except Exception as e:
                    self.ledErrorHandler.addState(TIME_SYNC_ERR)
                    self.errors |= TIME_SYNC_ERR
                    print("Error during time setting: {}".format(e))        
                
            await asyncio.sleep(10)
            self.memFree()
            
  
    async def wifiHandler(self):
        while True:
            try:
                self.ledWifiHandler.addState(AP)
                if(self.wifiManager.isConnected() == True):
                    if self.apTimeout > 0:
                        self.apTimeout -= 1
                    elif((int(self.setting.flash['sw,Wi-Fi AP']) == 0) and  self.apTimeout == 0):
                        self.wifiManager.turnOffAp()
                        self.ledWifiHandler.removeState(AP)
                    elif (int(self.setting.flash['sw,Wi-Fi AP']) == 1):
                        self.wifiManager.turnONAp()
                    self.ledWifiHandler.addState(WIFI)
                    if(self.settingAfterNewConnection == False):
                        self.settingAfterNewConnection = True
                else:
                    self.ledWifiHandler.removeState(WIFI)
                    if (len(self.wifiManager.read_profiles())!= 0):                            
                        if(self.tryOfConnections > 30):
                            self.tryOfConnections = 0
                            result = await self.wifiManager.get_connection()
                            if result:
                                self.settingAfterNewConnection = False
                        self.tryOfConnections = self.tryOfConnections + 1
                self.ledErrorHandler.removeState(WIFI_HANDLER_ERR)
                self.errors &= ~WIFI_HANDLER_ERR
            except Exception as e:
                self.ledErrorHandler.addState(WIFI_HANDLER_ERR)
                self.errors |= WIFI_HANDLER_ERR
                print("wifiHandler exception : {}".format(e))
            self.memFree()
            await asyncio.sleep(2)
                        
    async def interfaceHandler(self):
        while True:
            try:
                await self.evse.evseHandler()
                self.ledErrorHandler.removeState(EVSE_ERR)
                self.errors &= ~EVSE_ERR
            except Exception as e:
                self.ledErrorHandler.addState(EVSE_ERR)
                self.errors |= EVSE_ERR
                print("EVSE error: {}".format(e))
            self.memFree()
            try:
                await self.wattmeter.wattmeterHandler()
                self.ledErrorHandler.removeState(WATTMETER_ERR)
                self.errors &= ~WATTMETER_ERR
            except Exception as e:
                self.ledErrorHandler.addState(WATTMETER_ERR)
                self.errors |= WATTMETER_ERR
                print("WATTMETER error: {}".format(e))
             
            try:
                await self.rfid.rfidHandler()
            except Exception as e:
                print("RFID error: {}".format(e))
            
            self.memFree()
            await asyncio.sleep(1.5)

    #Handler for time
    async def systemHandler(self):
        while True:
            self.setting.flash['ERRORS'] = (str)(self.errors)
            self.wdt.feed()#WDG Handler 
            self.memFree()
            await asyncio.sleep(1)
            
    def mainTaskHandlerRun(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.wifiHandler())
        loop.create_task(self.systemHandler()) 
        loop.create_task(self.timeHandler())
        loop.create_task(self.interfaceHandler())
        loop.create_task(self.ledError())
        loop.create_task(self.ledWifi())
        loop.create_task(self.webServerApp.webServerRun())
        loop.create_task(self.modbusSlave.run())
        loop.run_forever()