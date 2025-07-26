# 🚀 CoreWise Zabbix Proxy + Scripts SSH

Sistema de proxy para monitoramento distribuído com coleta SSH e SNMP para equipamentos Huawei e Datacom.

## 📋 Características

- **Zabbix Proxy 7.0 LTS** com SQLite
- **Scripts SSH** para Huawei e Datacom
- **Ferramentas de debug** completas
- **Suporte SNMP** com snmpwalk
- **Diagnóstico automático** de conectividade

## 🛠️ Ferramentas Incluídas

### Debug e Rede
- `ping`, `telnet`, `traceroute`, `nmap`
- `net-tools`, `dnsutils`, `netcat`
- `tcpdump`, `strace`, `lsof`

### SNMP
- `snmpwalk`, `snmpget`, `snmpgetnext`
- MIBs configuradas automaticamente
- Suporte a SNMPv2c

### Sistema
- `htop`, `vim`, `less`
- `procps`, `strace`

## 🚀 Instalação

```bash
# Construir e iniciar
docker-compose up -d --build

# Verificar logs
docker-compose logs -f zabbix-proxy
```

## 🔧 Configuração

### Variáveis de Ambiente
```yaml
environment:
  ZBX_HOSTNAME: corewise-proxy
  ZBX_SERVER_HOST: 45.161.89.183
  ZBX_SERVER_PORT: 10051
  ZBX_TIMEOUT: 30
```

### Scripts Disponíveis
- `huawei_sfp.py` - Coleta SFP Huawei
- `datacom_sfp.py` - Coleta SFP Datacom
- `huawei_bgp.py` - Monitoramento BGP Huawei
- `huawei_health.py` - Saúde de equipamentos Huawei

## 🔍 Diagnóstico

### Script de Diagnóstico Completo
```bash
# Entrar no container
docker exec -it corewise-proxy bash

# Executar diagnóstico geral
python3 /usr/lib/zabbix/externalscripts/diagnostic_tools.py

# Executar diagnóstico específico
python3 /usr/lib/zabbix/externalscripts/diagnostic_tools.py 10.255.255.51 22 usuario senha
```

### Testes Manuais

#### Teste de Conectividade
```bash
# Teste TCP
telnet 10.255.255.51 22

# Teste ping
ping 10.255.255.51

# Teste traceroute
traceroute 10.255.255.51
```

#### Teste SSH
```bash
# SSH manual
ssh usuario@10.255.255.51 -p 22

# SSH com paramiko
python3 -c "
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.255.255.51', port=22, username='usuario', password='senha', timeout=30)
print('SSH OK')
ssh.close()
"
```

#### Teste SNMP
```bash
# SNMP básico
snmpwalk -v2c -c public 10.255.255.51 system.sysDescr.0

# SNMP com timeout
snmpwalk -v2c -c public -t 5 -r 1 10.255.255.51 system.sysDescr.0
```

#### Teste de Scripts
```bash
# Teste Huawei
python3 /usr/lib/zabbix/externalscripts/huawei_sfp.py collect 10.255.255.51 22 usuario senha HOSTNAME

# Teste Datacom
python3 /usr/lib/zabbix/externalscripts/datacom_sfp.py collect 10.255.255.51 22 usuario senha HOSTNAME public
```

## 📊 Monitoramento

### Configuração de Itens no Zabbix

#### Para Huawei:
```
Key: huawei_sfp_collect
Command: /usr/lib/zabbix/externalscripts/huawei_sfp.py collect {HOST.CONN} {$SSH_PORT} {$SSH_USER} {$SSH_PASS} {HOST.NAME}
```

#### Para Datacom:
```
Key: datacom_sfp_collect
Command: /usr/lib/zabbix/externalscripts/datacom_sfp.py collect {HOST.CONN} {$SSH_PORT} {$SSH_USER} {$SSH_PASS} {HOST.NAME} {$SNMP_COMMUNITY}
```

### Macros Necessárias
- `{$SSH_USER}` - Usuário SSH
- `{$SSH_PASS}` - Senha SSH
- `{$SSH_PORT}` - Porta SSH (padrão: 22)
- `{$SNMP_COMMUNITY}` - Comunidade SNMP (padrão: public)

## 🐛 Troubleshooting

### Problemas Comuns

#### 1. Timeout SSH
```bash
# Verificar conectividade TCP
python3 -c "import socket; s=socket.socket(); print('OK' if s.connect_ex(('10.255.255.51', 22)) == 0 else 'FAIL'); s.close()"

# Testar com timeout maior
python3 -c "
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.255.255.51', port=22, username='usuario', password='senha', timeout=60)
print('SSH OK')
ssh.close()
"
```

#### 2. Script Incorreto
- **Huawei**: Use `huawei_sfp.py`
- **Datacom**: Use `datacom_sfp.py`

#### 3. Credenciais SSH
```bash
# Testar credenciais
ssh usuario@10.255.255.51 -p 22
```

#### 4. SNMP Não Funciona
```bash
# Verificar se SNMP está habilitado
snmpwalk -v2c -c public 10.255.255.51 system.sysDescr.0

# Testar comunidade diferente
snmpwalk -v2c -c private 10.255.255.51 system.sysDescr.0
```

### Logs do Container
```bash
# Logs do Zabbix Proxy
docker exec corewise-proxy tail -f /var/log/zabbix/zabbix_proxy.log

# Logs do sistema
docker exec corewise-proxy journalctl -f

# Logs do Docker
docker-compose logs -f zabbix-proxy
```

## 📈 Performance

### Recursos Recomendados
- **CPU**: 2 cores
- **RAM**: 1GB mínimo, 2GB recomendado
- **Disco**: 10GB para logs e dados

### Otimizações
- Timeout SSH: 30s
- Cache de comandos habilitado
- Logs rotacionados automaticamente

## 🔒 Segurança

- Credenciais SSH armazenadas em macros
- Comunicação SSH criptografada
- Container isolado em rede própria
- Logs de auditoria habilitados

## 📞 Suporte

Para problemas específicos:
1. Execute o script de diagnóstico
2. Verifique os logs do container
3. Teste conectividade manual
4. Verifique configurações de rede

---

**Desenvolvido para CoreWise - Monitoramento Inteligente** 🚀 