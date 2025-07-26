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
        for key in ["curr", "txpower", "rxpower"]:
            m = re.search(patterns[key][i], output)
            if m:
                values[f"{key}_{i}"] = m.group(1)
    
    return values

def launch_discovery_original(ip, port, user, password, hostname):
    """Funcao original de discovery que funcionava - OTIMIZADO"""
    interfaces = get_interfaces(ip, port, user, password)
    discovery_gbic = []
    discovery_tempvolt = []
    
    for ifname, ifalias in interfaces.items():
        for lane in range(4):
            discovery_gbic.append({
                "{#IFNAME}": ifname,
                "{#IFALIAS}": ifalias,
                "{#GBIC_LANE}": f"Lane {lane}"
            })
        discovery_tempvolt.append({
            "{#IFNAME}": ifname,
            "{#IFALIAS}": ifalias
        })
    
    # Discovery otimizado
    subprocess.run([
        "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic", 
        "-o", json.dumps({"data": discovery_gbic})
    ], capture_output=True, timeout=8)
    
    subprocess.run([
        "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic_temp_volt", 
        "-o", json.dumps({"data": discovery_tempvolt})
    ], capture_output=True, timeout=8)

def collect_original_optimized(ip, port, user, password, hostname):
    """Funcao original de collect OTIMIZADA - versao final"""
    start_time = time.time()
    
    # Reutiliza interfaces do cache se ja foram obtidas no discovery
    interfaces = get_interfaces(ip, port, user, password)
    
    success_count = 0
    error_count = 0

    for ifname, ifalias in interfaces.items():
        try:
            # Usa cache para comandos de interface especifica
            command = f"display optical-module extend information interface {ifname} | no-more"
            output = ssh_command_with_cache(ip, port, user, password, command)
            
            values = parse_optical_output(output)

            # Temp e volt (sem lane)
            if "temp" in values:
                if send_zabbix_metric(hostname, f"temp[{ifname}]", values["temp"]):
                    success_count += 1
                else:
                    error_count += 1
                    
            if "volt" in values:
                if send_zabbix_metric(hostname, f"volt[{ifname}]", values["volt"]):
                    success_count += 1
                else:
                    error_count += 1
            
            # Curr, txpower, rxpower para cada Lane
            for i in range(4):
                lane_str = f"Lane {i}"
                for key in ["curr", "txpower", "rxpower"]:
                    value_key = f"{key}_{i}"
                    if value_key in values:
                        zabbix_key = f"{key}[{ifname},{lane_str}]"
                        if send_zabbix_metric(hostname, zabbix_key, values[value_key]):
                            success_count += 1
                        else:
                            error_count += 1
                            
        except Exception as e:
            error_count += 1
    
    elapsed = time.time() - start_time
    
    return success_count, error_count, elapsed

def launch_discovery_and_collect(ip, port, user, password, hostname):
    """Executa discovery e coleta OTIMIZADO - versao final para producao"""
    try:
        start_time = time.time()
        
        # Limpa cache
        clear_cache()
        
        # Executa discovery original
        launch_discovery_original(ip, port, user, password, hostname)
        
        # Executa collect otimizado
        success_count, error_count, collect_time = collect_original_optimized(ip, port, user, password, hostname)
        
        elapsed = time.time() - start_time
        
        # Feedback conciso de performance
        total = success_count + error_count
        if error_count == 0:
            print("SUCESSO: Discovery e coleta executados com sucesso!")
            print(f"Metricas: {success_count} processadas em {elapsed:.1f}s")
        else:
            print(f"PARCIAL: {error_count} falhas de {total} metricas total em {elapsed:.1f}s")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
    finally:
        clear_cache()

def collect(ip, port, user, password, hostname):
    """Funcao de collect para compatibilidade - OTIMIZADA"""
    try:
        clear_cache()
        
        success_count, error_count, elapsed = collect_original_optimized(ip, port, user, password, hostname)
        
        total = success_count + error_count
        if error_count == 0:
            print("SUCESSO: Coleta executada com sucesso!")
            print(f"Metricas: {success_count} processadas em {elapsed:.1f}s")
        else:
            print(f"PARCIAL: {error_count} falhas de {total} metricas total em {elapsed:.1f}s")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
    finally:
        clear_cache()

def main():
    if len(sys.argv) < 2:
        print("Uso: huawei_sfp.py <launch_discovery|collect> <ip> <port> <user> <password> <hostname>", file=sys.stderr)
        sys.exit(1)
    
    mode = sys.argv[1]
    if mode == "launch_discovery":
        if len(sys.argv) != 7:
            print("Uso: huawei_sfp.py launch_discovery <ip> <port> <user> <password> <hostname>", file=sys.stderr)
            sys.exit(1)
        _, _, ip, port, user, password, hostname = sys.argv
        launch_discovery_and_collect(ip, int(port), user, password, hostname)
    elif mode == "collect":
        if len(sys.argv) != 7:
            print("Uso: huawei_sfp.py collect <ip> <port> <user> <password> <hostname>", file=sys.stderr)
            sys.exit(1)
        _, _, ip, port, user, password, hostname = sys.argv
        collect(ip, int(port), user, password, hostname)
    else:
        print("ERRO: Modo desconhecido. Use launch_discovery ou collect.", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()