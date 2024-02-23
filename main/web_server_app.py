import picoweb
from machine import reset, RTC
from time import time, sleep
import ujson as json
from gc import collect, mem_free
import uasyncio as asyncio
import ulogging

collect()


class WebServerApp:
    def __init__(self, wlan, wattmeter, evse, comm_interface, config, rfid, inverter, history):
        self.rfid_object = rfid
        self.history_object = history
        self.inverter = inverter
        self.comm_interface = comm_interface
        self.wifi_manager = wlan
        self.ip_address = self.wifi_manager.get_ip()
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
            ("/updateRamSetting",self.update_ram_setting),
            ("/updateInverterData", self.update_inverter_data),
            ("/updateData", self.update_data),
            ("/settings", self.settings),
            ("/history", self.history),
            ("/getHistory", self.get_history),
            ("/energyChart", self.energy_chart),
            ("/getEspID", self.get_esp_id),
            ("/modbusRW", self.modbus_rw),
            ("/updateRFID", self.update_rfid),
            ("/rfid", self.rfid),
            ("/factoryReset", self.factory_reset)
        ]

        self.app = picoweb.WebApp(None, self.routes)
        self.logger = ulogging.getLogger(__name__)
        if int(self.config.flash['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def update_inverter_data(self, req, resp):
        collect()

        if req.method == "POST":
            datalayer = {"process": "unknown process"}
            req = await self.process_msg(req)

            for data in req.form:
                data = json.loads(data)
                for key in data:
                    if key in self.inverter.data_layer.data:
                        self.inverter.data_layer.data[key] = data[key]
                        datalayer = {"process": "ok"}
                    else:
                        datalayer = {"process": "key not found"}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

        else:
            merged_dict = self.inverter.data_layer.__str__()
            merged_json = json.dumps(merged_dict)
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(merged_json)

        collect()

    def main(self, req, resp):
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "main.html")

    def factory_reset(self, req, resp):
        from os import remove
        remove("charging_history.dat")
        remove("rfid.dat")
        remove("daily_consumption.dat")
        yield from picoweb.start_response(resp)
        yield from resp.awrite("charging_history.dat and rfid.dat have been successfully deleted and the Smartmodule will now reboot!")
        sleep(5)
        from machine import reset
        reset()

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
            size: int = int(req.headers[b"Content-Length"])
            qs: bytearray = yield from req.reader.read(size)
            req.qs = qs.decode()
            req = json.loads(req.qs)
            response: int = 0
            if 'rfid_mode' in req:
                response = self.rfid_object.handle_request(rfid_mode=req['rfid_mode'], user=req['user'], _id=req['id'])
            if 'get_rfid_mode' in req:
                response = self.rfid_object.mode
            datalayer = {"rfid_response": response}
            yield from picoweb.jsonify(resp, datalayer)

        else:
            rfid_database: json = json.dumps(self.rfid_object.data_layer.users)
            print(f"Get rfid database: {rfid_database}")
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(rfid_database)

    def get_history(self, req, resp):
        collect()
        history_database = json.dumps(self.history_object.sessions.__str__())
        yield from picoweb.start_response(resp, "application/json")
        yield from resp.awrite(history_database)
        collect()

    def update_data(self, req, resp) -> None:
        collect()

        datalayer: dict = {}
        if req.method == "POST":
            req = await self.process_msg(req)
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

            merged_dict = self.wattmeter.data_layer.__str__()
            merged_dict.update(self.evse.data_layer.__str__())
            merged_dict.update(self.rfid_object.data_layer.__str__())
            if self.inverter:
                merged_dict.update(self.inverter.data_layer.__str__())

            merged_json = json.dumps(merged_dict)
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(merged_json)
            collect()

    def update_wificlient(self, req, resp):
        collect()
        if req.method == "POST":
            size = int(req.headers[b"Content-Length"])
            qs = yield from req.reader.read(size)
            req.qs = qs.decode()
            try:
                i = json.loads(req.qs)
            except:
                pass
            datalayer = await self.wifi_manager.handle_configure(i["ssid"], i["password"])
            self.ip_address = self.wifi_manager.get_ip()
            datalayer = {"process": datalayer, "ip": self.ip_address}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

        else:
            client = self.wifi_manager.getSSID()
            datalayer = {}
            for i in client:
                if client[i] > -86 and len(i) > 0:
                    datalayer[i] = client[i]
            datalayer["connectSSID"] = self.wifi_manager.getCurrentConnectSSID()
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    def update_ram_setting(self, req, resp):
        collect()

        if req.method == "POST":
            datalayer = {}
            req = await self.process_msg(req)

            for i in req.form:
                i = json.loads(i)
                datalayer = self.config.handle_ram_configure(i["variable"], i["value"])
                datalayer = {"process": datalayer}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

        else:
            datalayer = self.config.get_ram_config()
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))
        collect()
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
        datalayer = {"ID": " Smartmodul: {}".format(self.config.get_config()['ID']), "IP": self.wifi_manager.get_ip()}
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
