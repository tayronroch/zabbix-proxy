#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para testar especificamente os MIBs SNMP
"""

import subprocess
import sys
import os

def test_snmp_conf():
    """Testa a configuração do SNMP"""
    print("🔍 TESTANDO CONFIGURAÇÃO SNMP")
    print("-" * 40)
    
    try:
        with open('/etc/snmp/snmp.conf', 'r') as f:
            config = f.read()
            print("📄 Conteúdo do /etc/snmp/snmp.conf:")
            print(config)
    except Exception as e:
        print(f"❌ Erro ao ler snmp.conf: {e}")

def test_mib_files():
    """Testa se os arquivos MIB existem"""
    print("\n🔍 TESTANDO ARQUIVOS MIB")
    print("-" * 40)
    
    mib_dirs = [
        "/usr/share/snmp/mibs",
        "/usr/share/snmp/mibs/custom"
    ]
    
    for mib_dir in mib_dirs:
        if os.path.exists(mib_dir):
            files = os.listdir(mib_dir)
            print(f"✅ {mib_dir}: {len(files)} arquivos")
            
            # Procurar por MIBs específicos
            if_mib_files = [f for f in files if 'IF-MIB' in f or 'if-mib' in f.lower()]
            if if_mib_files:
                print(f"   ✅ IF-MIB encontrado: {if_mib_files}")
            else:
                print(f"   ❌ IF-MIB NÃO encontrado")
        else:
            print(f"❌ {mib_dir}: diretório não existe")

def test_snmpwalk_basic():
    """Testa snmpwalk básico"""
    print("\n🔍 TESTANDO SNMPWALK BÁSICO")
    print("-" * 40)
    
    try:
        # Teste básico sem MIBs
        result = subprocess.run(['snmpwalk', '-v', '2c', '-c', 'public', 
                               '127.0.0.1', '1.3.6.1.2.1.1.1.0'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ snmpwalk básico funcionando")
            print(f"   Resposta: {result.stdout.strip()}")
        else:
            print(f"⚠️  snmpwalk retornou: {result.returncode}")
            print(f"   Erro: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️  snmpwalk timeout (normal se não há agente SNMP local)")
    except Exception as e:
        print(f"❌ Erro no snmpwalk: {e}")

def test_snmpwalk_with_mibs():
    """Testa snmpwalk com MIBs"""
    print("\n🔍 TESTANDO SNMPWALK COM MIBS")
    print("-" * 40)
    
    try:
        # Teste com MIBs carregados
        result = subprocess.run(['snmpwalk', '-v', '2c', '-c', 'public', 
                               '127.0.0.1', 'system.sysDescr.0'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ snmpwalk com MIBs funcionando")
            print(f"   Resposta: {result.stdout.strip()}")
        else:
            print(f"⚠️  snmpwalk com MIBs retornou: {result.returncode}")
            print(f"   Erro: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️  snmpwalk com MIBs timeout (normal se não há agente SNMP local)")
    except Exception as e:
        print(f"❌ Erro no snmpwalk com MIBs: {e}")

def test_if_mib_specific():
    """Testa especificamente o IF-MIB"""
    print("\n🔍 TESTANDO IF-MIB ESPECÍFICO")
    print("-" * 40)
    
    try:
        # Teste específico do IF-MIB
        result = subprocess.run(['snmpwalk', '-v', '2c', '-c', 'public', 
                               '127.0.0.1', 'ifDescr'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ IF-MIB funcionando corretamente")
            print(f"   Resposta: {result.stdout.strip()}")
        else:
            print(f"⚠️  IF-MIB retornou: {result.returncode}")
            print(f"   Erro: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️  IF-MIB timeout (normal se não há agente SNMP local)")
    except Exception as e:
        print(f"❌ Erro no IF-MIB: {e}")

def main():
    print("=" * 60)
    print("TESTE ESPECÍFICO DE MIBS SNMP")
    print("=" * 60)
    
    # Testar componentes
    test_snmp_conf()
    test_mib_files()
    test_snmpwalk_basic()
    test_snmpwalk_with_mibs()
    test_if_mib_specific()
    
    print("\n" + "=" * 60)
    print("💡 Se os MIBs não estiverem funcionando, reconstrua o container:")
    print("   docker-compose down && docker-compose up --build")
    print("=" * 60)

if __name__ == "__main__":
    main() 