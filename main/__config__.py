import bootloader
from collections import OrderedDict
import os

class Config: 
    
    def __init__(self):
        #all variables saved in flash
        self.boot = bootloader.Bootloader('https://github.com/smartmodul/production',"")
        self.flash = OrderedDict()
        self.flash['sw,AUTOMATIC UPDATE'] = '1'                                            #Reg 3000
        self.flash['txt,ACTUAL SW VERSION']='0'                                             #Reg 3001
        self.flash['sw,RFID VERIFICATION']='0'                                                 #Reg 3002
        self.flash['in,EVSE-MAX-CURRENT-A']='25'                                           #Reg 3003
        self.flash['sw,WHEN AC IN: CHARGING']='0'                                       #Reg 3004
        self.flash['in,TIME-ZONE']='2'                                                                #Reg 3005
        self.flash['sw,AC IN ACTIVE: HIGH']='0'                                               #Reg 3006
        self.flash['sw,TESTING SOFTWARE']='0'                                               #Reg 3007
        self.flash['sw,Wi-Fi AP'] = '1'                                                                   #Reg 3008
        self.flash['sw,EXTERNAL REGULATION'] = '0'                                     #Reg 3009
        self.flash['in,MODBUS-ID'] = '1'                                                            #Reg 3010        
        self.flash['ERRORS'] = '0'                                                                        #Reg 3011
        self.flash['ID'] = '0'                                                                                  #Reg 3012
        self.flash['bt,RESET'] = 0                                                                        #Reg 3013

        self.SETTING_PROFILES = 'setting.dat'
        self.handle_configure('txt,ACTUAL SW VERSION',self.boot.get_version(""))
        self.getConfig()
        self.ram = OrderedDict()
        self.ram['RFID_VERIFY'] = 0                                                                   #Reg 3100
        self.ram['EVSE_CURRENT']= int(self.flash['in,EVSE-MAX-CURRENT-A']) #Reg 3101

    # Update self.config from setting.dat and return dict(config)
    def getConfig(self):
        setting = {}
        try:
            setting = self.read_setting()
        except OSError:
            setting = {}
            
        if len(setting) != len(self.flash):
            with open(self.SETTING_PROFILES, 'w') as filetowrite:
                filetowrite.write('')
                filetowrite.close()
                
            for i in self.flash: 
                if i in setting:
                    if self.flash[i] != setting[i]:
                        self.flash[i] = setting[i]
            setting = {}
        
        for i in self.flash: 
            if i in setting:
                if self.flash[i] != setting[i]:
                    self.flash[i] = setting[i]   
            else:
                setting[i] = self.flash[i]
                self.write_setting(setting)
        
        if self.flash['ID'] == '0':
            id = bytearray(os.urandom(4))
            randId = ''
            for i in range(0,len(id)):
                randId+= str((int(id[i])))
            self.flash['ID'] = randId[-5:]
            self.handle_configure('ID', self.flash['ID'])
            
        return self.flash

    # Update self.config. Write new value to self.config and to file setting.dat
    def handle_configure(self,variable, value):
        try:
            self.handleDifferentRequests(variable,value)
            if len(variable)>0:
                try:
                    setting = self.read_setting()
                except OSError:
                    setting = {}
                
                if setting[variable] != value:
                    setting[variable] = value
                    self.write_setting(setting)
                    self.getConfig()
                    return True
            else:
                return False
        except Exception as e:
            print(e)
            
    def handleDifferentRequests(self,variable,value):
        if variable == 'bt,RESET WATTMETER':
            from machine import reset
            reset()

    #If exist read setting from setting.dat, esle create setting
    def read_setting(self):
        with open(self.SETTING_PROFILES) as f:
            lines = f.readlines()
        setting = {}
        try:
            for line in lines:
                variable, value = line.strip("\n").split(";")
                setting[variable] = value
            return setting
        
        except Exception as e:
            self.write_setting(self.flash)
            return self.flash

    # method for write data to file.dat
    def write_setting(self,setting):
        lines = []
        for variable, value in setting.items():
            lines.append("%s;%s\n" % (variable, value))
        with open(self.SETTING_PROFILES, "w") as f:
            f.write(''.join(lines))
            
