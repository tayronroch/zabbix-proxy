#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Huawei SFP collector - otimizado para executar discovery e coleta em uma unica operacao

Usage:
  huawei_sfp.py launch_discovery <ip> <port> <user> <password> <hostname>
  huawei_sfp.py collect <ip> <port> <user> <password> <hostname>

OTIMIZADO: launch_discovery agora executa discovery + coleta em uma unica operacao  
PERFORMANCE: Sequencial otimizado sem debug - versao final para producao
"""

import sys
import re
import subprocess
import paramiko
import json
import time

# Cache simples para evitar comandos duplicados
command_cache = {}

def ssh_command_with_cache(ip, port, user, password, command):
    """Executa comando SSH com cache - OTIMIZADO PARA PRODUCAO"""
    global command_cache
    
    # Verifica cache primeiro
    cache_key = f"{ip}:{port}:{command}"
    if cache_key in command_cache:
        return command_cache[cache_key]
    
    # Executa comando com timeouts otimizados
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=port, username=user, password=password, 
                   look_for_keys=False, timeout=10)  # Otimizado
        stdin, stdout, stderr = ssh.exec_command(command, timeout=20)  # Otimizado
        raw = stdout.read()
        try:
            output = raw.decode("utf-8")
        except UnicodeDecodeError:
            output = raw.decode("latin1")
        ssh.close()
        
        # Armazena no cache
        command_cache[cache_key] = output
        return output
        
    except Exception as e:
        raise Exception(f"Erro SSH em '{command}': {str(e)}")

def clear_cache():
    """Limpa cache de comandos"""
    global command_cache
    command_cache.clear()

def send_zabbix_metric(hostname, key, value, timeout=5):
    """Envia metrica individual para Zabbix - OTIMIZADO"""
    try:
        result = subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, 
            "-k", key, "-o", str(value)
        ], capture_output=True, timeout=timeout, text=True)
        return result.returncode == 0
    except Exception:
        return False

def get_interfaces(ip, port, user, password):
    """Funcao original para obter interfaces - com cache otimizado"""
    output = ssh_command_with_cache(ip, port, user, password, "display interface description | no-more")
    
    interfaces = {}
    for line in output.splitlines():
        m = re.match(r"(\S+)\s+\S+\s+\S+\s+(.*)", line.strip())
        if m:
            ifname = m.group(1)
            ifalias = m.group(2).strip()
            if ifname.startswith("100GE") and ifalias:
                interfaces[ifname] = ifalias
    
    return interfaces

def parse_optical_output(output):
    """Funcao original de parsing - sem alteracoes"""
    values = {}
    patterns = {
        "temp": r"Temperature\(C\)\s+([-\d\.]+)",
        "volt": r"Supply Voltage\(V\)\s+([-\d\.]+)",
        "curr": [r"Tx{} Bias\(mA\)\s+([-\d\.]+)".format(i) for i in range(4)],
        "txpower": [r"Tx{} Power\(avg dBm\)\s+([-\d\.]+)".format(i) for i in range(4)],
        "rxpower": [r"Rx{} Power\(avg dBm\)\s+([-\d\.]+)".format(i) for i in range(4)]
    }
    
    m = re.search(patterns["temp"], output)
    if m:
        values["temp"] = m.group(1)
    m = re.search(patterns["volt"], output)
    if m:
        values["volt"] = m.group(1)
    
    for i in range(4):
        m = re.search(patterns["curr"][i], output)
        if m:
            values[f"curr{i+1}"] = m.group(1)
        m = re.search(patterns["txpower"][i], output)
        if m:
            values[f"txpower{i+1}"] = m.group(1)
        m = re.search(patterns["rxpower"][i], output)
        if m:
            values[f"rxpower{i+1}"] = m.group(1)
    
    return values

def launch_discovery_original(ip, port, user, password, hostname):
    """Discovery original - mantido para compatibilidade"""
    try:
        interfaces = get_interfaces(ip, port, user, password)
        
        discovery_data = []
        for ifname, ifalias in interfaces.items():
            discovery_data.append({
                "{#IFNAME}": ifname,
                "{#IFALIAS}": ifalias
            })
        
        payload = json.dumps({"data": discovery_data}, separators=(',', ':'))
        
        # Envia discovery
        result = subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", "huawei.sfp.discovery", "-o", payload
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

def collect_original_optimized(ip, port, user, password, hostname):
    """Coleta otimizada - versao final para producao"""
    try:
        interfaces = get_interfaces(ip, port, user, password)
        
        success_count = 0
        error_count = 0
        
        for ifname, ifalias in interfaces.items():
            try:
                # Comando otimizado para Huawei
                output = ssh_command_with_cache(ip, port, user, password, 
                    f"display interface {ifname} transceiver verbose | no-more")
                
                values = parse_optical_output(output)
                
                # Envia metricas
                for key, value in values.items():
                    if send_zabbix_metric(hostname, f"huawei.sfp[{ifname},{key}]", value):
                        success_count += 1
                    else:
                        error_count += 1
                        
            except Exception as e:
                error_count += 1
                print(f"ERROR: {ifname} - {str(e)}")
        
        print(f"SUCCESS: {success_count} metricas enviadas, {error_count} erros")
        return success_count > 0
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

def launch_discovery_and_collect(ip, port, user, password, hostname):
    """OTIMIZADO: Executa discovery + coleta em uma unica operacao"""
    try:
        print(f"🚀 Iniciando discovery + coleta para {hostname} ({ip})")
        
        # Obtem interfaces uma unica vez
        interfaces = get_interfaces(ip, port, user, password)
        
        if not interfaces:
            print(f"❌ Nenhuma interface 100GE encontrada em {hostname}")
            return False
        
        # Discovery
        discovery_data = []
        for ifname, ifalias in interfaces.items():
            discovery_data.append({
                "{#IFNAME}": ifname,
                "{#IFALIAS}": ifalias
            })
        
        payload = json.dumps({"data": discovery_data}, separators=(',', ':'))
        
        # Envia discovery
        discovery_result = subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname,
            "-k", "huawei.sfp.discovery", "-o", payload
        ], capture_output=True, text=True)
        
        # Coleta
        success_count = 0
        error_count = 0
        
        for ifname, ifalias in interfaces.items():
            try:
                output = ssh_command_with_cache(ip, port, user, password, 
                    f"display interface {ifname} transceiver verbose | no-more")
                
                values = parse_optical_output(output)
                
                for key, value in values.items():
                    if send_zabbix_metric(hostname, f"huawei.sfp[{ifname},{key}]", value):
                        success_count += 1
                    else:
                        error_count += 1
                        
            except Exception as e:
                error_count += 1
                print(f"❌ {ifname}: {str(e)}")
        
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
    return collect_original_optimized(ip, port, user, password, hostname)

def main():
    if len(sys.argv) < 6:
        print("Usage: huawei_sfp.py <launch_discovery|collect> <ip> <port> <user> <password> <hostname>")
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