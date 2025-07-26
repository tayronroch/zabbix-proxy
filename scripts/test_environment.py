#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para testar se o ambiente está configurado corretamente
"""

import subprocess
import sys
import os

def test_zabbix_sender():
    """Testa se zabbix_sender está disponível"""
    print("🔍 TESTANDO ZABBIX_SENDER")
    print("-" * 40)
    
    try:
        result = subprocess.run(['which', 'zabbix_sender'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ zabbix_sender encontrado em: {result.stdout.strip()}")
            return True
        else:
            print("❌ zabbix_sender NÃO encontrado")
            return False
    except Exception as e:
        print(f"❌ Erro ao procurar zabbix_sender: {e}")
        return False

def test_snmp_mibs():
    """Testa se SNMP MIBs estão configurados"""
    print("\n🔍 TESTANDO SNMP MIBS")
    print("-" * 40)
    
    # Verificar se arquivos MIB existem
    mib_dirs = [
        "/usr/share/snmp/mibs",
        "/usr/share/snmp/mibs/custom"
    ]
    
    for mib_dir in mib_dirs:
        if os.path.exists(mib_dir):
            files = os.listdir(mib_dir)
            print(f"✅ {mib_dir}: {len(files)} arquivos MIB")
        else:
            print(f"❌ {mib_dir}: diretório não existe")
    
    # Testar snmpwalk básico
    try:
        result = subprocess.run(['snmpwalk', '-v', '2c', '-c', 'public', 
                               '127.0.0.1', '1.3.6.1.2.1.1.1.0'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ snmpwalk básico funcionando")
        else:
            print(f"⚠️  snmpwalk retornou: {result.returncode}")
            print(f"   Erro: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️  snmpwalk timeout (normal se não há agente SNMP local)")
    except Exception as e:
        print(f"❌ Erro no snmpwalk: {e}")

def test_scripts():
    """Testa se os scripts estão disponíveis"""
    print("\n🔍 TESTANDO SCRIPTS")
    print("-" * 40)
    
    scripts = [
        "huawei_sfp.py",
        "datacom_sfp.py", 
        "huawei_health.py",
        "huawei_bgp.py"
    ]
    
    for script in scripts:
        script_path = f"/usr/lib/zabbix/externalscripts/{script}"
        if os.path.exists(script_path):
            print(f"✅ {script}")
        else:
            print(f"❌ {script}")

def main():
    print("=" * 60)
    print("TESTE DE AMBIENTE - ZABBIX PROXY")
    print("=" * 60)
    
    # Testar componentes
    zabbix_ok = test_zabbix_sender()
    test_snmp_mibs()
    test_scripts()
    
    print("\n" + "=" * 60)
    if zabbix_ok:
        print("✅ AMBIENTE PRONTO PARA USO")
        print("💡 Execute: python3 /usr/lib/zabbix/externalscripts/test_environment.py")
    else:
        print("❌ PROBLEMAS DETECTADOS")
        print("💡 Reconstrua o container: docker-compose down && docker-compose up --build")
    print("=" * 60)

if __name__ == "__main__":
    main() 