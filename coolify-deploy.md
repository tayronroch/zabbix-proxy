# Deploy do Zabbix Proxy via Coolify - Configuração Automatizada

## Preparação para Deploy

### 1. Configurações no Coolify

1. **Criar novo projeto** no Coolify
2. **Tipo de deploy**: Docker Compose
3. **Repositório**: Conectar este repositório
4. **Branch**: main

### 2. Variáveis de Ambiente no Coolify

Configure as seguintes variáveis de ambiente no painel do Coolify:

```bash
# Configurações básicas (OBRIGATÓRIAS)
ZBX_HOSTNAME=corewise-proxy
ZBX_SERVER_HOST=45.161.89.183
ZBX_SERVER_PORT=10051

# Configurações otimizadas para 15k+ itens com 300GB+ disponível
ZBX_LOCAL_BUFFER=8760       # 1 ano de dados locais
ZBX_OFFLINE_BUFFER=17520    # 2 anos de dados offline
ZBX_HISTORY_CACHE_SIZE=256M
ZBX_TREND_CACHE_SIZE=128M
ZBX_HISTORY_INDEX_CACHE_SIZE=64M

# Configurações de retenção para grandes volumes
ZBX_DB_MAX_SIZE_GB=280                    # Limite de 280GB
ZBX_HISTORY_STORAGE_DAYS=365             # Histórico por 1 ano
ZBX_TRENDS_STORAGE_DAYS=1825             # Trends por 5 anos
ZBX_MAX_HOUSEKEEPER_DELETE=100000        # Limpeza mais agressiva

# Processos otimizados
ZBX_START_POLLERS=50
ZBX_START_PINGPOLLERS=20
ZBX_START_TRAPPERS=20
ZBX_START_DISCOVERERS=10

# Recursos do container
CONTAINER_MEMORY_LIMIT=8G
CONTAINER_MEMORY_RESERVATION=4G
CONTAINER_CPU_LIMIT=6.0
CONTAINER_CPU_RESERVATION=3.0
```

### 3. Configurações de Recursos Recomendadas

Para um servidor com 15k+ itens, recomenda-se:

- **CPU**: Mínimo 4 cores (6 cores recomendado)
- **Memória**: Mínimo 8GB (12GB recomendado)
- **Disco**: SSD com pelo menos 50GB livres
- **Rede**: Conexão estável com o Zabbix Server

### 4. Monitoramento e Logs

Após Deploy, monitore:

```bash
# Verificar logs do container
docker logs -f corewise-proxy

# Verificar uso de recursos
docker stats corewise-proxy

# Verificar conectividade com o servidor
docker exec corewise-proxy zabbix_get -s ZABBIX_SERVER_IP -k system.uptime
```

### 5. Troubleshooting Comum

#### Container reinicializando constantemente:
- Verifique se a memória alocada é suficiente (mínimo 8GB)
- Confirme conectividade com o Zabbix Server
- Analise logs para identificar erros específicos

#### Performance baixa:
- Ajuste os valores de cache no .env
- Aumente o número de pollers se necessário
- Verifique se o disco não está com I/O elevado

#### Itens não sendo coletados:
- Verifique se o proxy está registrado no Zabbix Server
- Confirme se os hosts estão atribuídos ao proxy correto
- Teste conectividade SNMP/SSH manualmente

### 6. Scripts de Verificação

O container inclui scripts para verificar:
- Conectividade de rede
- Status das MIBs SNMP
- Funcionamento do zabbix_sender
- Scripts externos disponíveis

### 7. Monitoramento Automático do Banco

O sistema inclui um script automático (`db_monitor.py`) que:
- **Monitora o tamanho do banco** (máximo 280GB)
- **Remove dados antigos** automaticamente:
  - Histórico: 1 ano (365 dias)
  - Trends: 5 anos (1825 dias)
- **Executa VACUUM** quando necessário
- **Roda diariamente às 2h** via cron

### 8. Backup e Recuperação

O banco SQLite é persistido no volume `zabbix-data`. Para backup:

```bash
# Verificar tamanho atual do banco
docker exec corewise-proxy du -h /var/lib/zabbix/zabbix_proxy.db

# Backup do banco (pode ser grande com 300GB!)
docker exec corewise-proxy sqlite3 /var/lib/zabbix/zabbix_proxy.db ".backup /tmp/backup.db"
docker cp corewise-proxy:/tmp/backup.db ./backup.db

# Restauração
docker cp ./backup.db corewise-proxy:/tmp/backup.db
docker exec corewise-proxy sqlite3 /var/lib/zabbix/zabbix_proxy.db ".restore /tmp/backup.db"

# Executar limpeza manual se necessário
docker exec corewise-proxy python3 /usr/lib/zabbix/externalscripts/db_monitor.py
```

## Configuração Automática no Coolify

1. **Clone este repositório** no Coolify
2. **Configure as variáveis de ambiente** listadas acima
3. **Deploy** - O Coolify detectará automaticamente o docker-compose.yaml
4. **Monitore os logs** durante a primeira inicialização

O arquivo `.env` já contém valores otimizados que podem ser sobrescritos pelas variáveis do Coolify.