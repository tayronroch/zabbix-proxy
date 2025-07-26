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
import tempfile
import subprocess
import json

# Cache simples para evitar comandos duplicados
command_cache = {}

def ssh_command(ip, port, user, password, command):
    """Executa comando SSH com cache para evitar duplicatas"""
    global command_cache
    
    # Verifica cache primeiro
    cache_key = f"{ip}:{port}:{command}"
    if cache_key in command_cache:
        return command_cache[cache_key]
    
    # Executa comando
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, port=int(port), username=user, password=password, 
                      look_for_keys=False, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=45)
        output = stdout.read().decode('utf-8', errors='ignore')
        client.close()
        
        # Armazena no cache
        command_cache[cache_key] = output
        return output
        
    except Exception as e:
        raise Exception(f"Erro SSH em '{command}': {str(e)}")

def clear_cache():
    """Limpa cache de comandos"""
    global command_cache
    command_cache.clear()

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

def parse_ipu_temperature_full(temperature_output):
    result = []
    current_slot = "unknown" # Inicializa com unknown ou um valor padrão

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

def launch_discovery_original(ip, port, user, password, hostname):
    """Funcao original de discovery que funcionava"""
    command_temp = "display temperature ipu | no-more"
    output_temp = ssh_command(ip, port, user, password, command_temp)
    
    ipu_list = []
    full_sensors = parse_ipu_temperature_full(output_temp)
    for entry in full_sensors:
        ipu_list.append({
            "{#SLOT}": entry["{#SLOT}"],
            "{#SENSOR_NAME}": entry["{#SENSOR_NAME}"],
            "{#I2C}": entry["{#I2C}"],
            "{#ADDR}": entry["{#ADDR}"],
            "{#CHL}": entry["{#CHL}"],
        })
    
    subprocess.run([
        "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
        "-k", "temperatureInfo", "-o", json.dumps({"data": ipu_list})
    ], capture_output=True, timeout=15)

def collect_original(ip, port, user, password, hostname):
    """Funcao original de collect que funcionava"""
    # CPU
    cmd_cpu = "display cpu-usage | no-more"
    cpu_out = ssh_command(ip, port, user, password, cmd_cpu)
    cpu = parse_cpu(cpu_out)

    # Memoria
    cmd_memory = "display memory-usage | no-more"
    memory_out = ssh_command(ip, port, user, password, cmd_memory)
    total_mem, used_mem, free_mem, used_mem_pct, free_mem_pct = parse_memory(memory_out)

    # Versao e uptime
    cmd_version = "display version | no-more"
    version_out = ssh_command(ip, port, user, password, cmd_version)
    version = parse_version(version_out)
    uptime = parse_uptime(version_out)

    # Temperaturas IPU (vai usar cache se ja foi executado no discovery)
    command_temp = "display temperature ipu | no-more"
    output_temp = ssh_command(ip, port, user, password, command_temp)
    full_sensors = parse_ipu_temperature_full(output_temp)

    # Envia cada leitura individualmente para evitar erro de lote
    for entry in full_sensors:
        key = f'temperatureInfo[{entry["{#SLOT}"]},{entry["{#SENSOR_NAME}"]},{entry["{#I2C}"]},{entry["{#ADDR}"]},{entry["{#CHL}"]}]'
        value = entry["TEMP"]
        cmd = [
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", key, "-o", value
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)

    # Envia dados gerais
    if cpu != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "cpuUsage", "-o", str(cpu)], capture_output=True, timeout=10)
    if total_mem != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryTotal", "-o", str(total_mem)], capture_output=True, timeout=10)
    if used_mem != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryUsed", "-o", str(used_mem)], capture_output=True, timeout=10)
    if free_mem != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryFree", "-o", str(free_mem)], capture_output=True, timeout=10)
    if used_mem_pct != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryUsedPercentage", "-o", str(used_mem_pct)], capture_output=True, timeout=10)
    if free_mem_pct != -1:
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "memoryFreePercentage", "-o", str(free_mem_pct)], capture_output=True, timeout=10)
    if version != "unknown":
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "firmwareVersion", "-o", version], capture_output=True, timeout=10)
    if uptime != "unknown":
        subprocess.run(["zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "firmwareUptime", "-o", uptime], capture_output=True, timeout=10)

def launch_discovery_and_collect(ip, port, user, password, hostname):
    """Executa discovery e coleta usando as funcoes originais que funcionavam - OTIMIZADO"""
    try:
        # Limpa cache
        clear_cache()
        
        # Executa discovery original
        launch_discovery_original(ip, port, user, password, hostname)
        
        # Executa collect original (reutiliza comando de temperatura do cache)
        collect_original(ip, port, user, password, hostname)
        
        print("SUCESSO: Discovery e coleta executados com sucesso!")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
    finally:
        clear_cache()

def collect(ip, port, user, password, hostname):
    """Funcao de collect para compatibilidade"""
    try:
        clear_cache()
        collect_original(ip, port, user, password, hostname)
        print("SUCESSO: Coleta executada com sucesso!")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
    finally:
        clear_cache()

def main():
    if len(sys.argv) < 2:
        print("Uso: huawei_health.py <launch_discovery|collect> <ip> <porta> <login> <senha> <hostname>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    if mode == 'launch_discovery':
        if len(sys.argv) != 7:
            print("Uso: huawei_health.py launch_discovery <ip> <porta> <login> <senha> <hostname>", file=sys.stderr)
            sys.exit(1)
        _, _, ip, port, user, password, hostname = sys.argv + [None]*(7-len(sys.argv))
        launch_discovery_and_collect(ip, port, user, password, hostname)
    elif mode == 'collect':
        if len(sys.argv) != 7:
            print("Uso: huawei_health.py collect <ip> <porta> <login> <senha> <hostname>", file=sys.stderr)
            sys.exit(1)
        _, _, ip, port, user, password, hostname = sys.argv + [None]*(7-len(sys.argv))
        collect(ip, port, user, password, hostname)
    else:
        print("ERRO: Modo desconhecido. Use launch_discovery ou collect.", file=sys.stderr)
        sys.exit(2)

if __name__ == '__main__':
    main()
