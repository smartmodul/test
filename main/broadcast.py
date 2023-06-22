from pymodbus.client import ModbusTcpClient
import socket

network_prefix = '192.168.0.'  # Předpona sítě
start_ip = 1  # Počáteční číslo posledního oktetu IP adresy
end_ip = 254  # Koncové číslo posledního oktetu IP adresy
modbus_port = 5020

# Skenování IP adres v rozsahu sítě
for ip_suffix in range(start_ip, end_ip + 1):
    ip_address = network_prefix + str(ip_suffix)
    print(ip_address)
    # Pokus o navázání spojení na dané IP adrese a portu
    client = ModbusTcpClient(ip_address, modbus_port)
    try:
        # Pokud se spojení naváže úspěšně, pak je zařízení nalezeno
        if client.connect():
            print(f"Zařízení Modbus TCP nalezeno na adrese: {ip_address}")
            # Můžete provádět další operace s nalezeným zařízením, pokud je to potřeba
            client.close()
    except (socket.timeout, ConnectionRefusedError):
        # Při timeoutu nebo odmítnutém spojení se přeskočí daná IP adresa
        continue
