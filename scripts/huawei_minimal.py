#!/usr/bin/env python3
import paramiko
import sys
import time

def minimal_test(ip, port, user, password, hostname):
    try:
        print(f"Conectando em {ip}:{port}...")
        
        # Conexão básica
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=int(port), username=user, password=password, 
                   look_for_keys=False, timeout=10)
        
        print("Conectado! Executando comandos...")
        
        # Teste comandos básicos conhecidos
        comandos_teste = [
            "screen-length disable",
            "terminal length 0", 
            "display interface",
            "show interface",
            "display ip interface brief",
            "show ip interface brief"
        ]
        
        output_completo = ""
        
        for cmd in comandos_teste:
            print(f"Testando comando: {cmd}")
            try:
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
                saida = stdout.read().decode('utf-8', errors='ignore')
                if "Error:" not in saida and "Unrecognized" not in saida:
                    print(f"✅ SUCESSO: {cmd}")
                    output_completo += f"\n=== {cmd} ===\n{saida}\n"
                    if "interface" in cmd.lower():
                        output = saida  # Guarda a saída do comando de interface que funcionou
                        break
                else:
                    print(f"❌ FALHOU: {cmd}")
            except Exception as e:
                print(f"❌ ERRO: {cmd} - {e}")
            time.sleep(0.5)
        
        print(f"\n=== SAÍDA FINAL SELECIONADA ===")
        if 'output' not in locals():
            output = output_completo
        print(f"Saída recebida: {len(output)} chars")
        print("=== SAÍDA COMPLETA ===")
        print(output)
        print("=== FIM SAÍDA ===")
        
        # Procura interfaces
        interfaces = []
        print("\n=== ANÁLISE LINHA POR LINHA ===")
        for line in output.splitlines():
            line = line.strip()
            if line:
                print(f"Linha: '{line}'")
                if "XGE" in line or "100GE" in line or "GigabitEthernet" in line:
                    parts = line.split()
                    print(f"  -> Interface encontrada: {parts}")
                    if len(parts) >= 3 and parts[1] == "up":
                        interfaces.append(parts[0])
                        print(f"  -> Adicionada: {parts[0]}")
        
        print(f"Interfaces encontradas: {interfaces}")
        
        ssh.close()
        
        # Simula envio para Zabbix (sem zabbix_sender real)
        if interfaces:
            print(f"Enviaria discovery para {len(interfaces)} interfaces")
            print("SUCESSO: Teste mínimo funcionou!")
        else:
            print("AVISO: Nenhuma interface encontrada")
            
    except Exception as e:
        print(f"ERRO: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Uso: minimal.py <ip> <port> <user> <password> <hostname>")
        sys.exit(1)
    
    minimal_test(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])