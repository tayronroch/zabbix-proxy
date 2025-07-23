# Zabbix Proxy + Scripts SSH - CoreWise

Sistema de proxy Zabbix com container de scripts SSH para monitoramento distribuído.

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

- **zabbix-proxy**: Proxy Zabbix com SQLite na porta 10051
- **zabbix-scripts**: Container com scripts SSH personalizados + zabbix-sender

## Scripts

Os scripts Python estão disponíveis em:
- **Scripts**: `/opt/corewise/scripts/` (container separado)

Scripts incluídos:
- `huawei_sfp.py` - Monitoramento SFP Huawei
- `huawei_bgp.py` - Monitoramento BGP Huawei  
- `huawei_health.py` - Monitoramento saúde Huawei
- `datacom_sfp.py` - Monitoramento SFP Datacom

## Configuração

- **Servidor Zabbix**: 45.161.89.183:10051
- **Proxy Hostname**: corewise-proxy
- **Database**: SQLite (incluído no proxy)
- **Scripts SSH**: Container separado com zabbix-sender

## Estrutura

```
├── docker-compose.yaml     # Docker Compose com Proxy + Scripts
├── Dockerfile.proxy        # Build do Zabbix Proxy (SQLite)
├── Dockerfile.sender       # Build do Container de Scripts SSH
├── scripts/                # Scripts Python SSH
│   ├── huawei_sfp.py
│   ├── huawei_bgp.py
│   ├── huawei_health.py
│   └── datacom_sfp.py
└── README.md              # Documentação
``` 