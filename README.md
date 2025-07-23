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
ZABBIX_SERVER_IP=45.161.89.183
```

### 3. Execute o Docker Compose
```bash
docker-compose up -d
```

## Serviços

- **zabbix-proxy**: Proxy Zabbix na porta 10051 com scripts personalizados

## Scripts

Os scripts Python estão incluídos na imagem Docker:
- `huawei_sfp.py` - Monitoramento SFP Huawei
- `huawei_bgp.py` - Monitoramento BGP Huawei  
- `huawei_health.py` - Monitoramento saúde Huawei
- `datacom_sfp.py` - Monitoramento SFP Datacom

## Configuração

- **Servidor Zabbix**: 45.161.89.183:10051
- **Hostname**: corewise-proxy
- **Scripts**: Incluídos em `/usr/lib/zabbix/externalscripts/` 