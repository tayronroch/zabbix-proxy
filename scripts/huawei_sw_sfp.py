#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Huawei Switch SFP collector - adaptado para switches da linha CE/S series

Usage:
  huawei_sw_sfp.py launch_discovery <ip> <port> <user> <password> <hostname>
  huawei_sw_sfp.py collect <ip> <port> <user> <password> <hostname>

OTIMIZADO: Para switches Huawei CE/S series com comandos específicos para BGP, hardware e SFP
PERFORMANCE: Sequencial otimizado sem debug - versao final para producao
"""

import sys
import re
import subprocess
import paramiko
import json
import time
import signal

# Cache simples para evitar comandos duplicados
command_cache = {}

def timeout_handler(signum, frame):
    """Handler para timeout geral"""
    raise TimeoutError("Script timeout - execução excedeu 30 segundos")

def set_timeout(seconds=30):
    """Define timeout geral para o script"""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

def ssh_execute_commands_batch(ip, port, user, password, commands, debug=False):
    """Executa múltiplos comandos em uma única sessão SSH"""
    ssh = None
    results = {}
    
    try:
        if debug:
            print(f"DEBUG: Executando batch de {len(commands)} comandos SSH")
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=port, username=user, password=password, 
                   look_for_keys=False, timeout=5)
        
        # Constrói comando completo com screen-length no início
        full_command = "screen-length 0 temporary\n" + "\n".join(commands)
        
        if debug:
            print(f"DEBUG: Executando comando combinado: {full_command[:200]}...")
        
        _, stdout, stderr = ssh.exec_command(full_command, timeout=25)
        raw_output = stdout.read()
        error_output = stderr.read().decode('utf-8', errors='ignore')
        
        if debug and error_output:
            print(f"DEBUG: SSH stderr: {error_output[:200]}")
        
        try:
            full_output = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            full_output = raw_output.decode("latin1")
        
        ssh.close()
        
        if debug:
            print(f"DEBUG: Batch executado. Output size: {len(full_output)} chars")
        
        # Parse da saída para separar cada comando
        # Procura pelos prompts do equipamento para separar as saídas
        command_outputs = []
        current_output = ""
        
        for line in full_output.splitlines():
            current_output += line + "\n"
            # Detecta fim de comando pelo prompt (ex: <HOSTNAME>)
            if line.strip().endswith(">") and ">" in line and len(line.strip()) < 100:
                command_outputs.append(current_output)
                current_output = ""
        
        # Se sobrou algo, adiciona
        if current_output.strip():
            command_outputs.append(current_output)
        
        # Mapeia saídas para comandos
        for i, cmd in enumerate(commands):
            if i < len(command_outputs):
                results[cmd] = command_outputs[i]
            else:
                results[cmd] = ""
        
        return results
        
    except Exception as e:
        if ssh:
            try:
                ssh.close()
            except:
                pass
        if debug:
            print(f"DEBUG: Erro SSH batch: {str(e)}")
        raise Exception(f"Erro SSH em batch: {str(e)}")

def ssh_command_with_cache(ip, port, user, password, command, debug=False, ssh_client=None):
    """Executa comando SSH com cache - COMPATIBILIDADE"""
    global command_cache
    
    # Verifica cache primeiro
    cache_key = f"{ip}:{port}:{command}"
    if cache_key in command_cache:
        if debug:
            print(f"DEBUG: Cache hit para '{command}'")
        return command_cache[cache_key]
    
    # Executa comando individual (fallback)
    ssh = None
    try:
        if debug:
            print(f"DEBUG: Executando comando SSH individual: '{command}'")
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=port, username=user, password=password, 
                   look_for_keys=False, timeout=5)
        
        full_command = f"screen-length 0 temporary; {command}"
        _, stdout, stderr = ssh.exec_command(full_command, timeout=8)
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
        if ssh:
            try:
                ssh.close()
            except:
                pass
        if debug:
            print(f"DEBUG: Erro SSH: {str(e)}")
        raise Exception(f"Erro SSH em '{command}': {str(e)}")

def clear_cache():
    """Limpa cache de comandos"""
    global command_cache
    command_cache.clear()

def send_zabbix_metric(hostname, key, value, timeout=3):
    """Envia metrica individual para Zabbix - OTIMIZADO"""
    try:
        result = subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, 
            "-k", key, "-o", str(value)
        ], capture_output=True, timeout=timeout, text=True)
        return result.returncode == 0
    except Exception:
        return False

def get_bgp_peers_ipv4(ip, port, user, password, debug=False):
    """Obtem peers BGP IPv4"""
    output = ssh_command_with_cache(ip, port, user, password, "display bgp peer verbose", debug)
    
    peers = {}
    current_peer = None
    
    for line in output.splitlines():
        line = line.strip()
        
        # Identifica peer IPv4 - formato similar ao IPv6
        if "BGP Peer is" in line:
            peer_match = re.search(r"BGP Peer is ([^,]+),\s+remote AS (\d+)", line)
            if peer_match:
                current_peer = peer_match.group(1).strip()
                remote_as = peer_match.group(2)
                peers[current_peer] = {"remote_as": remote_as}
                if debug:
                    print(f"DEBUG: Found BGP IPv4 peer: {current_peer}, AS: {remote_as}")
        
        # Estado do peer
        elif current_peer and "BGP current state:" in line:
            state_match = re.search(r"BGP current state:\s*(\w+)", line)
            if state_match:
                state = state_match.group(1)
                peers[current_peer]["state"] = state
                peers[current_peer]["state_num"] = "1" if state == "Established" else "0"
                if debug:
                    print(f"DEBUG: BGP state for {current_peer}: {state}")
        
        # Prefixos recebidos
        elif current_peer and "Received total routes:" in line:
            routes_match = re.search(r"Received total routes:\s*(\d+)", line)
            if routes_match:
                routes = routes_match.group(1)
                peers[current_peer]["received_routes"] = routes
                if debug:
                    print(f"DEBUG: Routes for {current_peer}: {routes}")
    
    if debug:
        print(f"DEBUG: Total BGP IPv4 peers found: {len(peers)}")
    
    return peers

def get_bgp_peers_ipv6(ip, port, user, password, debug=False):
    """Obtem peers BGP IPv6"""
    output = ssh_command_with_cache(ip, port, user, password, "display bgp ipv6 peer verbose", debug)
    
    peers = {}
    current_peer = None
    
    for line in output.splitlines():
        line = line.strip()
        
        # Identifica peer IPv6 - formato: "BGP Peer is 2804:3128:1:5169::FFFE,  remote AS 11344"
        if "BGP Peer is" in line:
            peer_match = re.search(r"BGP Peer is ([^,]+),\s+remote AS (\d+)", line)
            if peer_match:
                current_peer = peer_match.group(1).strip()
                remote_as = peer_match.group(2)
                peers[current_peer] = {"remote_as": remote_as}
                if debug:
                    print(f"DEBUG: Found BGP IPv6 peer: {current_peer}, AS: {remote_as}")
        
        # Estado do peer - formato: "BGP current state: Established, Up for 20h46m48s"
        elif current_peer and "BGP current state:" in line:
            state_match = re.search(r"BGP current state:\s*(\w+)", line)
            if state_match:
                state = state_match.group(1)
                peers[current_peer]["state"] = state
                # Converte para número (1=Established, 0=outros)
                peers[current_peer]["state_num"] = "1" if state == "Established" else "0"
                if debug:
                    print(f"DEBUG: BGP state for {current_peer}: {state}")
        
        # Prefixos recebidos - formato: "Received total routes: 0"
        elif current_peer and "Received total routes:" in line:
            routes_match = re.search(r"Received total routes:\s*(\d+)", line)
            if routes_match:
                routes = routes_match.group(1)
                peers[current_peer]["received_routes"] = routes
                if debug:
                    print(f"DEBUG: Routes for {current_peer}: {routes}")
    
    if debug:
        print(f"DEBUG: Total BGP IPv6 peers found: {len(peers)}")
    
    return peers

def get_power_info(ip, port, user, password, debug=False):
    """Obtem informações de energia"""
    output = ssh_command_with_cache(ip, port, user, password, "display power", debug)
    power_mgmt = ssh_command_with_cache(ip, port, user, password, "display power manage power-information", debug)
    
    power_data = {}
    
    # Parse display power - formato tabular:
    # Slot    PowerID  Online   Mode   State      Power(W)
    # 0       PWR1     Present  DC     Supply      1000.00
    for line in output.splitlines():
        line = line.strip()
        if re.match(r"^\d+\s+PWR\d+", line):
            parts = line.split()
            if len(parts) >= 6:
                power_id = parts[1]
                state = parts[4]
                power_w = parts[5]
                
                power_data[f"{power_id.lower()}_state"] = "1" if state == "Supply" else "0"
                power_data[f"{power_id.lower()}_power"] = power_w
                
                if debug:
                    print(f"DEBUG: Power {power_id}: {state}, {power_w}W")
    
    # Parse power management:
    # The current power consumption (mW)  : 98000
    for line in power_mgmt.splitlines():
        if "current power consumption (mW)" in line:
            current_match = re.search(r":\s*(\d+)", line)
            if current_match:
                # Converte mW para W
                power_mw = int(current_match.group(1))
                power_data["current_power_w"] = str(power_mw / 1000)
                if debug:
                    print(f"DEBUG: Current power: {power_mw}mW = {power_mw/1000}W")
        
        elif "average power consumption (mW)" in line:
            avg_match = re.search(r":\s*(\d+)", line)
            if avg_match:
                power_mw = int(avg_match.group(1))
                power_data["average_power_w"] = str(power_mw / 1000)
    
    return power_data

def get_fan_info(ip, port, user, password, debug=False):
    """Obtem informações dos ventiladores"""
    output = ssh_command_with_cache(ip, port, user, password, "display fan", debug)
    
    fans = {}
    
    # Parse formato tabular:
    # Slot  FanID   Online    Status    Speed     Mode     Airflow         Auto Min-Speed
    # 0         1   Present   Normal      40%     Auto     Front-to-Back                -
    for line in output.splitlines():
        line = line.strip()
        if re.match(r"^\d+\s+\d+\s+Present", line):
            parts = line.split()
            if len(parts) >= 5:
                fan_id = parts[1]
                status = parts[3]
                speed_percent = parts[4].replace('%', '')
                
                fans[f"fan_{fan_id}_status"] = "1" if status == "Normal" else "0"
                fans[f"fan_{fan_id}_speed_percent"] = speed_percent
                
                if debug:
                    print(f"DEBUG: Fan {fan_id}: {status}, {speed_percent}%")
    
    return fans

def get_version_info(ip, port, user, password, debug=False):
    """Obtem informações de versão"""
    output = ssh_command_with_cache(ip, port, user, password, "display version", debug)
    
    version_data = {}
    
    for line in output.splitlines():
        line = line.strip()
        
        # Software version: "VRP (R) software, Version 5.170 (S6730 V200R019C10SPC500)"
        if "VRP (R) software, Version" in line:
            version_match = re.search(r"Version\s+([\d\.]+)\s+\(([^)]+)\)", line)
            if version_match:
                version_data["software_version"] = version_match.group(1)
                version_data["software_build"] = version_match.group(2)
                if debug:
                    print(f"DEBUG: Software version: {version_match.group(1)}, build: {version_match.group(2)}")
        
        # Model: "HUAWEI S6730-H24X6C Routing Switch uptime is 42 weeks, 3 days, 12 hours, 14 minutes"
        elif "HUAWEI" in line and "uptime is" in line:
            model_match = re.search(r"HUAWEI\s+([\w-]+)", line)
            uptime_match = re.search(r"uptime is\s+(.+)", line)
            
            if model_match:
                version_data["device_model"] = model_match.group(1)
                if debug:
                    print(f"DEBUG: Device model: {model_match.group(1)}")
            
            if uptime_match:
                version_data["uptime"] = uptime_match.group(1).strip()
                if debug:
                    print(f"DEBUG: Uptime: {uptime_match.group(1)}")
        
        # BootROM: "BootROM       Version   : 0000.04f1"
        elif "BootROM" in line and "Version" in line:
            bootrom_match = re.search(r"BootROM\s+Version\s*:\s*([\w\.]+)", line)
            if bootrom_match:
                version_data["bootrom_version"] = bootrom_match.group(1)
    
    return version_data

def get_interfaces(ip, port, user, password, ssh_client=None):
    """Obtem interfaces com descrição"""
    output = ssh_command_with_cache(ip, port, user, password, "display interface description")
    
    interfaces = {}
    for line in output.splitlines():
        line = line.strip()
        # Ignora linhas de cabeçalho e informações
        if line.startswith("PHY:") or line.startswith("*down:") or line.startswith("#down:"):
            continue
        if line.startswith("(") or line.startswith("Interface"):
            continue
        if not line:
            continue
            
        # Parse das linhas de interface: Interface PHY Protocol Description
        parts = line.split()
        if len(parts) >= 3:
            ifname = parts[0]
            phy_status = parts[1] 
            proto_status = parts[2]
            # Descrição pode ter espaços, junta tudo depois da 3ª coluna
            ifalias = " ".join(parts[3:]) if len(parts) > 3 else ""
            
            # Inclui apenas interfaces físicas com SFP/transceivers
            if any(x in ifname for x in ["XGE", "100GE", "25GE", "40GE", "GigabitEthernet"]):
                # Só inclui interfaces que estão UP fisicamente (têm transceiver)
                if phy_status == "up":
                    interfaces[ifname] = ifalias if ifalias else "No Description"
    
    return interfaces

def get_transceiver_info(ip, port, user, password, interface, debug=False, ssh_client=None):
    """Obtem informações detalhadas do transceiver para uma interface específica"""
    try:
        # Tenta primeiro comando verbose
        output = ssh_command_with_cache(ip, port, user, password, f"display transceiver verbose interface {interface}", debug)
    except Exception as e:
        if debug:
            print(f"DEBUG: Comando verbose falhou para {interface}: {str(e)}")
        try:
            # Fallback para comando simples
            output = ssh_command_with_cache(ip, port, user, password, f"display transceiver interface {interface}", debug)
            if debug:
                print(f"DEBUG: Usando comando simples para {interface}")
        except Exception as e2:
            if debug:
                print(f"DEBUG: Ambos comandos falharam para {interface}: {str(e2)}")
            return {}
    
    transceiver_data = {}
    
    # Parse temperatura - formato: "  Temperature(°C)             :41.74"
    temp_match = re.search(r"Temperature\([^)]+\)\s*:\s*([+-]?\d+\.?\d*)", output)
    if temp_match:
        transceiver_data["temperature"] = temp_match.group(1)
        if debug:
            print(f"DEBUG: {interface} temperature: {temp_match.group(1)}°C")
    
    # Parse voltagem - formato: "  Voltage(V)                    :3.30"
    volt_match = re.search(r"Voltage\(V\)\s*:\s*(\d+\.?\d*)", output)
    if volt_match:
        transceiver_data["voltage"] = volt_match.group(1)
        if debug:
            print(f"DEBUG: {interface} voltage: {volt_match.group(1)}V")
    
    # Parse bias current - formato melhorado baseado na saída real
    if "100GE" in interface:
        # 100GE multi-lane: "  Bias Current(mA)              :66.68|69.75(Lane0|Lane1)"
        bias_multiline_pattern = r"Bias Current\(mA\)\s*:\s*([\d\.\|]+)\(Lane\d+\|Lane\d+\)\s*\n?\s*([\d\.\|]+)\(Lane\d+\|Lane\d+\)?"
        bias_match = re.search(bias_multiline_pattern, output, re.MULTILINE)
        if bias_match:
            # Primeira linha de lanes
            bias_values1 = bias_match.group(1).split('|')
            for i, value in enumerate(bias_values1):
                transceiver_data[f"bias_current_lane_{i}"] = value.strip()
            # Segunda linha de lanes se existir
            if bias_match.group(2):
                bias_values2 = bias_match.group(2).split('|')
                for i, value in enumerate(bias_values2, start=len(bias_values1)):
                    transceiver_data[f"bias_current_lane_{i}"] = value.strip()
        else:
            # Fallback para linha única
            bias_match = re.search(r"Bias Current\(mA\)\s*:\s*([\d\.\|]+)", output)
            if bias_match and '|' in bias_match.group(1):
                bias_values = bias_match.group(1).split('|')
                for i, value in enumerate(bias_values):
                    transceiver_data[f"bias_current_lane_{i}"] = value.strip()
    else:
        # XGE simples: "  Bias Current(mA)              :7.23"
        bias_match = re.search(r"Bias Current\(mA\)\s*:\s*(\d+\.?\d*)", output)
        if bias_match:
            transceiver_data["bias_current"] = bias_match.group(1)
    
    # Parse TX power - formato melhorado
    if "100GE" in interface:
        # 100GE multi-lane: "  TX Power(dBM)                 :1.37|1.48(Lane0|Lane1)"
        tx_multiline_pattern = r"TX Power\(dBM\)\s*:\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)\s*\n?\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)?"
        tx_match = re.search(tx_multiline_pattern, output, re.MULTILINE)
        if tx_match:
            # Primeira linha
            tx_values1 = tx_match.group(1).split('|')
            for i, value in enumerate(tx_values1):
                transceiver_data[f"tx_power_lane_{i}"] = value.strip()
            # Segunda linha se existir  
            if tx_match.group(2):
                tx_values2 = tx_match.group(2).split('|')
                for i, value in enumerate(tx_values2, start=len(tx_values1)):
                    transceiver_data[f"tx_power_lane_{i}"] = value.strip()
        else:
            # Fallback
            tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([\d\.\-\|]+)", output)
            if tx_match and '|' in tx_match.group(1):
                tx_values = tx_match.group(1).split('|')
                for i, value in enumerate(tx_values):
                    transceiver_data[f"tx_power_lane_{i}"] = value.strip()
    else:
        # XGE simples: "  TX Power(dBM)                 :-2.28"
        tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([+-]?\d+\.?\d*)", output)
        if tx_match:
            transceiver_data["tx_power"] = tx_match.group(1)
    
    # Parse RX power - formato melhorado
    if "100GE" in interface:
        # 100GE multi-lane: "  RX Power(dBM)                 :-0.50|-1.20(Lane0|Lane1)"
        rx_multiline_pattern = r"RX Power\(dBM\)\s*:\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)\s*\n?\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)?"
        rx_match = re.search(rx_multiline_pattern, output, re.MULTILINE)
        if rx_match:
            # Primeira linha
            rx_values1 = rx_match.group(1).split('|')
            for i, value in enumerate(rx_values1):
                transceiver_data[f"rx_power_lane_{i}"] = value.strip()
            # Segunda linha se existir
            if rx_match.group(2):
                rx_values2 = rx_match.group(2).split('|')
                for i, value in enumerate(rx_values2, start=len(rx_values1)):
                    transceiver_data[f"rx_power_lane_{i}"] = value.strip()
        else:
            # Fallback
            rx_match = re.search(r"RX Power\(dBM\)\s*:\s*([\d\.\-\|]+)", output)
            if rx_match and '|' in rx_match.group(1):
                rx_values = rx_match.group(1).split('|')
                for i, value in enumerate(rx_values):
                    transceiver_data[f"rx_power_lane_{i}"] = value.strip()
    else:
        # XGE simples: "  RX Power(dBM)                 :-2.75"
        rx_match = re.search(r"RX Power\(dBM\)\s*:\s*([+-]?\d+\.?\d*)", output)
        if rx_match:
            transceiver_data["rx_power"] = rx_match.group(1)
    
    if debug:
        print(f"DEBUG: {interface} transceiver data: {len(transceiver_data)} metrics")
    
    return transceiver_data

def parse_transceiver_output(output, interface, debug=False):
    """Parse da saída do comando display transceiver verbose interface"""
    transceiver_data = {}
    
    # Parse temperatura - formato: "  Temperature(°C)             :41.74"
    temp_match = re.search(r"Temperature\([^)]+\)\s*:\s*([+-]?\d+\.?\d*)", output)
    if temp_match:
        transceiver_data["temperature"] = temp_match.group(1)
        if debug:
            print(f"DEBUG: {interface} temperature: {temp_match.group(1)}°C")
    
    # Parse voltagem - formato: "  Voltage(V)                    :3.30"
    volt_match = re.search(r"Voltage\(V\)\s*:\s*(\d+\.?\d*)", output)
    if volt_match:
        transceiver_data["voltage"] = volt_match.group(1)
        if debug:
            print(f"DEBUG: {interface} voltage: {volt_match.group(1)}V")
    
    # Parse bias current - formato melhorado baseado na saída real
    if "100GE" in interface:
        # 100GE multi-lane: "  Bias Current(mA)              :66.68|69.75(Lane0|Lane1)"
        bias_multiline_pattern = r"Bias Current\(mA\)\s*:\s*([\d\.\|]+)\(Lane\d+\|Lane\d+\)\s*\n?\s*([\d\.\|]+)\(Lane\d+\|Lane\d+\)?"
        bias_match = re.search(bias_multiline_pattern, output, re.MULTILINE)
        if bias_match:
            # Primeira linha de lanes
            bias_values1 = bias_match.group(1).split('|')
            for i, value in enumerate(bias_values1):
                transceiver_data[f"bias_current_lane_{i}"] = value.strip()
            # Segunda linha de lanes se existir
            if bias_match.group(2):
                bias_values2 = bias_match.group(2).split('|')
                for i, value in enumerate(bias_values2, start=len(bias_values1)):
                    transceiver_data[f"bias_current_lane_{i}"] = value.strip()
        else:
            # Fallback para linha única
            bias_match = re.search(r"Bias Current\(mA\)\s*:\s*([\d\.\|]+)", output)
            if bias_match and '|' in bias_match.group(1):
                bias_values = bias_match.group(1).split('|')
                for i, value in enumerate(bias_values):
                    transceiver_data[f"bias_current_lane_{i}"] = value.strip()
    else:
        # XGE simples: "  Bias Current(mA)              :7.23"
        bias_match = re.search(r"Bias Current\(mA\)\s*:\s*(\d+\.?\d*)", output)
        if bias_match:
            transceiver_data["bias_current"] = bias_match.group(1)
    
    # Parse TX power - formato melhorado
    if "100GE" in interface:
        # 100GE multi-lane: "  TX Power(dBM)                 :1.37|1.48(Lane0|Lane1)"
        tx_multiline_pattern = r"TX Power\(dBM\)\s*:\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)\s*\n?\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)?"
        tx_match = re.search(tx_multiline_pattern, output, re.MULTILINE)
        if tx_match:
            # Primeira linha
            tx_values1 = tx_match.group(1).split('|')
            for i, value in enumerate(tx_values1):
                transceiver_data[f"tx_power_lane_{i}"] = value.strip()
            # Segunda linha se existir  
            if tx_match.group(2):
                tx_values2 = tx_match.group(2).split('|')
                for i, value in enumerate(tx_values2, start=len(tx_values1)):
                    transceiver_data[f"tx_power_lane_{i}"] = value.strip()
        else:
            # Fallback
            tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([\d\.\-\|]+)", output)
            if tx_match and '|' in tx_match.group(1):
                tx_values = tx_match.group(1).split('|')
                for i, value in enumerate(tx_values):
                    transceiver_data[f"tx_power_lane_{i}"] = value.strip()
    else:
        # XGE simples: "  TX Power(dBM)                 :-2.28"
        tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([+-]?\d+\.?\d*)", output)
        if tx_match:
            transceiver_data["tx_power"] = tx_match.group(1)
    
    # Parse RX power - formato melhorado
    if "100GE" in interface:
        # 100GE multi-lane: "  RX Power(dBM)                 :-0.50|-1.20(Lane0|Lane1)"
        rx_multiline_pattern = r"RX Power\(dBM\)\s*:\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)\s*\n?\s*([\d\.\-\|]+)\(Lane\d+\|Lane\d+\)?"
        rx_match = re.search(rx_multiline_pattern, output, re.MULTILINE)
        if rx_match:
            # Primeira linha
            rx_values1 = rx_match.group(1).split('|')
            for i, value in enumerate(rx_values1):
                transceiver_data[f"rx_power_lane_{i}"] = value.strip()
            # Segunda linha se existir
            if rx_match.group(2):
                rx_values2 = rx_match.group(2).split('|')
                for i, value in enumerate(rx_values2, start=len(rx_values1)):
                    transceiver_data[f"rx_power_lane_{i}"] = value.strip()
        else:
            # Fallback
            rx_match = re.search(r"RX Power\(dBM\)\s*:\s*([\d\.\-\|]+)", output)
            if rx_match and '|' in rx_match.group(1):
                rx_values = rx_match.group(1).split('|')
                for i, value in enumerate(rx_values):
                    transceiver_data[f"rx_power_lane_{i}"] = value.strip()
    else:
        # XGE simples: "  RX Power(dBM)                 :-2.75"
        rx_match = re.search(r"RX Power\(dBM\)\s*:\s*([+-]?\d+\.?\d*)", output)
        if rx_match:
            transceiver_data["rx_power"] = rx_match.group(1)
    
    if debug:
        print(f"DEBUG: {interface} transceiver data: {len(transceiver_data)} metrics")
    
    return transceiver_data

def launch_discovery_original(ip, port, user, password, hostname):
    """Discovery para switches Huawei"""
    interfaces = get_interfaces(ip, port, user, password)
    bgp_peers_v4 = get_bgp_peers_ipv4(ip, port, user, password)
    bgp_peers_v6 = get_bgp_peers_ipv6(ip, port, user, password)
    
    # Discovery de interfaces SFP - separa single e multi-lane
    discovery_single = []
    discovery_multi = []
    
    for ifname, ifalias in interfaces.items():
        if "100GE" in ifname:
            # Multi-lane interface - adiciona com lane 0 por padrão
            discovery_multi.append({
                "{#IFNAME}": ifname,
                "{#IFALIAS}": ifalias,
                "{#GBIC_LANE}": "0"
            })
        else:
            # Single-lane interface
            discovery_single.append({
                "{#IFNAME}": ifname,
                "{#IFALIAS}": ifalias
            })
    
    # Discovery de peers BGP IPv4
    discovery_bgp_v4 = []
    for peer_ip in bgp_peers_v4.keys():
        discovery_bgp_v4.append({
            "{#BGP_PEER}": peer_ip
        })
    
    # Discovery de peers BGP IPv6
    discovery_bgp_v6 = []
    for peer_ip in bgp_peers_v6.keys():
        discovery_bgp_v6.append({
            "{#BGP_PEER_V6}": peer_ip
        })
    
    # Envia discoveries SFP
    if discovery_single:
        subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic_single", 
            "-o", json.dumps({"data": discovery_single})
        ], capture_output=True, timeout=8)
        
    if discovery_multi:
        subprocess.run([
            "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic_multi", 
            "-o", json.dumps({"data": discovery_multi})
        ], capture_output=True, timeout=8)
    
    subprocess.run([
        "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_bgp_peers", 
        "-o", json.dumps({"data": discovery_bgp_v4})
    ], capture_output=True, timeout=8)
    
    subprocess.run([
        "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_bgp_peers_v6", 
        "-o", json.dumps({"data": discovery_bgp_v6})
    ], capture_output=True, timeout=8)

def collect_original_optimized(ip, port, user, password, hostname, debug=False):
    """Coleta otimizada para switches Huawei"""
    start_time = time.time()
    
    success_count = 0
    error_count = 0
    
    try:
        # Coleta BGP IPv4
        if debug:
            print("DEBUG: Coletando BGP IPv4 peers...")
        bgp_peers_v4 = get_bgp_peers_ipv4(ip, port, user, password, debug)
        for peer, data in bgp_peers_v4.items():
            for metric, value in data.items():
                key = f"bgp.peer.{metric}[{peer}]"
                if send_zabbix_metric(hostname, key, value):
                    success_count += 1
                    if debug:
                        print(f"DEBUG: Sent {key} = {value}")
                else:
                    error_count += 1
        
        # Coleta BGP IPv6
        if debug:
            print("DEBUG: Coletando BGP IPv6 peers...")
        bgp_peers_v6 = get_bgp_peers_ipv6(ip, port, user, password, debug)
        for peer, data in bgp_peers_v6.items():
            for metric, value in data.items():
                key = f"bgp.peer.v6.{metric}[{peer}]"
                if send_zabbix_metric(hostname, key, value):
                    success_count += 1
                    if debug:
                        print(f"DEBUG: Sent {key} = {value}")
                else:
                    error_count += 1
        
        # Coleta informações de energia
        if debug:
            print("DEBUG: Coletando informações de energia...")
        power_data = get_power_info(ip, port, user, password, debug)
        for metric, value in power_data.items():
            if send_zabbix_metric(hostname, f"system.power.{metric}", value):
                success_count += 1
            else:
                error_count += 1
        
        # Coleta informações dos ventiladores
        if debug:
            print("DEBUG: Coletando informações dos ventiladores...")
        fan_data = get_fan_info(ip, port, user, password, debug)
        for metric, value in fan_data.items():
            if send_zabbix_metric(hostname, f"system.{metric}", value):
                success_count += 1
            else:
                error_count += 1
        
        # Coleta informações de versão/sistema
        if debug:
            print("DEBUG: Coletando informações de versão...")
        version_data = get_version_info(ip, port, user, password, debug)
        for metric, value in version_data.items():
            if send_zabbix_metric(hostname, f"system.{metric}", value):
                success_count += 1
            else:
                error_count += 1
        
        # Coleta SFP/Transceivers
        if debug:
            print("DEBUG: Coletando SFP/Transceivers...")
        interfaces = get_interfaces(ip, port, user, password)
        for ifname in interfaces.keys():
            try:
                transceiver_data = get_transceiver_info(ip, port, user, password, ifname, debug)
                for metric, value in transceiver_data.items():
                    key = f"interface.sfp.{metric}[{ifname}]"
                    if send_zabbix_metric(hostname, key, value):
                        success_count += 1
                    else:
                        error_count += 1
            except Exception as ex:
                if debug:
                    print(f"DEBUG: Erro coletando transceiver {ifname}: {str(ex)}")
                error_count += 1
                
    except Exception as e:
        if debug:
            print(f"DEBUG: Erro geral na coleta: {str(e)}")
        error_count += 1
    
    elapsed = time.time() - start_time
    return success_count, error_count, elapsed

def launch_discovery_and_collect(ip, port, user, password, hostname, debug=False):
    """Executa discovery e coleta SUPER SIMPLES - APENAS 3 COMANDOS"""
    try:
        start_time = time.time()
        
        if debug:
            print("DEBUG: Iniciando coleta SFP simplificada...")
        
        # Limpa cache
        clear_cache()
        
        # UMA ÚNICA SESSÃO SSH com apenas 3 comandos essenciais
        commands = [
            "display interface description",
            "display transceiver verbose"
        ]
        
        if debug:
            print("DEBUG: Executando comandos SSH simplificados...")
        
        # Executa tudo em uma única sessão
        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, port=port, username=user, password=password, 
                       look_for_keys=False, timeout=3, banner_timeout=5)
            
            # Comando combinado exatamente como você pediu
            full_command = """screen-length 0 temporary
