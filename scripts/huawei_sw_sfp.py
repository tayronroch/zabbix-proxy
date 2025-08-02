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

# Cache simples para evitar comandos duplicados
command_cache = {}

def ssh_command_with_cache(ip, port, user, password, command, debug=False):
    """Executa comando SSH com cache - OTIMIZADO PARA PRODUCAO"""
    global command_cache
    
    # Verifica cache primeiro
    cache_key = f"{ip}:{port}:{command}"
    if cache_key in command_cache:
        if debug:
            print(f"DEBUG: Cache hit para '{command}'")
        return command_cache[cache_key]
    
    # Executa comando com timeouts otimizados
    try:
        if debug:
            print(f"DEBUG: Executando comando SSH: '{command}'")
            
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=port, username=user, password=password, 
                   look_for_keys=False, timeout=15)
        
        # Configura screen-length 0 e executa comando em uma única sessão
        full_command = f"screen-length 0 temporary\n{command}"
        _, stdout, _ = ssh.exec_command(full_command, timeout=30)
        raw = stdout.read()
        try:
            output = raw.decode("utf-8")
        except UnicodeDecodeError:
            output = raw.decode("latin1")
        
        ssh.close()
        
        if debug:
            print(f"DEBUG: Comando executado. Output size: {len(output)} chars")
            print(f"DEBUG: Primeiras 500 chars: {output[:500]}")
        
        # Armazena no cache
        command_cache[cache_key] = output
        return output
        
    except Exception as e:
        if debug:
            print(f"DEBUG: Erro SSH: {str(e)}")
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

def get_interfaces(ip, port, user, password):
    """Obtem interfaces com descrição"""
    output = ssh_command_with_cache(ip, port, user, password, "display interface description")
    
    interfaces = {}
    for line in output.splitlines():
        # Match interface lines
        m = re.match(r"(\S+)\s+\S+\s+\S+\s+(.*)", line.strip())
        if m:
            ifname = m.group(1)
            ifalias = m.group(2).strip()
            # Inclui interfaces 10GE, 25GE, 40GE, 100GE, etc
            if any(x in ifname for x in ["GE", "Ethernet"]) and ifalias:
                interfaces[ifname] = ifalias
    
    return interfaces

def get_transceiver_info(ip, port, user, password, interface, debug=False):
    """Obtem informações detalhadas do transceiver para uma interface específica"""
    output = ssh_command_with_cache(ip, port, user, password, f"display transceiver verbose interface {interface}", debug)
    
    transceiver_data = {}
    
    # Parse temperatura - formato: "Temperature(°C)             :41.00"
    temp_match = re.search(r"Temperature\(.*?\)\s*:\s*([+-]?\d+\.?\d*)", output)
    if temp_match:
        transceiver_data["temperature"] = temp_match.group(1)
        if debug:
            print(f"DEBUG: {interface} temperature: {temp_match.group(1)}°C")
    
    # Parse voltagem - formato: "Voltage(V)                    :3.30"
    volt_match = re.search(r"Voltage\(V\)\s*:\s*(\d+\.?\d*)", output)
    if volt_match:
        transceiver_data["voltage"] = volt_match.group(1)
        if debug:
            print(f"DEBUG: {interface} voltage: {volt_match.group(1)}V")
    
    # Parse bias current - pode ser simples ou multi-lane
    if "100GE" in interface:
        # 100GE com múltiplas lanes: "Bias Current(mA)              :66.69|69.77(Lane0|Lane1)"
        bias_match = re.search(r"Bias Current\(mA\)\s*:\s*([\d\.\|]+)\(Lane", output)
        if bias_match:
            bias_values = bias_match.group(1).split('|')
            for i, value in enumerate(bias_values):
                transceiver_data[f"bias_current_lane_{i}"] = value.strip()
                if debug:
                    print(f"DEBUG: {interface} bias current lane {i}: {value}mA")
    else:
        # 10GE simples: "Bias Current(mA)              :7.23"
        bias_match = re.search(r"Bias Current\(mA\)\s*:\s*(\d+\.?\d*)", output)
        if bias_match:
            transceiver_data["bias_current"] = bias_match.group(1)
    
    # Parse TX power - pode ser simples ou multi-lane
    if "100GE" in interface:
        # 100GE: "TX Power(dBM)                 :1.38|1.49(Lane0|Lane1)"
        tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([\d\.\-\|]+)\(Lane", output)
        if tx_match:
            tx_values = tx_match.group(1).split('|')
            for i, value in enumerate(tx_values):
                transceiver_data[f"tx_power_lane_{i}"] = value.strip()
                if debug:
                    print(f"DEBUG: {interface} TX power lane {i}: {value}dBm")
    else:
        # 10GE: "TX Power(dBM)                 :-2.26"
        tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([+-]?\d+\.?\d*)", output)
        if tx_match:
            transceiver_data["tx_power"] = tx_match.group(1)
    
    # Parse RX power - pode ser simples ou multi-lane
    if "100GE" in interface:
        # 100GE: "RX Power(dBM)                 :-0.53|-1.21(Lane0|Lane1)"
        rx_match = re.search(r"RX Power\(dBM\)\s*:\s*([\d\.\-\|]+)\(Lane", output)
        if rx_match:
            rx_values = rx_match.group(1).split('|')
            for i, value in enumerate(rx_values):
                transceiver_data[f"rx_power_lane_{i}"] = value.strip()
                if debug:
                    print(f"DEBUG: {interface} RX power lane {i}: {value}dBm")
    else:
        # 10GE: "RX Power(dBM)                 :-2.77"
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
    
    # Discovery de interfaces SFP
    discovery_sfp = []
    for ifname, ifalias in interfaces.items():
        discovery_sfp.append({
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
    
    # Envia discoveries
    subprocess.run([
        "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_switch_sfp", 
        "-o", json.dumps({"data": discovery_sfp})
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
    """Executa discovery e coleta OTIMIZADO - versao final para producao"""
    try:
        start_time = time.time()
        
        if debug:
            print("DEBUG: Iniciando discovery e coleta...")
        
        # Limpa cache
        clear_cache()
        
        # Executa discovery
        launch_discovery_original(ip, port, user, password, hostname)
        
        # Executa collect otimizado
        success_count, error_count, _ = collect_original_optimized(ip, port, user, password, hostname, debug)
        
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
        launch_discovery_and_collect(ip, int(port), user, password, hostname, debug)
    elif mode == "collect":
        if len(sys.argv) < 7:
            print("Uso: huawei_sw_sfp.py collect <ip> <port> <user> <password> <hostname> [debug]", file=sys.stderr)
            sys.exit(1)
        _, _, ip, port, user, password, hostname = sys.argv[:7]
        collect(ip, int(port), user, password, hostname, debug)
    else:
        print("ERRO: Modo desconhecido. Use launch_discovery ou collect.", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()