import picoweb
from machine import reset, RTC
from time import time
import ujson as json
from gc import collect, mem_free
import uasyncio as asyncio
import ulogging


class WebServerApp:
    def __init__(self, wlan, wattmeter, evse, comm_interface, config):
        self.comm_interface = comm_interface
        self.wifi_manager = wlan
        self.ip_address = self.wifi_manager.getIp()
        self.wattmeter = wattmeter
        self.evse = evse
        self.port = 8000
        self.datalayer = dict()
        self.config = config
        self.routes = [
            ("/", self.main),
            ("/datatable", self.data_table),
            ("/overview", self.over_view),
            ("/updateWificlient", self.update_wificlient),
            ("/updateSetting", self.update_setting),
            ("/updateData", self.update_data),
            ("/updateEvse", self.update_evse),
            ("/settings", self.settings),
            ("/history", self.history),
            ("/energyChart", self.energy_chart),
            ("/getEspID", self.get_esp_id),
            ("/modbusRW", self.modbus_rw),
            ("/updateRFID", self.update_rfid),
            ("/rfid", self.rfid)
        ]

        self.app = picoweb.WebApp(None, self.routes)
        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def main(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "main.html")

    def over_view(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "overview.html")

    def settings(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "settings.html", (req,))

    def history(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "history.html", (req,))

    def energy_chart(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "energyChart.html", (req,))

    def rfid(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "rfid.html", (req,))

    def modbus_rw(self, req, resp):
        collect()
        if req.method == "POST":
            datalayer = {}
            req = await self.process_msg(req)
            for i in req.form:
                i = json.loads(i)
                reg = int(i['reg'])
                _id = int(i['id'])
                data = int(i['value'])
                if i['type'] == 'read':
                    try:
                        async with self.comm_interface as w:
                            data = await w.read_register(reg, 1, _id)

                        if data is None:
                            datalayer = {"process": 0, "value": "Error during reading register"}
                        else:
                            datalayer = {"process": 1, "value": int(((data[0]) << 8) | (data[1]))}

                    except Exception as e:
                        datalayer = {"process": e}

                elif i['type'] == 'write':
                    try:
                        async with self.comm_interface as w:
                            await w.write_register(reg, [data], _id)

                    except Exception as e:
                        datalayer = {"process": e}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    def update_rfid(self, req, resp):
        collect()
        if req.method == "POST":
            req = req.get_data().decode('utf8').replace("'", '"')
            req = json.loads(req)
            if 'addRfid' in req:

                pass
            elif 'saveRfid' in req:
                pass
        # return response

        datalayer = {"Jan Novak": "12345678", "Michael Novak": "12345678123456"}
        yield from picoweb.start_response(resp, "application/json")
        yield from resp.awrite(json.dumps(datalayer))
        # return response     

    def update_data(self, req, resp):
        collect()
        datalayer = {}
        if req.method == "POST":
            req = await  self.process_msg(req)
            for i in req.form:
                i = json.loads(i)
                if list(i.keys())[0] == 'relay':
                    if self.wattmeter.negotiationRelay():
                        datalayer = {"process": 1}
                    else:
                        datalayer = {"process": 0}
                elif list(i.keys())[0] == 'time':
                    rtc = RTC()
                    rtc.datetime((int(i["time"][2]), int(i["time"][1]), int(i["time"][0]), 0, int(i["time"][3]),
                                  int(i["time"][4]), int(i["time"][5]), 0))
                    self.wattmeter.start_up_time = time()
                    self.wattmeter.time_init = True
                    datalayer = {"process": "OK"}
            yield from picoweb.jsonify(resp, datalayer)

        else:
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(self.wattmeter.data_layer.__str__())

    def update_evse(self, req, resp):
        yield from picoweb.start_response(resp, "application/json")
        yield from resp.awrite(self.evse.data_layer.__str__())

    def update_wificlient(self, req, resp):

        collect()
        if req.method == "POST":
            datalayer = {}
            size = int(req.headers[b"Content-Length"])
            qs = yield from req.reader.read(size)
            req.qs = qs.decode()
            try:
                i = json.loads(req.qs)
            except:
                pass
            datalayer = await self.wifi_manager.handle_configure(i["ssid"], i["password"])
            self.ip_address = self.wifi_manager.getIp()
            datalayer = {"process": datalayer, "ip": self.ip_address}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

        else:
            client = self.wifi_manager.getSSID()
            datalayer = {}
            for i in client:
                if client[i] > -86:
                    datalayer[i] = client[i]
            datalayer["connectSSID"] = self.wifi_manager.getCurrentConnectSSID()
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    def update_setting(self, req, resp):
        collect()

        if req.method == "POST":
            datalayer = {}
            req = await self.process_msg(req)

            for i in req.form:
                i = json.loads(i)
                datalayer = self.config.handle_configure(i["variable"], i["value"])
                datalayer = {"process": datalayer}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

        else:
            datalayer = self.config.get_config()
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    def data_table(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "datatable.html", (req,))

    def get_esp_id(self, req, resp):
        datalayer = {"ID": " Smartmodul: {}".format(self.config.get_config()['ID']), "IP": self.wifi_manager.getIp()}
        yield from picoweb.start_response(resp, "application/json")
        yield from resp.awrite(json.dumps(datalayer))

    def process_msg(self, req):
        size = int(req.headers[b"Content-Length"])
        qs = yield from req.reader.read(size)
        req.qs = qs.decode()
        req.parse_qs()
        return req

    async def web_server_run(self):
        try:
            self.logger.info("Webserver app started")
            self.app.run(debug=False, host='', port=self.port)
            while True:
                await asyncio.sleep(100)
        except Exception as e:
            self.logger.error("WEBSERVER ERROR: {}. I will reset MCU".format(e))
            reset()
