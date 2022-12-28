import picoweb
import wifiManager
from machine import reset,RTC
from time import time
import ujson as json
from gc import collect,mem_free
from asyn import sleep,cancellable,StopTask
import uasyncio as asyncio
from main import taskHandler

class WebServerApp:
    def __init__(self,wlan,wattmeter,evse,commInterface,config):
        self.commInterface = commInterface
        self.wifiManager = wlan
        self.ipAddress = self.wifiManager.getIp()
        self.wattmeter = wattmeter
        self.evse = evse
        self.port = 8000
        self.datalayer = dict()
        self.config = config
        self.ROUTES = [ 
            ("/", self.main), 
            ("/datatable", self.dataTable),
            ("/overview", self.overView),
            ("/updateWificlient",self.updateWificlient),
            ("/updateSetting",self.updateSetting),
            ("/updateData", self.updateData), 
            ("/updateEvse", self.updateEvse), 
            ("/settings", self.settings),
            ("/history", self.history),
            ("/energyChart", self.energyChart),
            ("/getEspID", self.getEspID),
            ("/modbusRW", self.modbusRW),
            #("/cloudConfig", self.cloudConfig),
            ("/updateRFID",self.updateRFID),
            ("/rfid",self.rfid)
        ]
        self.app = picoweb.WebApp(None, self.ROUTES)

         
    def main(self,req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp,"main.html")
    
    def overView(self,req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp,"overview.html")

    def settings(self,req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp,"settings.html", (req,))
        
    def history(self,req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp,"history.html", (req,))
    
    def energyChart(self,req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "energyChart.html", (req,))

    def rfid(self,req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "rfid.html", (req,))        

    def modbusRW(self,req, resp):
        collect()
        if req.method == "POST":
            datalayer = {}
            req = await  self.proccessMsg(req)
            for i in req.form:
                i = json.loads(i)
                reg = int(i['reg'])
                ID = int(i['id'])
                data = int(i['value'])
                if i['type'] == 'read':
                    try:
                        async with self.commInterface as w:
                            data = await w.readRegister(reg,1,ID)

                        if data is None:
                            datalayer = {"process":0,"value":"Error during reading register"}
                        else:
                            datalayer = {"process":1,"value":int(((data[0]) << 8) | (data[1]))}

                    except Exception as e:
                        datalayer = {"process":e}

                elif i['type'] == 'write':
                    try:
                        async with self.commInterface as w:
                            await w.writeRegister(reg,[data],ID)

                    except Exception as e:
                        datalayer = {"process":e}
                        
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))
    
    def updateRFID(self,req, resp):
        collect()
        if req.method == "POST":
            req = req.get_data().decode('utf8').replace("'", '"')
            req = json.loads(req)
            if 'addRfid' in req :
                
                pass
            elif 'saveRfid' in req :
                pass
        #return response

        datalayer = {"Jan Novak":"12345678","Michael Novak":"12345678123456"}
        yield from picoweb.start_response(resp, "application/json")
        yield from resp.awrite(json.dumps(datalayer))
        # return response     
    
    def updateData(self,req, resp):
        collect() 
        datalayer = {}
        if req.method == "POST":
            req = await  self.proccessMsg(req)
            for i in req.form:
                i = json.loads(i)
                if list(i.keys())[0] == 'relay':
                    if self.wattmeter.negotiationRelay():
                        datalayer = {"process":1}
                    else:
                        datalayer = {"process":0}
                elif list(i.keys())[0] == 'time':
                    rtc=RTC()
                    rtc.datetime((int(i["time"][2]), int(i["time"][1]), int(i["time"][0]), 0, int(i["time"][3]), int(i["time"][4]), int(i["time"][5]), 0))           
                    self.wattmeter.startUpTime = time()
                    self.wattmeter.timeInit = True
                    datalayer = {"process":"OK"}
            yield from picoweb.jsonify(resp,datalayer)
                
        else:
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(self.wattmeter.dataLayer.__str__())

    def updateEvse(self,req,resp):
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(self.evse.dataLayer.__str__())
    
    def updateWificlient(self,req, resp):
        
        collect()
        if req.method == "POST":
            datalayer = {}
            req = await  self.proccessMsg(req)
            for i in req.form: 
                i = json.loads(i)
                datalayer = await self.wifiManager.handle_configure(i["ssid"],i["password"])
                self.ipAddress=self.wifiManager.getIp()
                datalayer = {"process":datalayer,"ip":self.ipAddress}
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))
                
        else:
            client = self.wifiManager.getSSID()
            datalayer = {}
            for i in client:
                if client[i] > -86: #jestlize je sila signalu mensi nez 20% nezobrazuj ssid
                    datalayer[i]= client[i]   
            datalayer["connectSSID"] = self.wifiManager.getCurrentConnectSSID()
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    #Funkce pro vycitani a ukladani nastaveni
    def updateSetting(self,req, resp):
        collect()
        
        if req.method == "POST":
            datalayer = {}
            req = await self.proccessMsg(req)
            
            for i in req.form: 
                i = json.loads(i)                    
                datalayer = self.config.handle_configure(i["variable"],i["value"])
                datalayer = {"process":datalayer}
            
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))
                
        else:
            datalayer = self.config.getConfig()
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

                
    def dataTable(self,req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "datatable.html", (req,))

    def getEspID(self,req,resp):
        datalayer = {"ID":" Wattmeter: {}".format(self.config.getConfig()['ID']), "IP":self.wifiManager.getIp()}
        yield from picoweb.start_response(resp, "application/json")
        yield from resp.awrite(json.dumps(datalayer))
         
        
    def proccessMsg(self,req):
        size = int(req.headers[b"Content-Length"])
        qs = yield from req.reader.read(size)
        req.qs = qs.decode()
        req.parse_qs()
        return req
        

    async def webServerRun(self):
        try:
            print("Webserver app started")
            self.app.run(debug=False, host='',port=self.port)          
            while True:
                await asyncio.sleep(100)
        except Exception as e:
            print("WEBSERVER ERROR: {}. I will reset MCU".format(e))
            reset()
