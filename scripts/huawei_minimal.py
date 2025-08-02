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
        
        # Comando único combinado
        cmd = "screen-length 0 temporary\ndisplay interface description"
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        
        # Lê saída
        output = stdout.read().decode('utf-8', errors='ignore')
        print(f"Saída recebida: {len(output)} chars")
        
        # Procura interfaces
        interfaces = []
        for line in output.splitlines():
            if "XGE" in line or "100GE" in line:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "up":
                    interfaces.append(parts[0])
        
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