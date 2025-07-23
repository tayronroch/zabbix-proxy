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
    slot = "9" # ajuste se slot dinamico
    found_table = False
    for line in temperature_output.splitlines():
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
                "board": board,
                "i2c": i2c,
                "addr": addr,
                "chl": chl,
                "temp": temp,
                "slot": slot
            })
    return result

def send_zabbix_metric(hostname, key, value, timeout=5):
    """Envia metrica individual para Zabbix"""
    try:
        result = subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, 
            "-k", key, "-o", str(value)
        ], capture_output=True, timeout=timeout, text=True)
        return result.returncode == 0
    except Exception:
        return False

def launch_discovery_original(ip, port, user, password, hostname):
    """Discovery original - mantido para compatibilidade"""
    try:
        # Obtem informacoes basicas
        version_output = ssh_command(ip, port, user, password, "display version")
        temperature_output = ssh_command(ip, port, user, password, "display environment")
        
        # Parse dados
        version = parse_version(version_output)
        temperatures = parse_ipu_temperature_full(temperature_output)
        
        # Cria discovery data
        discovery_data = []
        discovery_data.append({
            "{#VERSION}": version,
            "{#UPTIME}": parse_uptime(version_output)
        })
        
        for temp in temperatures:
            discovery_data.append({
                "{#BOARD}": temp["board"],
                "{#SLOT}": temp["slot"],
                "{#TEMP}": temp["temp"]
            })
        
        payload = json.dumps({"data": discovery_data}, separators=(',', ':'))
        
        # Envia discovery
        result = subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", "huawei.health.discovery", "-o", payload
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"SUCCESS: Discovery enviado para {hostname}")
            return True
        else:
            print(f"ERROR: Falha no discovery para {hostname}")
            return False
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

def collect_original(ip, port, user, password, hostname):
    """Coleta original - versao final para producao"""
    try:
        # Obtem dados
        cpu_output = ssh_command(ip, port, user, password, "display cpu-usage")
        memory_output = ssh_command(ip, port, user, password, "display memory-usage")
        version_output = ssh_command(ip, port, user, password, "display version")
        temperature_output = ssh_command(ip, port, user, password, "display environment")
        
        # Parse dados
        cpu_usage = parse_cpu(cpu_output)
        memory_data = parse_memory(memory_output)
        temperatures = parse_ipu_temperature_full(temperature_output)
        
        # Envia metricas
        success_count = 0
        error_count = 0
        
        # CPU
        if cpu_usage != -1:
            if send_zabbix_metric(hostname, "huawei.cpu.usage", cpu_usage):
                success_count += 1
            else:
                error_count += 1
        
        # Memory
        if memory_data[0] != -1:
            if send_zabbix_metric(hostname, "huawei.memory.total", memory_data[0]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.used", memory_data[1]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.free", memory_data[2]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.used_pct", memory_data[3]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.free_pct", memory_data[4]):
                success_count += 1
            else:
                error_count += 1
        
        # Temperature
        for temp in temperatures:
            if send_zabbix_metric(hostname, f"huawei.temperature[{temp['board']}]", temp["temp"]):
                success_count += 1
            else:
                error_count += 1
        
        print(f"SUCCESS: {success_count} metricas enviadas, {error_count} erros")
        return success_count > 0
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

def launch_discovery_and_collect(ip, port, user, password, hostname):
    """OTIMIZADO: Executa discovery + coleta em uma unica operacao"""
    try:
        print(f"🚀 Iniciando discovery + coleta para {hostname} ({ip})")
        
        # Obtem dados uma unica vez
        cpu_output = ssh_command(ip, port, user, password, "display cpu-usage")
        memory_output = ssh_command(ip, port, user, password, "display memory-usage")
        version_output = ssh_command(ip, port, user, password, "display version")
        temperature_output = ssh_command(ip, port, user, password, "display environment")
        
        # Parse dados
        cpu_usage = parse_cpu(cpu_output)
        memory_data = parse_memory(memory_output)
        version = parse_version(version_output)
        temperatures = parse_ipu_temperature_full(temperature_output)
        
        # Discovery
        discovery_data = []
        discovery_data.append({
            "{#VERSION}": version,
            "{#UPTIME}": parse_uptime(version_output)
        })
        
        for temp in temperatures:
            discovery_data.append({
                "{#BOARD}": temp["board"],
                "{#SLOT}": temp["slot"],
                "{#TEMP}": temp["temp"]
            })
        
        payload = json.dumps({"data": discovery_data}, separators=(',', ':'))
        
        # Envia discovery
        discovery_result = subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", "huawei.health.discovery", "-o", payload
        ], capture_output=True, text=True)
        
        # Coleta
        success_count = 0
        error_count = 0
        
        # CPU
        if cpu_usage != -1:
            if send_zabbix_metric(hostname, "huawei.cpu.usage", cpu_usage):
                success_count += 1
            else:
                error_count += 1
        
        # Memory
        if memory_data[0] != -1:
            if send_zabbix_metric(hostname, "huawei.memory.total", memory_data[0]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.used", memory_data[1]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.free", memory_data[2]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.used_pct", memory_data[3]):
                success_count += 1
            else:
                error_count += 1
            if send_zabbix_metric(hostname, "huawei.memory.free_pct", memory_data[4]):
                success_count += 1
            else:
                error_count += 1
        
        # Temperature
        for temp in temperatures:
            if send_zabbix_metric(hostname, f"huawei.temperature[{temp['board']}]", temp["temp"]):
                success_count += 1
            else:
                error_count += 1
        
        # Resultado final
        if discovery_result.returncode == 0 and error_count == 0:
            print(f"✅ SUCCESS: Discovery + {success_count} metricas enviadas")
            return True
        elif discovery_result.returncode != 0:
            print(f"❌ ERROR: Falha no discovery")
            return False
        else:
            print(f"⚠️ PARCIAL: Discovery OK, {error_count} metricas falharam")
            return success_count > 0
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def collect(ip, port, user, password, hostname):
    """Mantido para compatibilidade - executa apenas coleta"""
    return collect_original(ip, port, user, password, hostname)

def main():
    if len(sys.argv) < 6:
        print("Usage: huawei_health.py <launch_discovery|collect> <ip> <port> <user> <password> <hostname>")
        sys.exit(1)
    
    action = sys.argv[1]
    ip = sys.argv[2]
    port = int(sys.argv[3])
    user = sys.argv[4]
    password = sys.argv[5]
    hostname = sys.argv[6]
    
    if action == "launch_discovery":
        launch_discovery_and_collect(ip, port, user, password, hostname)
    elif action == "collect":
        collect(ip, port, user, password, hostname)
    else:
        print("Unknown action")
        sys.exit(1)

if __name__ == "__main__":
    main() 