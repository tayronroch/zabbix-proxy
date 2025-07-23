#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Datacom SFP collector - inclui descoberta de alias via SNMP

Usage:
  datacom_sfp.py launch_discovery <host> <ssh_port> <ssh_user> <ssh_pass> <zbx_host> [<snmp_community>]
  datacom_sfp.py collect        <host> <ssh_port> <ssh_user> <ssh_pass> <zbx_host> [<snmp_community>]

Este script:
- SSH para coletar JSON de transceivers
- SNMP para mapear ifDescr -> ifAlias
- Gera payload JSON de discovery (lanes) e discovery (temp/volt)
- Envia via zabbix_sender discovery e valores de temp, voltage, rx, tx, current
- OTIMIZADO: launch_discovery agora executa discovery + coleta em uma unica operacao
"""
import sys
import json
import re
import subprocess
from typing import List, Dict
import paramiko

DEFAULT_SSH_PORT = 22
DEFAULT_SNMP_COMM = 'public'
SNMPWALK = '/usr/bin/snmpwalk'
SNMP_TIMEOUT = 1
SNMP_RETRIES = 1

CMD_LIST = "show interface transceivers | display json"
TRAPPER_LANES = 'gbicDiscovery'
TRAPPER_TEMPVOLT = 'discovery_gbic_temp_volt'

def ssh_run(host: str, port: int, user: str, pwd: str, cmd: str) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, password=pwd, timeout=10)
    _, stdout, _ = client.exec_command(cmd)
    output = stdout.read().decode('utf-8', errors='ignore')
    client.close()
    return output


def build_alias_map(host: str, community: str) -> Dict[str, str]:
    idx_to_descr: Dict[str, str] = {}
    try:
        out = subprocess.check_output([
            SNMPWALK, '-v2c', '-c', community, '-t', str(SNMP_TIMEOUT),
            '-r', str(SNMP_RETRIES), host, 'IF-MIB::ifDescr'
        ], text=True, timeout=SNMP_TIMEOUT+1)
        for line in out.splitlines():
            m = re.match(r"IF-MIB::ifDescr\.(\d+) = STRING: (.+)", line)
            if m:
                idx_to_descr[m.group(1)] = m.group(2)
    except Exception:
        pass
    alias_map: Dict[str, str] = {}
    try:
        out = subprocess.check_output([
            SNMPWALK, '-v2c', '-c', community, '-t', str(SNMP_TIMEOUT),
            '-r', str(SNMP_RETRIES), host, 'IF-MIB::ifAlias'
        ], text=True, timeout=SNMP_TIMEOUT+1)
        for line in out.splitlines():
            m = re.match(r"IF-MIB::ifAlias\.(\d+) = STRING: ?(.*)", line)
            if m and m.group(1) in idx_to_descr:
                alias_map[idx_to_descr[m.group(1)]] = m.group(2)
    except Exception:
        pass
    return alias_map


def is_number(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def build_json_lanes(recs: List[Dict], alias_map: Dict[str, str]) -> str:
    data = []
    for r in recs:
        iftype = r.get('if-type', '')
        base_id = r.get('id', r.get('if-index', ''))
        iface = f"{iftype.replace('-', ' ')} {base_id}"
        alias = alias_map.get(f"{iftype}-{base_id}", '')
        lanes = [lane for lane in range(1, 5) if f"tx{lane}-bias" in r]
        if not lanes and 'tx1-bias' in r:
            lanes = [1]
        for lane in lanes:
            label = f"{iface} - {alias} Ramo {lane}".replace("  ", " ").strip(" -")
            data.append({
                '{#LABEL}': label,
                '{#IFNAME}': iface,
                '{#GBIC_LANE}': str(lane)
            })
    return json.dumps({'data': data}, ensure_ascii=False, separators=(',', ':'))


def build_json_tempvolt(recs: List[Dict], alias_map: Dict[str, str]) -> str:
    data = []
    for r in recs:
        iftype = r.get('if-type', '')
        base_id = r.get('id', r.get('if-index', ''))
        iface = f"{iftype.replace('-', ' ')} {base_id}"
        alias = alias_map.get(f"{iftype}-{base_id}", '')
        for metric_key, _ in [('temp', ''), ('voltage', '')]:
            label = alias or iface
            data.append({
                '{#LABEL}': label,
                '{#IFNAME}': iface,
                '{#METRIC}': metric_key
            })
    return json.dumps({'data': data}, ensure_ascii=False, separators=(',', ':'))


def send_metric_data(recs: List[Dict], zbx: str) -> tuple:
    """Envia os dados de metricas coletadas para o Zabbix"""
    success_count = 0
    error_count = 0
    
    for r in recs:
        iftype = r.get('if-type', '')
        base_id = r.get('id', r.get('if-index', ''))
        iface = f"{iftype.replace('-', ' ')} {base_id}"
        
        # Temperatura
        temp = r.get('temperature', '')
        if is_number(temp):
            result = subprocess.run([
                'zabbix_sender', '-z', '127.0.0.1', '-s', zbx,
                '-k', f'temp[{iface}]', '-o', str(temp)
            ], capture_output=True, check=False)
            if result.returncode == 0:
                success_count += 1
            else:
                error_count += 1
        
        # Voltagem
        volt = r.get('vcc-3v3', '')
        if is_number(volt):
            result = subprocess.run([
                'zabbix_sender', '-z', '127.0.0.1', '-s', zbx,
                '-k', f'voltage[{iface}]', '-o', str(volt)
            ], capture_output=True, check=False)
            if result.returncode == 0:
                success_count += 1
            else:
                error_count += 1
        
        # Lanes (corrente, rx power, tx power)
        lanes = [lane for lane in range(1, 5) if r.get(f"tx{lane}-bias") is not None]
        if not lanes and r.get('tx1-bias') is not None:
            lanes = [1]
        
        for lane in lanes:
            # Corrente
            bias = r.get(f"tx{lane}-bias", '')
            if is_number(bias):
                result = subprocess.run([
                    'zabbix_sender', '-z', '127.0.0.1', '-s', zbx,
                    '-k', f'current[{iface}:{lane}]', '-o', str(bias)
                ], capture_output=True, check=False)
                if result.returncode == 0:
                    success_count += 1
                else:
                    error_count += 1
            
            # RX Power
            rx = r.get(f"rx{lane}-power", '')
            if is_number(rx):
                result = subprocess.run([
                    'zabbix_sender', '-z', '127.0.0.1', '-s', zbx,
                    '-k', f'rxpower[{iface}:{lane}]', '-o', str(rx)
                ], capture_output=True, check=False)
                if result.returncode == 0:
                    success_count += 1
                else:
                    error_count += 1
            
            # TX Power
            tx = r.get(f"tx{lane}-power", '')
            if is_number(tx):
                result = subprocess.run([
                    'zabbix_sender', '-z', '127.0.0.1', '-s', zbx,
                    '-k', f'txpower[{iface}:{lane}]', '-o', str(tx)
                ], capture_output=True, check=False)
                if result.returncode == 0:
                    success_count += 1
                else:
                    error_count += 1
    
    return success_count, error_count


def discovery_and_collect(host: str, port: int, user: str, pwd: str, zbx: str, community: str) -> None:
    """Executa discovery e coleta de dados em uma unica operacao otimizada"""
    try:
        # Conecta uma unica vez via SSH e obtem os dados
        raw = ssh_run(host, port, user, pwd, CMD_LIST)
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            print("ERRO: Falha ao processar dados JSON do equipamento", file=sys.stderr)
            return
        
        recs = obj.get('data', {}).get('dmos-base:status', {}).get('interface', {}).get('dmos-transceivers:transceivers', [])
        if not recs:
            print("ERRO: Nenhum transceiver encontrado no equipamento", file=sys.stderr)
            return
        
        # Obtem o mapeamento de alias uma unica vez via SNMP
        alias_map = build_alias_map(host, community)
        
        # Gera e envia os payloads de discovery
        payload_lanes = build_json_lanes(recs, alias_map)
        payload_tempvolt = build_json_tempvolt(recs, alias_map)
        host_q = f'"{zbx}"'
        lines = [
            f"{host_q} {TRAPPER_LANES} {payload_lanes}",
            f"{host_q} {TRAPPER_TEMPVOLT} {payload_tempvolt}"
        ]
        
        # Envia discovery sem verbosidade
        discovery_result = subprocess.run([
            'zabbix_sender', '-z', '127.0.0.1', '-i', '-'
        ], input="\n".join(lines).encode(), capture_output=True, check=False)
        
        # Envia os dados de metricas coletadas
        success_count, error_count = send_metric_data(recs, zbx)
        
        # Resultado final
        if discovery_result.returncode == 0 and error_count == 0:
            print("SUCESSO: Discovery e coleta executados com sucesso!")
            print(f"Enviados: {success_count} metricas processadas")
        elif discovery_result.returncode != 0:
            print("ERRO: Falha no envio do discovery para o Zabbix")
        else:
            print(f"PARCIAL: Discovery OK, mas {error_count} metricas falharam de {success_count + error_count} total")
            
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)


def collect(host: str, port: int, user: str, pwd: str, zbx: str, community: str) -> None:
    """Mantido para compatibilidade - executa apenas coleta de dados"""
    try:
        raw = ssh_run(host, port, user, pwd, CMD_LIST)
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            print("ERRO: Falha ao processar dados JSON do equipamento", file=sys.stderr)
            return
        recs = obj.get('data', {}).get('dmos-base:status', {}).get('interface', {}).get('dmos-transceivers:transceivers', [])
        if not recs:
            print("ERRO: Nenhum transceiver encontrado no equipamento", file=sys.stderr)
            return
        
        success_count, error_count = send_metric_data(recs, zbx)
        
        if error_count == 0:
            print("SUCESSO: Coleta executada com sucesso!")
            print(f"Enviados: {success_count} metricas processadas")
        else:
            print(f"PARCIAL: {error_count} metricas falharam de {success_count + error_count} total")
            
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)

if __name__ == '__main__':
    if len(sys.argv) < 7:
        print("Usage: datacom_sfp.py <launch_discovery|collect> <host> <ssh_port> <ssh_user> <ssh_pass> <zbx_host> [<snmp_community>]", file=sys.stderr)
        sys.exit(1)
    act = sys.argv[1]
    host_str = sys.argv[2]
    port_str = sys.argv[3]
    usr = sys.argv[4]
    pwd = sys.argv[5]
    zbx_host = sys.argv[6]
    snmp_comm = sys.argv[7] if len(sys.argv) > 7 else DEFAULT_SNMP_COMM
    try:
        port = int(port_str)
    except ValueError:
        port = DEFAULT_SSH_PORT
    if act == 'launch_discovery':
        discovery_and_collect(host_str, port, usr, pwd, zbx_host, snmp_comm)
    elif act == 'collect':
        collect(host_str, port, usr, pwd, zbx_host, snmp_comm)
    else:
        print("Unknown action", file=sys.stderr)
        sys.exit(2)