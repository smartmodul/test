import ujson as json
import time
import uasyncio as asyncio
from machine import Pin,UART
from gc import collect, mem_free
from collections import OrderedDict

class Wattmeter:
     
    def __init__(self,commInterface,config):

        self.relay  = Pin(25, Pin.OUT)
        self.relay.off()
        self.wattmeterInterface = commInterface
        self.dataLayer = DataLayer()
        self.fileHandler = fileHandler()
        self.DAILY_CONSUMPTION = 'daily_consumption.dat'
        self.timeInit = False
        self.timeOfset = False
        self.lastMinute =  0
        self.lastHour = 0
        self.lastDay =  0
        self.lastMonth = 0
        self.lastYear = 0
        self.test = 0
        self.startUpTime = 0
        self.config = config
        self.dataLayer.data['ID'] = self.config.flash['ID'] 
        self.WATTMETER_ID = 100

        self.tst = 0

    async def wattmeterHandler(self):
        #Read data from wattmeter
        if (self.timeOfset == False)and(self.timeInit == True):
            self.startUpTime = time.time()
            self.lastMinute =  int(time.localtime()[4])
            self.lastDay =  int(time.localtime()[2])
            self.lastMonth = int(time.localtime()[1])
            self.lastYear =  int(time.localtime()[0])
            self.dataLayer.data['D'] = self.fileHandler.readData(self.DAILY_CONSUMPTION)
            self.dataLayer.data["M"] = self.fileHandler.getMonthlyEnergy(self.DAILY_CONSUMPTION)
            self.timeOfset = True
            
        self.dataLayer.data['RUN_TIME'] = time.time() - self.startUpTime
        curentYear = str(time.localtime()[0])[-2:] 
        self.dataLayer.data['WATTMETER_TIME'] = ("{0:02}.{1:02}.{2}  {3:02}:{4:02}:{5:02}".format(time.localtime()[2],time.localtime()[1],curentYear,time.localtime()[3],time.localtime()[4],time.localtime()[5]))
        status = await self.__readWattmeter_data(6000,22)
        #Check if time-sync puls must be send
        if (self.lastMinute is not int(time.localtime()[4]))and(self.timeInit == True):
            
            if len(self.dataLayer.data["Pm"])<61:
                self.dataLayer.data["Pm"].append(self.dataLayer.data['Em']*6)#self.dataLayer.data["P1"])
            else:
                self.dataLayer.data["Pm"] = self.dataLayer.data["Pm"][1:]
                self.dataLayer.data["Pm"].append(self.dataLayer.data['Em']*6)#self.dataLayer.data["P1"])
            
            self.dataLayer.data["Pm"][0] = len(self.dataLayer.data["Pm"])
            async with self.wattmeterInterface as w:
                await w.writeRegister(100,[1],self.WATTMETER_ID)
            self.lastMinute = int(time.localtime()[4]) 

        if self.timeInit:
            if self.lastHour is not int(time.localtime()[3]):
                async with self.wattmeterInterface as w:
                    await w.writeRegister(101,[1],self.WATTMETER_ID)
                self.lastHour = int(time.localtime()[3])
                if len(self.dataLayer.data["Es"])<97:
                    self.dataLayer.data["Es"].append(self.lastHour)
                    self.dataLayer.data["Es"].append(self.dataLayer.data['Eh'])
                    self.dataLayer.data["Es"].append(self.dataLayer.data['En'])
                    self.dataLayer.data["Es"].append(self.dataLayer.data['A'])
                else:
                    self.dataLayer.data["Es"] = self.dataLayer.data["Es"][4:]
                    self.dataLayer.data["Es"].append(self.lastHour)
                    self.dataLayer.data["Es"].append(self.dataLayer.data['Eh'])
                    self.dataLayer.data["Es"].append(self.dataLayer.data['En'])
                    self.dataLayer.data["Es"].append(self.dataLayer.data['A'])
            
                self.dataLayer.data["Es"][0] = len(self.dataLayer.data["Es"])
            
            else:
                if len(self.dataLayer.data["Es"])<97:
                    self.dataLayer.data["Es"][len(self.dataLayer.data["Es"])-3]= self.dataLayer.data['Eh']
                    self.dataLayer.data["Es"][len(self.dataLayer.data["Es"])-2]= self.dataLayer.data['En']
                    self.dataLayer.data["Es"][len(self.dataLayer.data["Es"])-1]=  self.dataLayer.data['A']
                else:
                    self.dataLayer.data["Es"][94]= self.dataLayer.data['Eh']
                    self.dataLayer.data["Es"][95]= self.dataLayer.data['En']
                    self.dataLayer.data["Es"][96]=  self.dataLayer.data['A']
        
        if (self.lastDay is not int(time.localtime()[2]))and self.timeInit and self.timeOfset:

            day = {("{0:02}/{1:02}/{2}".format(self.lastMonth,self.lastDay ,str(self.lastYear)[-2:] )) : [self.dataLayer.data["E1dP"] + self.dataLayer.data["E2dP"]+self.dataLayer.data["E3dP"], self.dataLayer.data["E1dN"] + self.dataLayer.data["E2dN"]+self.dataLayer.data["E3dN"]]}
            async with self.wattmeterInterface as w:
                await w.writeRegister(102,[1],self.WATTMETER_ID)
            
            self.lastYear = int(time.localtime()[0])
            self.lastMonth = int(time.localtime()[1])
            self.lastDay = int(time.localtime()[2])
            self.fileHandler.writeData(self.DAILY_CONSUMPTION, day)
            self.dataLayer.data["D"] =  self.fileHandler.readData(self.DAILY_CONSUMPTION,31)
            self.dataLayer.data["M"] = self.fileHandler.getMonthlyEnergy(self.DAILY_CONSUMPTION)

    async def __readWattmeter_data(self,reg,length):
        async with self.wattmeterInterface as w:
                receiveData =  await w.readRegister(reg,length,self.WATTMETER_ID)
        try:
            if (receiveData != "Null") and (reg == 6000):
                self.dataLayer.data['I1'] =     int(((receiveData[0]) << 8) | (receiveData[1]))
                self.dataLayer.data['I2'] =     int(((receiveData[2]) << 8) | (receiveData[3]))
                self.dataLayer.data['I3'] =     int(((receiveData[4]) << 8) | (receiveData[5]))
                self.dataLayer.data['U1'] =     int(((receiveData[6]) << 8) | (receiveData[7]))
                self.dataLayer.data['U2'] =     int(((receiveData[8]) << 8) | (receiveData[9]))
                self.dataLayer.data['U3'] =     int(((receiveData[10]) << 8) | (receiveData[11]))
                self.dataLayer.data['P1'] =     int(((receiveData[12]) << 8) | (receiveData[13]))
                self.dataLayer.data['P2'] =     int(((receiveData[14]) << 8) | (receiveData[15]))
                self.dataLayer.data['P3'] =     int(((receiveData[16]) << 8) | (receiveData[17]))
                a = (int)(receiveData[18]<< 8)  | receiveData[19]
                if a == 1 and  '1'== self.config.flash['sw,AC IN ACTIVE: HIGH']:
                    self.dataLayer.data['A'] = 1
                elif a == 0 and  '0'== self.config.flash['sw,AC IN ACTIVE: HIGH']:
                    self.dataLayer.data['A'] = 1
                else:
                    self.dataLayer.data['A'] = 0           
                #2502
                self.dataLayer.data['Em'] = int(((receiveData[20]) << 8) | receiveData[21]) + int(((receiveData[22])<< 8)|receiveData[23]) + int((receiveData[24] << 8) |receiveData[25])
                #2902
                self.dataLayer.data["EpDP"]= int(((receiveData[26]) << 8) | receiveData[27]) + int(((receiveData[28]) << 8) | receiveData[29]) + int(((receiveData[30])<< 8) | receiveData[31])
                #4000
                self.dataLayer.data["E1tP"]= int((receiveData[34] << 24) | (receiveData[35] << 16) | (receiveData[32] << 8) | receiveData[33])
                self.dataLayer.data["E2tP"]= int((receiveData[38] << 24) | (receiveData[39] << 16) | (receiveData[36] << 8) | receiveData[37])
                self.dataLayer.data["E3tP"]= int((receiveData[42] << 24) | (receiveData[43] << 16) | (receiveData[40] << 8) | receiveData[41])
                return 0

            else:   
                return 1
            
        except Exception as e:
            return -1
        
               
