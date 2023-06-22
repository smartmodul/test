from umodbus.tcp import TCP
import socket
import uasyncio as asyncio


class Inverter:
    def __init__(self):
        #self.modbus_tcp = TCP(slave_ip="192.168.0.101", slave_port=5020)
        self.scanner = Scanner()
        #self.scanner.start_scann()

    async def run(self):
        await self.scanner.scan_network()
        return
        try:
            data = self.modbus_tcp.read_holding_registers(slave_addr=101,
                                                          starting_addr=1000,
                                                          register_qty=10)
            print("Response: ", data)
        except:
            pass


class Scanner:
    def __init__(self):
        self.network_prefix = '192.168.0.'  # Předpona sítě
        self.start_ip = 100  # Počáteční číslo posledního oktetu IP adresy
        self.end_ip = 254  # Koncové číslo posledního oktetu IP adresy
        self.modbus_port = 5020

    async def scan_ip_address(self, ip_address):
        try:
            reader, writer = await asyncio.open_connection(ip_address, self.modbus_port)
            if writer is not None and reader is not None:
                modbus_tcp = TCP(slave_ip=ip_address, slave_port=self.modbus_port)
                data = modbus_tcp.read_holding_registers(slave_addr=101,
                                                         starting_addr=1000,
                                                         register_qty=10)
                print(data)
                print(f"Zařízení Modbus TCP nalezeno na adrese: {ip_address}")
            writer.close()
            await writer.wait_closed()

        except:
            pass

    async def scan_network(self):
        for ip_suffix in range(self.start_ip, self.end_ip + 1):
            ip_address = self.network_prefix + str(ip_suffix)
            #print(ip_address)
            try:
                await asyncio.wait_for(self.scan_ip_address(ip_address), timeout=1)
            except Exception as e:
                pass