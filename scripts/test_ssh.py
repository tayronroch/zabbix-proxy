#!/usr/bin/env python3
import paramiko
import sys

def test_ssh(ip, port, user, password):
    try:
        print(f"Testando conexão SSH para {ip}:{port} com usuário {user}")
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=int(port), username=user, password=password, 
                   look_for_keys=False, timeout=5)
        
        print("Conexão SSH estabelecida com sucesso!")
        
        # Teste comando simples
        _, stdout, stderr = ssh.exec_command("display version")
        output = stdout.read().decode('utf-8', errors='ignore')
        
        print(f"Comando executado. Output length: {len(output)} chars")
        print("Primeiras 200 chars:")
        print(output[:200])
        
        ssh.close()
        print("Conexão SSH fechada com sucesso!")
        
    except Exception as e:
        print(f"ERRO SSH: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Uso: test_ssh.py <ip> <port> <user> <password>")
        sys.exit(1)
    
    test_ssh(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])