class DataLayer:
    def __str__(self):
        return json.dumps(self.data)           

    def __init__(self):
        self.data = OrderedDict()
        self.data['I1'] = 0              #I1
        self.data['I2'] = 0              #I2
        self.data['I3'] = 0              #I3
        self.data['U1'] = 0
        self.data['U2'] = 0
        self.data['U3'] = 0
        self.data['P1'] = 0
        self.data['P2'] = 0
        self.data['P3'] = 0
        self.data['W1'] = 0           #positive power peak L1
        self.data['W2'] = 0           #positive power peak L2
        self.data['W3'] = 0           #positive power peak L3
        self.data['Em'] = 0            #Pavg per minute
        self.data['En'] = 0            #Pavg per minute
        self.data['Eh'] = 0             #positive hour energy
        self.data['A'] = 0                #AC_IN
        self.data["E1dP"] = 0
        self.data["E2dP"] = 0
        self.data["E3dP"] = 0
        self.data["EpDP"] = 0#positive previous day Energy L1,L2,L3
        self.data["E1tP"] = 0#positive total Energy L1
        self.data["E2tP"] = 0#positive total Energy L1
        self.data["E3tP"] = 0#positive total Energy L1
        self.data['ID'] = 0
        self.data["Pm"] = [0]                               #minute power
        self.data["Es"] = [0]                                 #Hour energy
        self.data['D'] = None                             #Daily energy
        self.data['M'] = None                            #Monthly energy
        self.data['RUN_TIME'] = 0
        self.data['WATTMETER_TIME'] = 0
  
