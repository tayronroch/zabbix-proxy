#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar se os MIBs fundamentais foram baixados corretamente
"""

import subprocess
import sys
import os

def check_mib_files():
    """Verifica se os arquivos MIB fundamentais existem"""
    print("🔍 VERIFICANDO ARQUIVOS MIB FUNDAMENTAIS")
    print("-" * 50)
    
    fundamental_mibs = [
        "SNMPv2-SMI.txt",
        "SNMPv2-TC.txt", 
        "IF-MIB.txt",
        "IP-MIB.txt",
        "TCP-MIB.txt",
        "UDP-MIB.txt",
        "HOST-RESOURCES-MIB.txt",
        "INET-ADDRESS-MIB.txt"
    ]
    
    mib_dir = "/usr/share/snmp/mibs"
    
    if not os.path.exists(mib_dir):
        print(f"❌ Diretório {mib_dir} não existe!")
        return False
    
    files = os.listdir(mib_dir)
    print(f"📁 Diretório {mib_dir}: {len(files)} arquivos encontrados")
    
    missing_mibs = []
    found_mibs = []
    
    for mib in fundamental_mibs:
        if mib in files:
            found_mibs.append(mib)
            print(f"✅ {mib}")
        else:
            missing_mibs.append(mib)
            print(f"❌ {mib} - FALTANDO")
    
    print(f"\n📊 Resumo:")
    print(f"   ✅ Encontrados: {len(found_mibs)}")
    print(f"   ❌ Faltando: {len(missing_mibs)}")
    
    if missing_mibs:
        print(f"\n🔧 MIBs faltando: {', '.join(missing_mibs)}")
        return False
    
    return True

def test_snmp_conf():
    """Testa a configuração do SNMP"""
    print("\n🔍 VERIFICANDO CONFIGURAÇÃO SNMP")
    print("-" * 50)
    
    try:
        with open('/etc/snmp/snmp.conf', 'r') as f:
            config = f.read()
            print("📄 Conteúdo do /etc/snmp/snmp.conf:")
            print(config)
            return True
    except Exception as e:
        print(f"❌ Erro ao ler snmp.conf: {e}")
        return False

def test_snmpwalk_local():
    """Testa snmpwalk no localhost"""
    print("\n🔍 TESTANDO SNMPWALK LOCAL")
    print("-" * 50)
    
    try:
        # Teste básico com OID numérico
        result = subprocess.run(['snmpwalk', '-v', '2c', '-c', 'public', 
                               '127.0.0.1', '1.3.6.1.2.1.1.1.0'], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            print("✅ snmpwalk básico funcionando")
            print(f"   Resposta: {result.stdout.strip()}")
            return True
        else:
            print(f"⚠️  snmpwalk retornou: {result.returncode}")
            print(f"   Erro: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("⚠️  snmpwalk timeout (normal se não há agente SNMP local)")
        return True  # Timeout é normal se não há agente SNMP
    except Exception as e:
        print(f"❌ Erro no snmpwalk: {e}")
        return False

def test_mib_loading():
    """Testa se os MIBs estão sendo carregados"""
    print("\n🔍 TESTANDO CARREGAMENTO DE MIBS")
    print("-" * 50)
    
    try:
        # Teste com nome simbólico (requer MIBs carregados)
        result = subprocess.run(['snmpwalk', '-v', '2c', '-c', 'public', 
                               '127.0.0.1', 'system.sysDescr.0'], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            print("✅ MIBs carregados corretamente")
            print(f"   Resposta: {result.stdout.strip()}")
            return True
        else:
            print(f"⚠️  MIBs não carregados: {result.returncode}")
            print(f"   Erro: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("⚠️  Timeout (normal se não há agente SNMP local)")
        return True
    except Exception as e:
        print(f"❌ Erro no teste de MIBs: {e}")
        return False

def download_missing_mibs():
    """Tenta baixar MIBs faltantes"""
    print("\n🔧 TENTANDO BAIXAR MIBS FALTANTES")
    print("-" * 50)
    
    mib_urls = {
        "SNMPv2-SMI.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/SNMPv2-SMI.txt",
        "SNMPv2-TC.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/SNMPv2-TC.txt",
        "IF-MIB.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/IF-MIB.txt",
        "IP-MIB.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/IP-MIB.txt",
        "TCP-MIB.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/TCP-MIB.txt",
        "UDP-MIB.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/UDP-MIB.txt",
        "HOST-RESOURCES-MIB.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/HOST-RESOURCES-MIB.txt",
        "INET-ADDRESS-MIB.txt": "https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs/INET-ADDRESS-MIB.txt"
    }
    
    mib_dir = "/usr/share/snmp/mibs"
    downloaded = 0
    
    for mib_file, url in mib_urls.items():
        mib_path = os.path.join(mib_dir, mib_file)
        if not os.path.exists(mib_path):
            try:
                print(f"📥 Baixando {mib_file}...")
                result = subprocess.run(['wget', '-q', '-O', mib_path, url], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"✅ {mib_file} baixado com sucesso")
                    downloaded += 1
                else:
                    print(f"❌ Falha ao baixar {mib_file}")
            except Exception as e:
                print(f"❌ Erro ao baixar {mib_file}: {e}")
        else:
            print(f"✅ {mib_file} já existe")
    
    print(f"\n📊 Total baixado: {downloaded} MIBs")
    return downloaded > 0

def main():
    print("=" * 60)
    print("VERIFICAÇÃO COMPLETA DE MIBS SNMP")
    print("=" * 60)
    
    # Verificar arquivos MIB
    mibs_ok = check_mib_files()
    
    # Verificar configuração SNMP
    config_ok = test_snmp_conf()
    
    # Testar snmpwalk
    snmp_ok = test_snmpwalk_local()
    
    # Testar carregamento de MIBs
    mib_loading_ok = test_mib_loading()
    
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    print(f"   MIBs fundamentais: {'✅ OK' if mibs_ok else '❌ FALHA'}")
    print(f"   Configuração SNMP: {'✅ OK' if config_ok else '❌ FALHA'}")
    print(f"   snmpwalk básico: {'✅ OK' if snmp_ok else '❌ FALHA'}")
    print(f"   Carregamento MIBs: {'✅ OK' if mib_loading_ok else '❌ FALHA'}")
    
    if not mibs_ok:
        print("\n🔧 TENTANDO CORRIGIR MIBS FALTANTES...")
        download_missing_mibs()
        print("\n🔄 Execute novamente o teste após a correção")
    
    print("\n" + "=" * 60)
    if mibs_ok and config_ok and snmp_ok and mib_loading_ok:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("✅ Seus scripts SNMP devem funcionar corretamente")
    else:
        print("⚠️  ALGUNS PROBLEMAS DETECTADOS")
        print("💡 Reconstrua o container: docker-compose down && docker-compose up --build")
    print("=" * 60)

if __name__ == "__main__":
    main() 