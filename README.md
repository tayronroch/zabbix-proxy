# Zabbix Proxy - CoreWise

Sistema de proxy Zabbix para monitoramento distribuído de equipamentos de rede.

## Descrição

Este projeto contém a configuração Docker Compose para um proxy Zabbix com scripts personalizados para monitoramento de equipamentos Huawei e Datacom.

## Estrutura do Projeto

- `docker-compose.proxy.yml` - Configuração principal do Docker Compose
- `Dockerfile.zabbix.sender` - Dockerfile para o container Zabbix Sender
- `scripts/` - Scripts Python para monitoramento de equipamentos
  - `huawei_sfp.py` - Monitoramento de portas SFP Huawei
  - `huawei_bgp.py` - Monitoramento de BGP Huawei
  - `huawei_health.py` - Monitoramento de saúde Huawei
  - `datacom_sfp.py` - Monitoramento de portas SFP Datacom

## Deploy

Este projeto é configurado para deploy via Docker Compose. O Coolify irá:

1. Detectar o tipo de aplicação como Docker Compose
2. Fazer build das imagens Docker
3. Iniciar os serviços definidos no docker-compose.proxy.yml

## Variáveis de Ambiente

- `ZABBIX_SERVER_IP` - IP do servidor Zabbix principal (padrão: 192.168.1.100)

## Portas

- `10051` - Porta do Zabbix Proxy

## Serviços

### zabbix-proxy
- Imagem: zabbix/zabbix-proxy-sqlite3:alpine-7.0-latest
- Função: Proxy Zabbix para monitoramento distribuído

### zabbix-sender
- Imagem customizada baseada em zabbix/zabbix-sender:alpine-7.0-latest
- Função: Envio de dados para o Zabbix com scripts personalizados 