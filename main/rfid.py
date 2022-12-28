import json
import uasyncio as asyncio
import time
import ulogging as  logging
from machine import Pin,UART
from collections import OrderedDict

class Rfid():
 
    
    def __init__(self, commInterface,config):
        #self.commInterface = commInterface
        self.rfidInterface = commInterface
        self.setting = config
        self.dataLayer = DataLayer()
        self.RFID_ID = 101
    
    async def rfidHandler(self):
        try:
            await self.__readRfid_data(2000,7) #,self.RFID_ID
            return False#self.checkRfidDatabase(ID)
        except Exception as e:
            #logging.("rfidHandler fce: {}".format(e))
            return False
        
    async def __readRfid_data(self,reg,lenght): 
        async with self.rfidInterface as r:
            receiveData =  await r.readRegister(reg,lenght,self.RFID_ID)
        try:
            if reg == 2000 and (receiveData != None):
                self.dataLayer.data["CNT"] = int(((receiveData[0]) << 8)  | receiveData[1])
                self.dataLayer.data["LEN"] = int(((receiveData[2]) << 8)  | receiveData[3])
                            
                if  4 == self.dataLayer.data["LEN"] :
                    self.dataLayer.data["ID-1"] = int(((receiveData[5]) << 8)  | receiveData[4])
                    self.dataLayer.data["ID-2"] = int(((receiveData[7]) << 8)  | receiveData[6])
                    self.dataLayer.data["ID-3"] = 0
                    self.dataLayer.data["ID-4"] = 0
                    self.dataLayer.data["ID-5"] = 0
                    
                if  7 == self.dataLayer.data["LEN"] :
                    self.dataLayer.data["ID-1"] = int(((receiveData[5]) << 8)  | receiveData[4])
                    self.dataLayer.data["ID-2"] = int(((receiveData[7]) << 8)  | receiveData[6])
                    self.dataLayer.data["ID-3"] = int(((receiveData[9]) << 8)  | receiveData[8])
                    self.dataLayer.data["ID-4"] = int(receiveData[10])
                    self.dataLayer.data["ID-5"] = 0
                    
                if  10 == self.dataLayer.data["LEN"] :
                    self.dataLayer.data["ID-1"] = int(((receiveData[5]) << 8)  | receiveData[4])
                    self.dataLayer.data["ID-2"] = int(((receiveData[7]) << 8)  | receiveData[6])
                    self.dataLayer.data["ID-3"] = int(((receiveData[9]) << 8)  | receiveData[8])
                    self.dataLayer.data["ID-4"] = int(((receiveData[11]) << 8)  | receiveData[10])
                    self.dataLayer.data["ID-5"] = int(((receiveData[13]) << 8)  | receiveData[12])
                return 1
            else:
                return 0      

        except Exception as e:
            raise Exception("reading error: {}".format(e))

    def checkRfidDatabase(self,ID):

        return True

class DataLayer:
    def __str__(self):
        return json.dumps(self.data)
        
    def __init__(self):
        self.data = OrderedDict()
        self.data["CNT"] = 0        
        self.data["LEN"] = 0
        self.data["ID-1"] = 0
        self.data["ID-2"] = 0
        self.data["ID-3"] = 0
        self.data["ID-4"] = 0
        self.data["ID-5"] = 0
        self.data["USER"] = "Uknown"