from main.inverters.base import BaseInverter
from umodbus.tcp import TCP
from gc import collect
from asyncio import sleep

collect()


class Solax(BaseInverter):

    def __init__(self, *args, **kwargs):
        super(Solax, self).__init__(*args, **kwargs)
        self.modbus_port: int = 502
        self.modbus_tcp: TCP = None
        self.device_type: int = 0x0
        self.data_layer.data["type"] = "Solax"
        #self.reset_wifi_dongle()

    async def run(self):
        self.data_layer.data["status"] = self.connection_status
        if self.modbus_tcp is not None:
            try:
                response = self.modbus_tcp.read_input_registers(slave_addr=1, starting_addr=0x006A, register_qty=11)
                self.process_msg(response, starting_addr=0x006A)
                await sleep(1)
                response = self.modbus_tcp.read_input_registers(slave_addr=1, starting_addr=0x0082, register_qty=6)
                self.process_msg(response, starting_addr=0x0082)
                await sleep(1)
                response = self.modbus_tcp.read_input_registers(slave_addr=1, starting_addr=0x1C, register_qty=1)
                self.process_msg(response, starting_addr=0x1C)
                self.reconnect_error_cnt = 0
                self.data_layer.data["ip"] = self.set_ip_address

            except Exception as e:
                if e.errno == 128:
                    self.logger.error("Socket not connected (ENOTCONN)")
                    self.reconnect_error_cnt = 10
                elif e.errno == 116:
                    self.logger.error("Socket timeout (ETIMEDOUT)")
                elif e.errno == 104:
                    self.logger.error("Socket connection reset (ECONNRESET)")
                else:
                    self.logger.error(f"Modbus TCP error: {e}")

                self.reconnect_error_cnt += 1
                if self.reconnect_error_cnt > self.max_reconnect_error_cnt:
                    self.data_layer.data["status"] = 2
                    #self.reset_wifi_dongle()
                    try:
                        self.modbus_tcp._sock.close()
                    except:
                        pass
                    self.modbus_tcp = await self.try_reconnect(modbus_port=self.modbus_port,
                                                               ip_address=self.set_ip_address,
                                                               slave_addr=1,
                                                               starting_addr=self.device_type,
                                                               number_of_reg=7,
                                                               callback=self.check_msg)
                    collect()
        else:
            await self.scann()

    def reset_wifi_dongle(self):
        import urequests
        collect()
        self.logger.info(f"Try reset wifi dongle on ip address: {self.set_ip_address}")
        url = f"http://{self.set_ip_address}"
        response = urequests.get(url)
        self.logger.info(response.text)
        response.close()
        collect()

    async def scann(self) -> None:
        #self.reset_wifi_dongle()
        self.data_layer.data["status"] = 2
        self.modbus_tcp: TCP = await self.scan_network(modbus_port=self.modbus_port,
                                                       ip_address=self.wifi_manager.get_ip(),
                                                       slave_addr=1,
                                                       starting_addr=self.device_type,
                                                       number_of_reg=7,
                                                       callback=self.check_msg)
        collect()

    def process_msg(self, response: tuple, starting_addr: int) -> None:

        if starting_addr == 0x006A:
            self.data_layer.data["u1"] = int(response[0] / 10)
            self.data_layer.data["u2"] = int(response[4] / 10)
            self.data_layer.data["u3"] = int(response[8] / 10)

        elif starting_addr == 0x0082:
            self.data_layer.data["p1"] = -1 * int((response[1] << 16) | response[0])
            self.data_layer.data["p2"] = -1 * int((response[3] << 16) | response[2])
            self.data_layer.data["p3"] = -1 * int((response[5] << 16) | response[4])
            self.data_layer.data["i1"] = int((self.data_layer.data["p1"] * 100) / self.data_layer.data["u1"]) if (
                    self.data_layer.data["u1"] > 0) else 0
            self.data_layer.data["i2"] = int((self.data_layer.data["p2"] * 100) / self.data_layer.data["u2"]) if (
                    self.data_layer.data["u2"] > 0) else 0
            self.data_layer.data["i3"] = int((self.data_layer.data["p3"] * 100) / self.data_layer.data["u3"]) if (
                    self.data_layer.data["u3"] > 0) else 0

        elif starting_addr == 0x1C:
            self.data_layer.data["soc"] = int(response[0])

    def check_msg(self, result: tuple) -> bool:
        device_type = ''
        for i in result:
            if i != 0:
                device_type = f"{device_type}{chr(i >> 8)}{chr(i & 0xFF)}"
        self.logger.info(f"Device type: {device_type}")
        if len(device_type) >= 14:
            self.data_layer.data['id'] = device_type
            return True
        return False
