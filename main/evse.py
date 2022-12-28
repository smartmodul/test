import json
import uasyncio as asyncio
import time
import math
from collections import OrderedDict

class Evse():
 
    
    def __init__(self, wattmeter,evse, config):
        self.evseInterface = evse
        self.dataLayer = DataLayer()
        self.setting = config
        self.wattmeter = wattmeter
        self.regulationLock1 = False
        self.lock1Counter = 0
        self.newChargingProccess = False
        self.EVSE_ID = 1
        self.clearBits = 0

    
    async def evseHandler(self, verify=False, user="Unknown"):
        #first read data from evse
        status = 0
        
        if int(self.setting.ram["EVSE_CURRENT"]) > int(self.setting.flash["in,EVSE-MAX-CURRENT-A"]):
            self.setting.ram["EVSE_CURRENT"] = self.setting.flash["in,EVSE-MAX-CURRENT-A"]
        
        current = int(self.setting.flash["in,EVSE-MAX-CURRENT-A"])
        
        if self.setting.flash["sw,EXTERNAL REGULATION"] is '1':
            current = int(self.setting.ram["EVSE_CURRENT"])

        if self.clearBits == 1:
            async with self.evseInterface as e:
                await e.writeRegister(1004,[0],ID=1)
            self.clearBits = 0

        status = await self.__readEvse_data(1000,8,ID=1)
        if status == -1:
            raise Exception("reading error.")
        try:
            if(status == 0):
                if(self.setting.flash["sw,RFID VERIFICATION"] is '0'):
                    if(self.setting.flash["sw,WHEN AC IN: CHARGING"] is '1'):
                        if self.wattmeter.dataLayer.data["A"] == 1:
                            async with self.evseInterface as e:
                                await e.writeRegister(1000,[current],ID=1)
                        else:
                            async with self.evseInterface as e:
                                await e.writeRegister(1000,[0],ID=1)
                    else:
                        async with self.evseInterface as e:
                            await e.writeRegister(1000,[current],ID=1)

                elif(self.setting.flash["sw,RFID VERIFICATION"] is '1'):
                    if self.setting.ram['RFID_VERIFY'] == 1:
                        if(self.setting.flash["sw,WHEN AC IN: CHARGING"] == '1'):
                            if self.wattmeter.dataLayer.data["A"] == 1:
                                async with self.evseInterface as e:
                                    await e.writeRegister(1000,[current],ID=1)
                            else:
                                async with self.evseInterface as e:
                                    await e.writeRegister(1000,[0],ID=1)
                        else:
                            async with self.evseInterface as e:
                                await e.writeRegister(1000,[current],ID=1)
                    else:
                        async with self.evseInterface as e:
                            await e.writeRegister(1000,[0],ID=1)


        except Exception as e:
            raise Exception("fce handler error: {}".format(e))

          
        
    async def __readEvse_data(self,reg,length,ID):   
        try:
            async with self.evseInterface as e:
                receiveData =  await e.readRegister(reg,length,ID)
            if reg == 1000 and (receiveData != "Null") and (receiveData):
                self.dataLayer.data["ACTUAL_CONFIG_CURRENT"] = int(((receiveData[0]) << 8)  | receiveData[1])
                self.dataLayer.data["ACTUAL_OUTPUT_CURRENT"] = int(((receiveData[2]) << 8)  | receiveData[3])
                self.dataLayer.data["EV_STATE"] = int(((receiveData[4]) << 8)  | receiveData[5])   
                self.dataLayer.data["OPT"] = int(((receiveData[6]) << 8)  | receiveData[7])
                self.dataLayer.data["CLEAR_CMD"] = int(((receiveData[8]) << 8)  | receiveData[9])
                self.dataLayer.data["FW_VERSION"] = int(((receiveData[10]) << 8)  | receiveData[11])
                self.dataLayer.data["EVSE_STATE"] = int(((receiveData[12]) << 8)  | receiveData[13])
                self.dataLayer.data["EVSE_STATUS"] = int(((receiveData[14]) << 8)  | receiveData[15])
                
                self.dataLayer.data["EV_COMM_ERR"] = 0
                return 0
                        
            else: 
                return -1
                 
        except Exception as e:
            if reg == 1000:
                self.dataLayer.data["EV_COMM_ERR"] += 1
                if(self.dataLayer.data["EV_COMM_ERR"] > 30): 
                    self.dataLayer.data["ACTUAL_CONFIG_CURRENT"] = 0
                    self.dataLayer.data["ACTUAL_OUTPUT_CURRENT"] = 0
                    self.dataLayer.data["EV_STATE"] = 0
                    self.dataLayer.data["OPT"] = 0
                    self.dataLayer.data["CLEAR_CMD"] = 0
                    self.dataLayer.data["FW_VERSION"] = 0
                    self.dataLayer.data["EVSE_STATE"] = 0
                    self.dataLayer.data["EVSE_STATUS"] = 0
                    self.dataLayer.data["EV_COMM_ERR"] = 31
            return -1
        
    def verifyRFID(self):
        pass

    def checkIfEVisConnected(self):
        if self.dataLayer.data["EV_STATE"] == 2: #pripojen nebo nabiji
            return True
        return False

    def checkIfEVisCharging(self):
        if self.dataLayer.data["EV_STATE"] == 3: #pripojen nebo nabiji
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