class fileHandler:
                
    def readData(self,file,length=None):
        data = []
        try:
            #b = mem_free()
            csv_gen = self.csv_reader(file)
            row_count = 0
            data = []
            for row in csv_gen:
                collect()
                row_count += 1

            csv_gen = self.csv_reader(file)
            cnt = 0
            for i in csv_gen:
                cnt+=1
                if cnt>row_count-31:
                    data.append(i.replace("\n",""))
                collect()
            #print("Mem free before:{}; after:{}; rozdil:{} ".format(b,mem_free(),b-mem_free()))
            return data
        except Exception as e:
            return [] 
    
    def csv_reader(self,file_name):
        for row in open(file_name, "r"):
            try:
                yield row
            except StopIteration:
                return

    def getMonthlyEnergy(self,file):
        energy = []
        lastMonth = 0
        lastYear = 0
        positiveEnergy = 0
        negativeEnergy = 0

        try:
            csv_gen = self.csv_reader(file)
            for line in csv_gen:
                line = line.replace("\n","").replace("/",":").replace("[","").replace("]","").replace(",",":").replace(" ","").split(":")
                #print("0 - Mem free before:{}; after:{}; rozdil:{} ".format(b,mem_free(),b-mem_free()))
                if lastMonth == 0:
                    lastMonth = int(line[0])
                    lastYear = int(line[2])

                if lastMonth != int(line[0]):
                    if len(energy)<12:                 
                        energy.append("{}/{}:[{},{}]".format(lastMonth,lastYear,positiveEnergy,negativeEnergy))
                    else:
                        energy = energy[1:]
                        energy.append("{}/{}:[{},{}]".format(lastMonth,lastYear,positiveEnergy,negativeEnergy))
                    positiveEnergy = 0
                    negativeEnergy = 0
                    lastMonth = int(line[0])
                    lastYear = int(line[2])

                positiveEnergy += int(line[3])
                negativeEnergy += int(line[4])
                collect()                

            if len(energy)<12:                 
                energy.append("{}/{}:[{},{}]".format(lastMonth,lastYear,positiveEnergy,negativeEnergy))
            else:
                energy = energy[1:]
                energy.append("{}/{}:[{},{}]".format(lastMonth,lastYear,positiveEnergy,negativeEnergy))
            return energy    
                
        except Exception as e:
            print("Error: ",e)

    def writeData(self,file,data):
        lines = []
        for variable, value in data.items():
            lines.append(("%s:%s\n" % (variable, value)).replace(" ",""))
            
        with open(file, "a+") as f:
            f.write(''.join(lines))