display interface description
display transceiver verbose"""
            
            if debug:
                print("DEBUG: Executando comando combinado...")
            
            _, stdout, stderr = ssh.exec_command(full_command, timeout=15)
            raw_output = stdout.read()
            
            try:
                full_output = raw_output.decode("utf-8")
            except UnicodeDecodeError:
                full_output = raw_output.decode("latin1")
            
            ssh.close()
            
            if debug:
                print(f"DEBUG: Comando executado. Output size: {len(full_output)} chars")
                print(f"DEBUG: Primeiras 1000 chars: {full_output[:1000]}")
            
            # Parse interfaces da saída combinada
            interfaces = {}
            lines = full_output.splitlines()
            
            # Procura pela seção de interfaces (após display interface description)
            interface_section = False
            for line in lines:
                line = line.strip()
                
                if "display interface description" in line:
                    interface_section = True
                    continue
                elif "display transceiver verbose" in line:
                    interface_section = False
                    break
                
                if interface_section:
                    # Ignora linhas de cabeçalho
                    if line.startswith("PHY:") or line.startswith("*down:") or line.startswith("#down:"):
                        continue
                    if line.startswith("(") or line.startswith("Interface"):
                        continue
                    if not line or line.endswith(">"):
                        continue
                        
                    # Parse das linhas de interface
                    parts = line.split()
                    if len(parts) >= 3:
                        ifname = parts[0]
                        phy_status = parts[1] 
                        ifalias = " ".join(parts[3:]) if len(parts) > 3 else "No Description"
                        
                        # Inclui apenas interfaces físicas com SFP UP
                        if any(x in ifname for x in ["XGE", "100GE", "25GE", "40GE"]) and phy_status == "up":
                            interfaces[ifname] = ifalias
            
            if debug:
                print(f"DEBUG: Interfaces encontradas: {len(interfaces)} - {list(interfaces.keys())}")
            
            # Processa discovery baseado nos dados reais dos transceivers
            discovery_single = []
            discovery_multi = []
            
            # Primeiro passo: coleta dados dos transceivers para discovery preciso
            for ifname, ifalias in interfaces.items():
                try:
                    # Procura pela seção desta interface na saída do transceiver verbose
                    interface_pattern = f"{ifname} transceiver information:"
                    start_idx = full_output.find(interface_pattern)
                    
                    if start_idx != -1:
                        # Encontra o fim da seção
                        next_interface = full_output.find(" transceiver information:", start_idx + 1)
                        if next_interface == -1:
                            interface_output = full_output[start_idx:]
                        else:
                            interface_output = full_output[start_idx:next_interface]
                        
                        # Parse para identificar lanes
                        transceiver_data = parse_transceiver_output(interface_output, ifname, debug)
                        
                        if "100GE" in ifname:
                            # Multi-lane: descobre quantas lanes existem
                            lanes_found = set()
                            for metric in transceiver_data.keys():
                                if "_lane_" in metric:
                                    lane_num = metric.split("_")[-1]
                                    lanes_found.add(lane_num)
                            
                            # Cria discovery para cada lane encontrada
                            for lane in sorted(lanes_found):
                                discovery_multi.append({
                                    "{#IFNAME}": ifname,
                                    "{#IFALIAS}": ifalias,
                                    "{#GBIC_LANE}": lane
                                })
                        else:
                            # Single-lane
                            if transceiver_data:  # Só adiciona se encontrou dados
                                discovery_single.append({
                                    "{#IFNAME}": ifname,
                                    "{#IFALIAS}": ifalias
                                })
                except Exception as ex:
                    if debug:
                        print(f"DEBUG: Erro no discovery de {ifname}: {str(ex)}")
                    # Fallback: adiciona baseado no nome da interface
                    if "100GE" in ifname:
                        discovery_multi.append({
                            "{#IFNAME}": ifname,
                            "{#IFALIAS}": ifalias,
                            "{#GBIC_LANE}": "0"
                        })
                    else:
                        discovery_single.append({
                            "{#IFNAME}": ifname,
                            "{#IFALIAS}": ifalias
                        })
            
            if debug:
                print(f"DEBUG: Single-lane discovery: {len(discovery_single)} interfaces")
                print(f"DEBUG: Multi-lane discovery: {len(discovery_multi)} interfaces")
            
            # Envia discovery para single-lane
            if discovery_single:
                discovery_result = subprocess.run([
                    "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic_single", 
                    "-o", json.dumps({"data": discovery_single})
                ], capture_output=True, timeout=5, text=True)
                
                if debug:
                    print(f"DEBUG: Single-lane discovery result: {discovery_result.returncode}")
                    if discovery_result.stderr:
                        print(f"DEBUG: Single-lane discovery stderr: {discovery_result.stderr}")
            
            # Envia discovery para multi-lane
            if discovery_multi:
                discovery_result = subprocess.run([
                    "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic_multi", 
                    "-o", json.dumps({"data": discovery_multi})
                ], capture_output=True, timeout=5, text=True)
            
            # Debug do último discovery executado
            if 'discovery_result' in locals():
                if debug:
                    print(f"DEBUG: Discovery sender result: {discovery_result.returncode}")
                    print(f"DEBUG: Discovery sender stdout: {discovery_result.stdout}")
                    print(f"DEBUG: Discovery sender stderr: {discovery_result.stderr}")
                
                if discovery_result.returncode != 0:
                    print(f"AVISO: Discovery pode ter falhado: {discovery_result.stderr}")
            else:
                if debug:
                    print("DEBUG: Nenhum discovery foi executado")
            
            # Aguarda um pouco para o Zabbix processar o discovery
            if debug:
                print("DEBUG: Aguardando processamento do discovery...")
            time.sleep(2)
            
            # Parse dados dos transceivers da saída combinada
            success_count = 0
            error_count = 0
            metrics_batch = []
            
            # Processa cada interface encontrada
            for ifname in interfaces.keys():
                try:
                    # Procura pela seção desta interface na saída do transceiver verbose
                    interface_pattern = f"{ifname} transceiver information:"
                    start_idx = full_output.find(interface_pattern)
                    
                    if start_idx != -1:
                        # Encontra o fim da seção (próxima interface ou fim)
                        next_interface = full_output.find(" transceiver information:", start_idx + 1)
                        if next_interface == -1:
                            interface_output = full_output[start_idx:]
                        else:
                            interface_output = full_output[start_idx:next_interface]
                        
                        # Parse dos dados SFP
                        transceiver_data = parse_transceiver_output(interface_output, ifname, debug)
                        
                        if debug:
                            print(f"DEBUG: Interface {ifname} - coletadas {len(transceiver_data)} métricas")
                        
                        # Envia métricas com as chaves corretas baseadas no tipo de interface
                        if "100GE" in ifname:
                            # Multi-lane interface - usa chaves ML com lane numbers
                            for metric, value in transceiver_data.items():
                                if metric.endswith("_lane_0") or metric.endswith("_lane_1") or metric.endswith("_lane_2") or metric.endswith("_lane_3"):
                                    # Extrai número da lane
                                    lane_num = metric.split("_")[-1]
                                    base_metric = "_".join(metric.split("_")[:-2])
                                    
                                    if base_metric == "bias_current":
                                        key = f"currML[{ifname},{lane_num}]"
                                    elif base_metric == "tx_power":
                                        key = f"txpowerML[{ifname},{lane_num}]"
                                    elif base_metric == "rx_power":
                                        key = f"rxpowerML[{ifname},{lane_num}]"
                                    else:
                                        continue
                                        
                                    metrics_batch.append(f"{hostname} {key} {value}")
                                    success_count += 1
                                elif metric == "temperature":
                                    key = f"tempML[{ifname},0]"
                                    metrics_batch.append(f"{hostname} {key} {value}")
                                    success_count += 1
                                elif metric == "voltage":
                                    key = f"voltML[{ifname},0]"
                                    metrics_batch.append(f"{hostname} {key} {value}")
                                    success_count += 1
                        else:
                            # Single-lane interface - usa chaves simples
                            for metric, value in transceiver_data.items():
                                if metric == "bias_current":
                                    key = f"curr[{ifname}]"
                                elif metric == "tx_power":
                                    key = f"txpower[{ifname}]"
                                elif metric == "rx_power":
                                    key = f"rxpower[{ifname}]"
                                elif metric == "temperature":
                                    key = f"temp[{ifname}]"
                                elif metric == "voltage":
                                    key = f"volt[{ifname}]"
                                else:
                                    continue
                                    
                                metrics_batch.append(f"{hostname} {key} {value}")
                                success_count += 1
                    else:
                        if debug:
                            print(f"DEBUG: Seção transceiver não encontrada para {ifname}")
                        error_count += 1
                        
                except Exception as ex:
                    if debug:
                        print(f"DEBUG: Erro processando {ifname}: {str(ex)}")
                    error_count += 1
            
            # Envia todas as métricas em lote
            if metrics_batch:
                try:
                    batch_data = "\n".join(metrics_batch)
                    process = subprocess.run([
                        "zabbix_sender", "-z", "127.0.0.1", "-i", "-"
                    ], input=batch_data, capture_output=True, timeout=5, text=True)
                    if process.returncode != 0:
                        if debug:
                            print(f"DEBUG: Zabbix sender falhou: {process.stderr}")
                        error_count += len(metrics_batch)
                        success_count = 0
                except Exception as e:
                    if debug:
                        print(f"DEBUG: Erro enviando métricas: {str(e)}")
                    error_count += len(metrics_batch)
                    success_count = 0
            
        except Exception as ssh_error:
            if ssh:
                try:
                    ssh.close()
                except:
                    pass
            raise ssh_error
        
        elapsed = time.time() - start_time
        
        # Feedback conciso de performance
        if error_count == 0:
            print("SUCESSO: Discovery e coleta SFP executados com sucesso!")
            print(f"Metricas SFP: {success_count} processadas em {elapsed:.1f}s")
        else:
            print(f"PARCIAL: {error_count} falhas de {success_count + error_count} metricas SFP em {elapsed:.1f}s")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
    finally:
        clear_cache()

def collect(ip, port, user, password, hostname, debug=False):
    """Funcao de collect para compatibilidade - OTIMIZADA"""
    try:
        clear_cache()
        
        success_count, error_count, elapsed = collect_original_optimized(ip, port, user, password, hostname, debug)
        
        total = success_count + error_count
        if error_count == 0:
            print("SUCESSO: Coleta executada com sucesso!")
            print(f"Metricas: {success_count} processadas em {elapsed:.1f}s")
        else:
            print(f"PARCIAL: {error_count} falhas de {total} metricas total em {elapsed:.1f}s")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
    finally:
        clear_cache()

def main():
    # Define timeout geral de 30 segundos
    set_timeout(30)
    
    try:
        if len(sys.argv) < 2:
            print("Uso: huawei_sw_sfp.py <launch_discovery|collect> <ip> <port> <user> <password> <hostname> [debug]", file=sys.stderr)
            sys.exit(1)
        
        # Verifica se debug foi habilitado
        debug = len(sys.argv) > 7 and sys.argv[7].lower() == "debug"
        
        mode = sys.argv[1]
        if mode == "launch_discovery":
            if len(sys.argv) < 7:
                print("Uso: huawei_sw_sfp.py launch_discovery <ip> <port> <user> <password> <hostname> [debug]", file=sys.stderr)
                sys.exit(1)
            _, _, ip, port, user, password, hostname = sys.argv[:7]
            
            # Validação de parâmetros - verifica se macros foram substituídas
            if port.startswith('{$') or user.startswith('{$') or password.startswith('{$'):
                print("ERRO: Macros não foram substituídas pelo Zabbix. Verifique se {$SSH_PORT}, {$SSH_USER} e {$SSH_PASS} estão definidas no template.", file=sys.stderr)
                sys.exit(1)
            
            try:
                port_int = int(port)
            except ValueError:
                print(f"ERRO: Porta SSH inválida: '{port}'. Deve ser um número.", file=sys.stderr)
                sys.exit(1)
                
            launch_discovery_and_collect(ip, port_int, user, password, hostname, debug)
        elif mode == "collect":
            if len(sys.argv) < 7:
                print("Uso: huawei_sw_sfp.py collect <ip> <port> <user> <password> <hostname> [debug]", file=sys.stderr)
                sys.exit(1)
            _, _, ip, port, user, password, hostname = sys.argv[:7]
            
            # Validação de parâmetros - verifica se macros foram substituídas
            if port.startswith('{$') or user.startswith('{$') or password.startswith('{$'):
                print("ERRO: Macros não foram substituídas pelo Zabbix. Verifique se {$SSH_PORT}, {$SSH_USER} e {$SSH_PASS} estão definidas no template.", file=sys.stderr)
                sys.exit(1)
            
            try:
                port_int = int(port)
            except ValueError:
                print(f"ERRO: Porta SSH inválida: '{port}'. Deve ser um número.", file=sys.stderr)
                sys.exit(1)
                
            collect(ip, port_int, user, password, hostname, debug)
        else:
            print("ERRO: Modo desconhecido. Use launch_discovery ou collect.", file=sys.stderr)
            sys.exit(2)
            
    except TimeoutError as e:
        print(f"ERRO: {str(e)}", file=sys.stderr)
        sys.exit(3)
    finally:
        # Cancela o alarme
        signal.alarm(0)

if __name__ == "__main__":
    main()