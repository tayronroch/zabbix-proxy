# Zabbix Proxy - CoreWise

Sistema de proxy Zabbix para monitoramento distribuído.

## Como Usar

### 1. Clone o repositório
```bash
git clone <seu-repositorio>
cd zabbix-proxy
```

### 2. Configure as variáveis de ambiente
Crie um arquivo `.env` com:
```
ZABBIX_SERVER_IP=192.168.1.100
```

### 3. Execute o Docker
```bash
docker build -t zabbix-proxy .
docker run -p 10051:10051 --env ZBX_HOSTNAME=corewise-proxy --env ZBX_SERVER_HOST=192.168.1.100 --env ZBX_SERVER_PORT=10051 zabbix-proxy
```

## Serviços

- **zabbix-proxy**: Proxy Zabbix na porta 10051 com scripts personalizados

## Scripts

Os scripts Python estão na pasta `scripts/`:
- `huawei_sfp.py` - Monitoramento SFP Huawei
- `huawei_bgp.py` - Monitoramento BGP Huawei  
- `huawei_health.py` - Monitoramento saúde Huawei
- `datacom_sfp.py` - Monitoramento SFP Datacom 