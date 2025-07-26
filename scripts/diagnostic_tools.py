#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico completo para Zabbix Proxy
Testa conectividade, SSH, SNMP e scripts externos
"""

import sys
import socket
import subprocess
import time
import paramiko
import json

def test_tcp_connectivity(host, port, timeout=5):
    """Testa conectividade TCP"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"Erro TCP: {e}")
        return False

def test_ssh_connection(host, port, user, password, timeout=10):
    """Testa conexão SSH"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=user, password=password, timeout=timeout)
        ssh.close()
        return True
    except Exception as e:
        print(f"Erro SSH: {e}")
        return False

def test_snmp_connection(host, community="public", timeout=5):
    """Testa conexão SNMP"""
    try:
        result = subprocess.run([
            "snmpwalk", "-v2c", "-c", community, "-t", str(timeout), 
            "-r", "1", host, "system.sysDescr.0"
        ], capture_output=True, timeout=timeout+2, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Erro SNMP: {e}")
        return False

def test_script_execution(script_path, args):
    """Testa execução de script externo"""
    try:
        result = subprocess.run([script_path] + args, 
                              capture_output=True, timeout=30, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print("=" * 60)
    print("DIAGNÓSTICO COMPLETO - ZABBIX PROXY")
    print("=" * 60)
    
    # Teste 1: Conectividade básica
    print("\n1️⃣ TESTE DE CONECTIVIDADE")
    print("-" * 30)
    
    # Teste DNS
    try:
        ip = socket.gethostbyname("google.com")
        print(f"✅ DNS: OK ({ip})")
    except Exception as e:
        print(f"❌ DNS: FAIL ({e})")
    
    # Teste Internet
    if test_tcp_connectivity("8.8.8.8", 53, 5):
        print("✅ Internet: OK")
    else:
        print("❌ Internet: FAIL")
    
    # Teste 2: Ferramentas instaladas
    print("\n2️⃣ FERRAMENTAS INSTALADAS")
    print("-" * 30)
    
    tools = ["ping", "telnet", "snmpwalk", "traceroute", "nmap"]
    for tool in tools:
        try:
            subprocess.run([tool, "--help"], capture_output=True, timeout=5)
            print(f"✅ {tool}: OK")
        except:
            print(f"❌ {tool}: FAIL")
    
    # Teste 3: Scripts externos
    print("\n3️⃣ SCRIPTS EXTERNOS")
    print("-" * 30)
    
    scripts = [
        "/usr/lib/zabbix/externalscripts/huawei_sfp.py",
        "/usr/lib/zabbix/externalscripts/datacom_sfp.py",
        "/usr/lib/zabbix/externalscripts/huawei_bgp.py",
        "/usr/lib/zabbix/externalscripts/huawei_health.py"
    ]
    
    for script in scripts:
        try:
            with open(script, 'r') as f:
                print(f"✅ {script.split('/')[-1]}: OK")
        except:
            print(f"❌ {script.split('/')[-1]}: FAIL")
    
    # Teste 4: Conectividade específica (se argumentos fornecidos)
    if len(sys.argv) >= 5:
        host = sys.argv[1]
        port = int(sys.argv[2])
        user = sys.argv[3]
        password = sys.argv[4]
        
        print(f"\n4️⃣ TESTE ESPECÍFICO: {host}:{port}")
        print("-" * 30)
        
        # Teste TCP
        if test_tcp_connectivity(host, port, 10):
            print(f"✅ TCP {host}:{port}: OK")
            
            # Teste SSH
            if test_ssh_connection(host, port, user, password, 30):
                print(f"✅ SSH {user}@{host}:{port}: OK")
            else:
                print(f"❌ SSH {user}@{host}:{port}: FAIL")
        else:
            print(f"❌ TCP {host}:{port}: FAIL")
        
        # Teste SNMP
        if test_snmp_connection(host, "public", 5):
            print(f"✅ SNMP {host}: OK")
        else:
            print(f"❌ SNMP {host}: FAIL")
    
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO CONCLUÍDO")
    print("=" * 60)

if __name__ == "__main__":
    main() 