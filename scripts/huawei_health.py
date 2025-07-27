#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Huawei Health collector - otimizado para executar discovery e coleta em uma unica operacao

Usage:
  huawei_health.py launch_discovery <ip> <port> <user> <password> <hostname>
  huawei_health.py collect <ip> <port> <user> <password> <hostname>

OTIMIZADO: launch_discovery agora executa discovery + coleta em uma unica operacao
"""

import sys
import paramiko
import re
import logging
import tempfile
import subprocess
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ssh_command(ip, port, user, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, port=int(port), username=user, password=password, look_for_keys=False)
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode('utf-8', errors='ignore')
    client.close()
    return output

def parse_cpu(cpu_output):
    m = re.search(r"System cpu use rate is\s*:\s*(\d+)%", cpu_output)
    return int(m.group(1)) if m else -1

def parse_memory(memory_output):
    m_total = re.search(r'System Total Memory Is:\s+(\d+)\s+Kbytes', memory_output)
    m_used = re.search(r'Total Memory Used Is:\s+(\d+)\s+Kbytes', memory_output)
    m_used_pct = re.search(r'Memory Using Percentage Is:\s+(\d+)%', memory_output)
    if m_total and m_used and m_used_pct:
        total = int(m_total.group(1))
        used = int(m_used.group(1))
        used_pct = int(m_used_pct.group(1))
        free = total - used
        free_pct = 100 - used_pct
        return total, used, free, used_pct, free_pct
    else:
        return -1, -1, -1, -1, -1

def parse_version(version_output):
    m = re.search(r"VRP \(R\) software, Version ([\d\.]+)", version_output)
    return m.group(1) if m else "unknown"

def parse_uptime(version_output):
    m = re.search(r"uptime is ([^\n]+)", version_output)
    if m:
        uptime = m.group(1).split("Patch")[0].strip()
        return uptime
    return "unknown"

def parse_fan_speed(fan_output):
    """Parse velocidade dos ventiladores"""
    speeds = []
    for line in fan_output.splitlines():
        # Procura por padrões de velocidade de fan
        m = re.search(r'\[(\d+)\](\d+)%', line)
        if m:
            fan_num = m.group(1)
            speed = int(m.group(2))
            speeds.append(speed)
    
    if speeds:
        return sum(speeds) / len(speeds)  # Média das velocidades
    return -1

def parse_power_info(power_output):
    """Parse informações de energia para discovery"""
    power_data = []
    
    for line in power_output.splitlines():
        # Procura por linhas de power supply
        m = re.match(r'(\d+)\s+Yes\s+(\w+)\s+(\w+)', line.strip())
        if m:
            slot = m.group(1)
            mode = m.group(2)
            state = m.group(3)
            
            # Determina status baseado no state
            status = 1 if state == "Normal" else 0
            
            power_data.append({
                "{#SLOT}": slot,
                "{#MODE}": mode,
                "{#STATE}": state,
                "{#STATUS}": status
            })
    
    return power_data

def parse_power_supply_info(power_supply_output):
    """Parse informações de power supply"""
    m = re.search(r'Real\s+(\d+)', power_supply_output)
    return int(m.group(1)) if m else -1

def parse_health_info(health_output):
    """Parse informações de saúde do sistema"""
    m = re.search(r'(\d+)%\s+(\d+)%\s+(\d+)MB/(\d+)MB', health_output)
    if m:
        cpu_usage = int(m.group(1))
        memory_usage = int(m.group(2))
        memory_used = int(m.group(3))
        memory_total = int(m.group(4))
        return cpu_usage, memory_usage, memory_used, memory_total
    return -1, -1, -1, -1

def parse_ipu_temperature_full(temperature_output):
    result = []
    current_slot = "unknown" # Inicializa com unknown ou um valor padrão
    found_table = False  # Inicializa a variável found_table

    for line in temperature_output.splitlines():
        # Tenta capturar o slot da linha "Base-Board, Unit:C, Slot X"
        slot_match = re.search(r'Base-Board, Unit:C, Slot (\d+)', line)
        if slot_match:
            current_slot = slot_match.group(1)
            continue # Pula para a próxima linha depois de encontrar o slot

        if re.match(r'PCB\s+I2C\s+Addr\s+Chl', line):
            found_table = True
            continue
        if not found_table or line.strip() == "" or line.startswith("-"):
            continue

        m = re.match(r'(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\S+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+(-?\d+)', line.strip())
        if m:
            board = m.group(1)
            i2c = m.group(2)
            addr = m.group(3)
            chl = m.group(4)
            temp = m.group(5)
            result.append({
                "{#SLOT}": current_slot, # Usa o slot dinâmico
                "{#SENSOR_NAME}": board,
                "{#I2C}": i2c,
                "{#ADDR}": addr,
                "{#CHL}": chl,
                "TEMP": temp
            })
    return result

def launch_discovery(ip, port, user, password, hostname):
    logger.info("Executando discovery de sensores IPU...")
    command_temp = "display temperature ipu | no-more"
    output_temp = ssh_command(ip, port, user, password, command_temp)
    print("[DEBUG] Saida display temperature ipu:\n")
    print(output_temp)
    
    full_sensors = parse_ipu_temperature_full(output_temp)
    
    # Envia cada sensor individualmente para discovery
    for entry in full_sensors:
        key = f'temperatureInfo[{entry["{#SLOT}"]},{entry["{#SENSOR_NAME}"]},{entry["{#I2C}"]},{entry["{#ADDR}"]},{entry["{#CHL}"]}]'
        value = entry["TEMP"]
        
        cmd = [
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", key, "-o", value
        ]
        logger.info("Enviando discovery: %s %s %s", hostname, key, value)
        subprocess.run(cmd, capture_output=True)
    
    logger.info("Discovery de sensores IPU concluido. Total: %d sensores", len(full_sensors))
    print("Discovery de sensores IPU concluido.")

def collect(ip, port, user, password, hostname):
    logger.info("Coletando CPU...")
    cmd_cpu = "display cpu-usage | no-more"
    cpu_out = ssh_command(ip, port, user, password, cmd_cpu)
    cpu = parse_cpu(cpu_out)

    logger.info("Coletando memoria...")
    cmd_memory = "display memory-usage | no-more"
    memory_out = ssh_command(ip, port, user, password, cmd_memory)
    total_mem, used_mem, free_mem, used_mem_pct, free_mem_pct = parse_memory(memory_out)

    logger.info("Coletando versao e uptime...")
    cmd_version = "display version | no-more"
    version_out = ssh_command(ip, port, user, password, cmd_version)
    version = parse_version(version_out)
    uptime = parse_uptime(version_out)

    logger.info("Coletando temperaturas IPU...")
    command_temp = "display temperature ipu | no-more"
    output_temp = ssh_command(ip, port, user, password, command_temp)
    full_sensors = parse_ipu_temperature_full(output_temp)

    # NOVOS COMANDOS - Fan/Ventiladores
    logger.info("Coletando dados dos ventiladores...")
    cmd_fan = "display fan | no-more"
    fan_out = ssh_command(ip, port, user, password, cmd_fan)
    fan_speed = parse_fan_speed(fan_out)

    # NOVOS COMANDOS - Power/Energia
    logger.info("Coletando dados de energia...")
    cmd_power = "display power | no-more"
    power_out = ssh_command(ip, port, user, password, cmd_power)
    power_info = parse_power_info(power_out)

    # NOVOS COMANDOS - Power Supply Info
    logger.info("Coletando informações de power supply...")
    cmd_power_supply = "display power-supply information | no-more"
    power_supply_out = ssh_command(ip, port, user, password, cmd_power_supply)
    total_power = parse_power_supply_info(power_supply_out)

    # NOVOS COMANDOS - Health
    logger.info("Coletando dados de saúde do sistema...")
    cmd_health = "display health | no-more"
    health_out = ssh_command(ip, port, user, password, cmd_health)
    health_cpu, health_mem_pct, health_mem_used, health_mem_total = parse_health_info(health_out)

    # envia cada leitura individualmente para evitar erro de lote
    for entry in full_sensors:
        key = f'temperatureInfo[{entry["{#SLOT}"]},{entry["{#SENSOR_NAME}"]},{entry["{#I2C}"]},{entry["{#ADDR}"]},{entry["{#CHL}"]}]'
        value = entry["TEMP"]
        cmd = [
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", key, "-o", value
        ]
        logger.info("Enviando: %s %s %s", hostname, key, value)
        subprocess.run(cmd, capture_output=True)

    # envia tambem os dados gerais
    if cpu != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "cpuUsage", "-o", str(cpu)], capture_output=True)
    if total_mem != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryTotal", "-o", str(total_mem)], capture_output=True)
    if used_mem != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryUsed", "-o", str(used_mem)], capture_output=True)
    if free_mem != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryFree", "-o", str(free_mem)], capture_output=True)
    if used_mem_pct != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryUsedPercentage", "-o", str(used_mem_pct)], capture_output=True)
    if free_mem_pct != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryFreePercentage", "-o", str(free_mem_pct)], capture_output=True)
    if version != "unknown":
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "firmwareVersion", "-o", version], capture_output=True)
    if uptime != "unknown":
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "firmwareUptime", "-o", uptime], capture_output=True)
    
    # NOVOS DADOS - Fan
    if fan_speed != -1:
        logger.info("Enviando velocidade dos ventiladores: %s", fan_speed)
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "fanMean", "-o", str(fan_speed)], capture_output=True)
    
    # NOVOS DADOS - Power
    if total_power != -1:
        logger.info("Enviando consumo total de potência: %s", total_power)
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "total_power_usage", "-o", str(total_power)], capture_output=True)

    # Envia discovery de power
    if power_info:
        logger.info("Enviando discovery de power: %s", len(power_info))
        subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", "powerInfo", "-o", json.dumps({"data": power_info})
        ], capture_output=True)

    print("Coleta concluida!")

def main():
    if len(sys.argv) < 2:
        print("Uso: huawei_health.py <launch_discovery|collect> <ip> <porta> <login> <senha> <hostname>")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == 'launch_discovery':
        if len(sys.argv) != 7:
            print("Uso: huawei_health.py launch_discovery <ip> <porta> <login> <senha> <hostname>")
            sys.exit(1)
        _, _, ip, port, user, password, hostname = sys.argv + [None]*(7-len(sys.argv))
        
        # Validação para macros não resolvidas
        if port == '{$SSH_PORT}' or port.startswith('{$'):
            print("ERRO: Macro SSH_PORT não resolvida. Verifique a configuração do host no Zabbix.")
            sys.exit(1)
        if user == '{$SSH_USER}' or user.startswith('{$'):
            print("ERRO: Macro SSH_USER não resolvida. Verifique a configuração do host no Zabbix.")
            sys.exit(1)
        if password == '{$SSH_PASS}' or password.startswith('{$'):
            print("ERRO: Macro SSH_PASS não resolvida. Verifique a configuração do host no Zabbix.")
            sys.exit(1)
            
        launch_discovery(ip, port, user, password, hostname)
    elif mode == 'collect':
        if len(sys.argv) != 7:
            print("Uso: huawei_health.py collect <ip> <porta> <login> <senha> <hostname>")
            sys.exit(1)
        _, _, ip, port, user, password, hostname = sys.argv + [None]*(7-len(sys.argv))
        
        # Validação para macros não resolvidas
        if port == '{$SSH_PORT}' or port.startswith('{$'):
            print("ERRO: Macro SSH_PORT não resolvida. Verifique a configuração do host no Zabbix.")
            sys.exit(1)
        if user == '{$SSH_USER}' or user.startswith('{$'):
            print("ERRO: Macro SSH_USER não resolvida. Verifique a configuração do host no Zabbix.")
            sys.exit(1)
        if password == '{$SSH_PASS}' or password.startswith('{$'):
            print("ERRO: Macro SSH_PASS não resolvida. Verifique a configuração do host no Zabbix.")
            sys.exit(1)
            
        collect(ip, port, user, password, hostname)
    else:
        print("Modo desconhecido")

if __name__ == '__main__':
    main()
