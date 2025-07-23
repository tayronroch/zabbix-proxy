#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Huawei BGP collector - otimizado para executar discovery e coleta em uma unica operacao

Usage:
  huawei_bgp.py launch_discovery <host> <port> <user> <password> <zabbix_host>
  huawei_bgp.py collect <host> <port> <user> <password> <zabbix_host>

OTIMIZADO: launch_discovery agora executa discovery + coleta em uma unica operacao
"""

import paramiko
import sys
import re
import json
import subprocess

# Cache simples para evitar comandos duplicados (mais seguro que conexao global)
command_cache = {}

def run_ssh_command(host, port, user, password, command):
    """Executa comando SSH com cache simples"""
    global command_cache
    
    # Verifica cache primeiro
    cache_key = f"{host}:{port}:{command}"
    if cache_key in command_cache:
        return command_cache[cache_key]
    
    # Executa comando com conexao individual (mais estavel)
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=int(port), username=user, password=password, 
                   look_for_keys=False, allow_agent=False, timeout=30)
        stdin, stdout, stderr = ssh.exec_command(command, timeout=60)
        output = stdout.read().decode(errors='ignore')
        ssh.close()
        
        # Armazena no cache para reutilizacao
        command_cache[cache_key] = output
        return output
        
    except Exception as e:
        raise Exception(f"Erro SSH em '{command}': {str(e)}")

def clear_cache():
    """Limpa cache de comandos"""
    global command_cache
    command_cache.clear()

def send_to_zabbix(zabbix_host, key, value, lld=False, use_shell_quotes=False):
    try:
        if use_shell_quotes:
            if lld:
                cmd = f'zabbix_sender -z 127.0.0.1 -s "{zabbix_host}" -k {key} -o \'{value}\''
            else:
                cmd = f'zabbix_sender -z 127.0.0.1 -s "{zabbix_host}" -k {key} -o {value}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        else:
            cmd = ["zabbix_sender", "-z", "127.0.0.1", "-s", zabbix_host, "-k", key]
            if lld:
                cmd += ["-o", value]
            else:
                cmd += ["-o", str(value)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception as e:
        raise Exception(f"Erro Zabbix sender: {str(e)}")

def extract_peers(output):
    peers = []
    peer_blocks = re.split(r"\n\s*BGP Peer is ", output)
    for block in peer_blocks[1:]:
        m = re.match(r"([^\s,]+)", block)
        if not m:
            continue
        peer_ip = m.group(1)
        desc = ""
        desc_m = re.search(r'Peer\'s description: "([^"]+)"', block)
        if desc_m:
            desc = desc_m.group(1)
        peers.append({
            "{#DESCRIPTION}": desc,
            "{#PEER}": peer_ip
        })
    return peers

def parse_uptime_to_hours(uptime_str):
    days = hours = mins = secs = 0
    m = re.search(r"(\d+)d", uptime_str)
    if m: days = int(m.group(1))
    m = re.search(r"(\d+)h", uptime_str)
    if m: hours = int(m.group(1))
    m = re.search(r"(\d+)m", uptime_str)
    if m: mins = int(m.group(1))
    m = re.search(r"(\d+)s", uptime_str)
    if m: secs = int(m.group(1))
    total_hours = days*24 + hours + (mins/60) + (secs/3600)
    return round(total_hours, 2)

def bgp_state_to_num(state_str):
    state_map = {
        "Idle": 0,
        "Connect": 1,
        "Active": 2,
        "OpenSent": 3,
        "OpenConfirm": 4,
        "Established": 5
    }
    return state_map.get(state_str, -1)

def launch_discovery_original(host, port, user, password, zabbix_host):
    """Discovery original - mantido para compatibilidade"""
    try:
        output = run_ssh_command(host, port, user, password, "display bgp peer")
        peers = extract_peers(output)
        
        if not peers:
            print(f"❌ Nenhum peer BGP encontrado em {host}")
            return False
        
        # Cria discovery data
        discovery_data = {"data": peers}
        payload = json.dumps(discovery_data, separators=(',', ':'))
        
        # Envia discovery
        send_to_zabbix(zabbix_host, "huawei.bgp.discovery", payload, lld=True)
        print(f"✅ Discovery enviado para {zabbix_host}: {len(peers)} peers")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def collect_original(host, port, user, password, zabbix_host):
    """Coleta original - versao final para producao"""
    try:
        output = run_ssh_command(host, port, user, password, "display bgp peer")
        peers = extract_peers(output)
        
        if not peers:
            print(f"❌ Nenhum peer BGP encontrado em {host}")
            return False
        
        success_count = 0
        error_count = 0
        
        for peer in peers:
            peer_ip = peer["{#PEER}"]
            desc = peer["{#DESCRIPTION}"]
            
            try:
                # Obtem detalhes do peer
                peer_output = run_ssh_command(host, port, user, password, f"display bgp peer {peer_ip}")
                
                # Parse estado
                state_match = re.search(r"BGP current state\s*:\s*(\w+)", peer_output)
                if state_match:
                    state = state_match.group(1)
                    state_num = bgp_state_to_num(state)
                    if send_to_zabbix(zabbix_host, f"huawei.bgp.state[{peer_ip}]", state_num):
                        success_count += 1
                    else:
                        error_count += 1
                
                # Parse uptime
                uptime_match = re.search(r"BGP current state\s*:\s*\w+\s*,\s*Up for\s*([^,\n]+)", peer_output)
                if uptime_match:
                    uptime_str = uptime_match.group(1).strip()
                    uptime_hours = parse_uptime_to_hours(uptime_str)
                    if send_to_zabbix(zabbix_host, f"huawei.bgp.uptime[{peer_ip}]", uptime_hours):
                        success_count += 1
                    else:
                        error_count += 1
                
                # Parse prefix count
                prefix_match = re.search(r"Received routes\s*:\s*(\d+)", peer_output)
                if prefix_match:
                    prefix_count = int(prefix_match.group(1))
                    if send_to_zabbix(zabbix_host, f"huawei.bgp.prefixes[{peer_ip}]", prefix_count):
                        success_count += 1
                    else:
                        error_count += 1
                        
            except Exception as e:
                error_count += 1
                print(f"❌ Erro ao processar peer {peer_ip}: {str(e)}")
        
        print(f"✅ {success_count} metricas enviadas, {error_count} erros")
        return success_count > 0
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def launch_discovery_and_collect(host, port, user, password, zabbix_host):
    """OTIMIZADO: Executa discovery + coleta em uma unica operacao"""
    try:
        print(f"🚀 Iniciando discovery + coleta BGP para {zabbix_host} ({host})")
        
        # Obtem dados uma unica vez
        output = run_ssh_command(host, port, user, password, "display bgp peer")
        peers = extract_peers(output)
        
        if not peers:
            print(f"❌ Nenhum peer BGP encontrado em {host}")
            return False
        
        # Discovery
        discovery_data = {"data": peers}
        payload = json.dumps(discovery_data, separators=(',', ':'))
        
        # Envia discovery
        try:
            send_to_zabbix(zabbix_host, "huawei.bgp.discovery", payload, lld=True)
            discovery_success = True
        except Exception as e:
            print(f"❌ Erro no discovery: {str(e)}")
            discovery_success = False
        
        # Coleta
        success_count = 0
        error_count = 0
        
        for peer in peers:
            peer_ip = peer["{#PEER}"]
            desc = peer["{#DESCRIPTION}"]
            
            try:
                # Obtem detalhes do peer
                peer_output = run_ssh_command(host, port, user, password, f"display bgp peer {peer_ip}")
                
                # Parse estado
                state_match = re.search(r"BGP current state\s*:\s*(\w+)", peer_output)
                if state_match:
                    state = state_match.group(1)
                    state_num = bgp_state_to_num(state)
                    if send_to_zabbix(zabbix_host, f"huawei.bgp.state[{peer_ip}]", state_num):
                        success_count += 1
                    else:
                        error_count += 1
                
                # Parse uptime
                uptime_match = re.search(r"BGP current state\s*:\s*\w+\s*,\s*Up for\s*([^,\n]+)", peer_output)
                if uptime_match:
                    uptime_str = uptime_match.group(1).strip()
                    uptime_hours = parse_uptime_to_hours(uptime_str)
                    if send_to_zabbix(zabbix_host, f"huawei.bgp.uptime[{peer_ip}]", uptime_hours):
                        success_count += 1
                    else:
                        error_count += 1
                
                # Parse prefix count
                prefix_match = re.search(r"Received routes\s*:\s*(\d+)", peer_output)
                if prefix_match:
                    prefix_count = int(prefix_match.group(1))
                    if send_to_zabbix(zabbix_host, f"huawei.bgp.prefixes[{peer_ip}]", prefix_count):
                        success_count += 1
                    else:
                        error_count += 1
                        
            except Exception as e:
                error_count += 1
                print(f"❌ Erro ao processar peer {peer_ip}: {str(e)}")
        
        # Resultado final
        if discovery_success and error_count == 0:
            print(f"✅ SUCCESS: Discovery + {success_count} metricas enviadas")
            return True
        elif not discovery_success:
            print(f"❌ ERROR: Falha no discovery")
            return False
        else:
            print(f"⚠️ PARCIAL: Discovery OK, {error_count} metricas falharam")
            return success_count > 0
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def collect(host, port, user, password, zabbix_host):
    """Mantido para compatibilidade - executa apenas coleta"""
    return collect_original(host, port, user, password, zabbix_host)

def main():
    if len(sys.argv) < 6:
        print("Usage: huawei_bgp.py <launch_discovery|collect> <host> <port> <user> <password> <zabbix_host>")
        sys.exit(1)
    
    action = sys.argv[1]
    host = sys.argv[2]
    port = int(sys.argv[3])
    user = sys.argv[4]
    password = sys.argv[5]
    zabbix_host = sys.argv[6]
    
    if action == "launch_discovery":
        launch_discovery_and_collect(host, port, user, password, zabbix_host)
    elif action == "collect":
        collect(host, port, user, password, zabbix_host)
    else:
        print("Unknown action")
        sys.exit(1)

if __name__ == "__main__":
    main()
        