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
    mapping = {
        "Idle": 1,
        "Connect": 2,
        "Active": 3,
        "OpenSent": 4,
        "OpenConfirm": 5,
        "Established": 6
    }
    return mapping.get(state_str, 0)

def launch_discovery_original(host, port, user, password, zabbix_host):
    """Funcao original de discovery que funcionava - com cache otimizado"""
    try:
        cmds_routes = [
            ("display ipv6 routing-table statistics", "ipv6"),
            ("display bgp ipv6 routing-table statistics", "bgp_ipv6"),
            ("display ip routing-table statistics", "ipv4"),
            ("display bgp routing-table statistics", "bgp_ipv4")
        ]
        values = {}
        for cmd, tag in cmds_routes:
            output = run_ssh_command(host, port, user, password, cmd)
            if tag == "ipv6":
                m = re.search(r"Summary Prefixes\s*:\s*(\d+)", output)
                if m: values["hwIPv6RibRoutes"] = int(m.group(1))
            elif tag == "bgp_ipv6":
                m = re.search(r"Total Number of Routes:\s*(\d+)", output)
                if m: values["hwIPv6FibRoutes"] = int(m.group(1))
            elif tag == "ipv4":
                m = re.search(r"Summary Prefixes\s*:\s*(\d+)", output)
                if m: values["hwIPv4RibRoutes"] = int(m.group(1))
            elif tag == "bgp_ipv4":
                m = re.search(r"Total Number of Routes:\s*(\d+)", output)
                if m: values["hwIPv4FibRoutes"] = int(m.group(1))
        
        values["hwIPv4v6RibRoutes"] = values.get("hwIPv4RibRoutes",0) + values.get("hwIPv6RibRoutes",0)
        values["hwIPv4v6FibRoutes"] = values.get("hwIPv4FibRoutes",0) + values.get("hwIPv6FibRoutes",0)
        
        for key, val in values.items():
            send_to_zabbix(zabbix_host, key, val)

        all_peers = []
        for cmd in ["display bgp ipv6 peer verbose | no-more", "display bgp peer verbose | no-more"]:
            output = run_ssh_command(host, port, user, password, cmd)
            all_peers += extract_peers(output)
        lld_json = json.dumps({"data": all_peers}, ensure_ascii=False)
        send_to_zabbix(zabbix_host, "bgpSessions", lld_json, lld=True)
        
    except Exception as e:
        raise Exception(f"Erro em discovery: {str(e)}")

def collect_original(host, port, user, password, zabbix_host):
    """Funcao original de collect que funcionava - com cache otimizado"""
    try:
        # Usa cache - comandos BGP ja executados no discovery
        peers_discovered = []
        for cmd in ["display bgp ipv6 peer verbose | no-more", "display bgp peer verbose | no-more"]:
            output = run_ssh_command(host, port, user, password, cmd)  # Cache evita re-execucao
            peers_discovered += extract_peers(output)
        peer_set = set((p["{#DESCRIPTION}"], p["{#PEER}"]) for p in peers_discovered)

        for cmd in ["display bgp ipv6 peer verbose | no-more", "display bgp peer verbose | no-more"]:
            output = run_ssh_command(host, port, user, password, cmd)  # Cache evita re-execucao
            peer_blocks = re.split(r"\n\s*BGP Peer is ", output)
            for block in peer_blocks[1:]:
                m = re.match(r"([^\s,]+)", block)
                if not m:
                    continue
                peer_ip = m.group(1)
                desc_m = re.search(r'Peer\'s description: "([^"]+)"', block)
                if not desc_m:
                    continue
                description = desc_m.group(1)
                if (description, peer_ip) not in peer_set:
                    continue

                state = re.search(r"BGP current state:\s*([^\s,]+)", block)
                state_val = state.group(1) if state else ""

                uptime = re.search(r"Up for ([^,]+)", block)
                uptime_val = uptime.group(1) if uptime else ""

                recv_routes = re.search(r"Received total routes:\s*(\d+)", block)
                recv_routes_val = recv_routes.group(1) if recv_routes else "0"

                adv_routes = re.search(r"Advertised total routes:\s*(\d+)", block)
                adv_routes_val = adv_routes.group(1) if adv_routes else "0"

                uptime_hours = parse_uptime_to_hours(uptime_val) if uptime_val else 0
                state_num = bgp_state_to_num(state_val) if state_val else 0

                send_to_zabbix(zabbix_host, f'bgpAdvRoutes["{description}",{peer_ip}]', adv_routes_val, use_shell_quotes=True)
                send_to_zabbix(zabbix_host, f'BGPpeerRouter["{description}",{peer_ip}]', recv_routes_val, use_shell_quotes=True)
                send_to_zabbix(zabbix_host, f'hwBgpPeerFsmEstablishedTime["{description}",{peer_ip}]', uptime_hours, use_shell_quotes=True)
                send_to_zabbix(zabbix_host, f'hwBgpPeerState["{description}",{peer_ip}]', state_num, use_shell_quotes=True)
                
    except Exception as e:
        raise Exception(f"Erro em collect: {str(e)}")

def launch_discovery_and_collect(host, port, user, password, zabbix_host):
    """Executa discovery e coleta - VERSAO ROBUSTA"""
    try:
        # Limpa cache
        clear_cache()
        print("Iniciando discovery...")
        
        # Executa discovery
        launch_discovery_original(host, port, user, password, zabbix_host)
        print("Discovery concluido. Iniciando coleta...")
        
        # Executa collect (reutiliza comandos do cache)
        collect_original(host, port, user, password, zabbix_host)
        
        print("SUCESSO: Discovery e coleta executados com sucesso!")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
    finally:
        clear_cache()

def collect(host, port, user, password, zabbix_host):
    """Funcao de collect para compatibilidade"""
    try:
        collect_original(host, port, user, password, zabbix_host)
        print("SUCESSO: Coleta executada com sucesso!")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("Usage: huawei_bgp.py <launch_discovery|collect> <host> <port> <user> <password> <zabbix_host>", file=sys.stderr)
        sys.exit(1)
    mode, host, port, user, password, zabbix_host = sys.argv[1:7]
    if mode == "launch_discovery":
        launch_discovery_and_collect(host, port, user, password, zabbix_host)
    elif mode == "collect":
        collect(host, port, user, password, zabbix_host)
    else:
        print("ERRO: Modo desconhecido. Use launch_discovery ou collect.", file=sys.stderr)
        sys.exit(2)
        