# ANALISE DE CONFIGURACOES PARA ALTA CARGA - ZABBIX PROXY 7.0 LTS

## RESUMO EXECUTIVO

Baseado na analise do seu ambiente Zabbix Proxy 7.0 LTS com **32.327 itens** e **261 hosts**, identifiquei varios pontos de otimizacao para resolver os problemas de performance mostrados no grafico de "Utilizacao de processos coletores de dados de poller inalcançaveis".

## ⚠️ IMPORTANTE: MUDANCAS NO ZABBIX 7.0 LTS

### Principais Mudancas:
1. **Variaveis de ambiente limitadas** - Muitas configuracoes agora sao definidas diretamente no `zabbix_proxy.conf`
2. **Novos processos** - History Pollers, LLD Processors, Task Manager, etc.
3. **Configuracoes de cache** - Agora sao definidas no arquivo de configuracao
4. **Compatibilidade** - Zabbix 7.0 nao suporta muitas variaveis ZBX_START_*

## PROBLEMAS IDENTIFICADOS

### 1. **Poller Unreachable > 75%**
- **Problema**: Processos de coleta ficam sobrecarregados
- **Causa**: Configuracoes de pollers insuficientes para a carga atual
- **Impacto**: Perda de dados e latencia alta

### 2. **Configuracoes Atuais vs Necessarias**

| Configuracao | Atual | Recomendada | Melhoria |
|---------------|-------|-------------|----------|
| StartPollers | 120 | 200 | +67% |
| CacheSize | 1G | 2G | +100% |
| HistoryCacheSize | 512M | 1G | +100% |
| Memory Limit | 8G | 12G | +50% |
| CPU Limit | 3.5 | 4.0 | +14% |

## OTIMIZACOES PROPOSTAS (ZABBIX 7.0 LTS)

### 1. **Configuracoes de Processos (Dockerfile.proxy)**
```bash
# ATUAL (Dockerfile)
StartPollers=120
StartIPMIPollers=10
StartDiscoverers=20
StartHTTPPollers=10
StartTrappers=40

# OTIMIZADO (Dockerfile.proxy)
StartPollers=200
StartIPMIPollers=20
StartDiscoverers=30
StartHTTPPollers=20
StartTrappers=60

# NOVOS PROCESSOS ZABBIX 7.0 LTS
StartHistoryPollers=10
StartLLDProcessors=5
StartTaskManager=1
StartAlertManagers=3
StartPreprocessors=3
```

### 2. **Configuracoes de Cache (Dockerfile.proxy)**
```bash
# ATUAL (Dockerfile)
CacheSize=1G
HistoryCacheSize=512M
HistoryIndexCacheSize=128M

# OTIMIZADO (Dockerfile.proxy)
CacheSize=2G
HistoryCacheSize=1G
HistoryIndexCacheSize=256M
```

### 3. **Configuracoes de Recursos (.env)**
```bash
# ATUAL (docker-compose.yaml)
memory: 8G
cpus: 3.5

# OTIMIZADO (.env)
CONTAINER_MEMORY_LIMIT=12G
CONTAINER_CPU_LIMIT=4.0
```

### 4. **Configuracoes de Timeout (.env)**
```bash
# ATUAL (Dockerfile)
Timeout=30
UnreachableDelay=60
UnavailableDelay=300

# OTIMIZADO (.env)
ZBX_TIMEOUT=20
```

## IMPLEMENTACAO CORRETA (ZABBIX 7.0 LTS)

### Passo 1: Atualizar Dockerfile.proxy
```bash
# Editar o arquivo Dockerfile.proxy e alterar as configuracoes:
# - StartPollers=200
# - CacheSize=2G
# - HistoryCacheSize=1G
# - Adicionar novos processos do Zabbix 7.0
```

### Passo 2: Criar arquivo .env
```bash
# Renomear o arquivo criado
mv env_otimizado.txt .env
```

### Passo 3: Reconstruir e aplicar configuracoes
```bash
# Reconstruir a imagem com as novas configuracoes
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Passo 4: Monitorar performance
```bash
# Verificar logs
docker logs corewise-proxy

# Verificar uso de recursos
docker stats corewise-proxy
```

## NOVAS CONFIGURACOES ZABBIX 7.0 LTS

### 1. **History Pollers**
- **Funcao**: Processa itens calculados, agregados e verificacoes internas
- **Recomendacao**: 10 para alta carga
- **Impacto**: Melhora performance de itens calculados

### 2. **LLD Processors**
- **Funcao**: Processa descoberta de baixo nivel
- **Recomendacao**: 5 para alta carga
- **Impacto**: Melhora descoberta automatica

### 3. **Task Manager**
- **Funcao**: Gerencia tarefas assincronas
- **Recomendacao**: 1 (padrao)
- **Impacto**: Melhora gerenciamento de tarefas

### 4. **Alert Managers**
- **Funcao**: Processa alertas
- **Recomendacao**: 3 para alta carga
- **Impacto**: Melhora processamento de alertas

### 5. **Preprocessors**
- **Funcao**: Processa dados antes do armazenamento
- **Recomendacao**: 3 para alta carga
- **Impacto**: Melhora processamento de dados

## BENEFICIOS ESPERADOS

### 1. **Reducao de Poller Unreachable**
- **Antes**: 100% de utilizacao (problema)
- **Depois**: < 50% de utilizacao (meta)

### 2. **Melhoria de Performance**
- **Throughput**: +67% mais pollers
- **Cache**: +100% mais memoria de cache
- **Novos Processos**: History Pollers e LLD Processors

### 3. **Estabilidade**
- Menos desconexoes
- Melhor coleta de dados
- Sistema mais responsivo

## MONITORAMENTO POST-IMPLEMENTACAO

### 1. **Metricas a Acompanhar**
- Utilizacao de poller unreachable
- Tempo de resposta dos hosts
- Uso de memoria e CPU
- Tamanho do banco SQLite
- **Novo**: History Pollers utilization
- **Novo**: LLD Processors utilization

### 2. **Alertas Recomendados**
```bash
# Criar triggers para:
- Poller unreachable > 50%
- History Pollers > 80%
- LLD Processors > 80%
- Memoria > 80%
- CPU > 80%
- Latencia > 200ms
```

## CONFIGURACOES ADICIONAIS

### 1. **Otimizacoes de Sistema**
```bash
# Adicionar ao docker-compose.yaml
sysctls:
  - net.core.somaxconn=65535
  - net.ipv4.tcp_max_syn_backlog=65535
```

### 2. **Otimizacoes de Rede**
```bash
# Configurar DNS otimizado
DNS_PRIMARY=8.8.8.8
DNS_SECONDARY=8.8.4.4
```

### 3. **Otimizacoes de Log**
```bash
# Rotacao de logs otimizada
LogFileSize=100M
LogFileCount=10
```

## RECOMENDACOES FINAIS

### 1. **Implementacao Gradual**
- Aplicar mudancas em horario de baixa carga
- Monitorar por 24h antes de ajustes finais
- Fazer backup do banco antes das mudancas

### 2. **Ajustes Baseados em Resultados**
- Se poller unreachable ainda > 50%: aumentar StartPollers
- Se memoria > 90%: reduzir cache ou aumentar limite
- Se CPU > 90%: otimizar timeouts ou reduzir processos
- **Novo**: Se History Pollers > 80%: aumentar StartHistoryPollers

### 3. **Manutencao Regular**
- Monitorar crescimento do banco SQLite
- Ajustar configuracoes conforme crescimento
- Revisar configuracoes mensalmente

## CONCLUSAO

As configuracoes atuais estao adequadas para uma carga media, mas insuficientes para os **32.327 itens** e **261 hosts** do seu ambiente. As otimizacoes propostas devem resolver os problemas de poller unreachable e melhorar significativamente a performance geral do sistema.

**Prioridade**: Implementar as configuracoes de processos e cache primeiro, pois sao as que terao maior impacto na resolucao do problema atual.

**IMPORTANTE**: No Zabbix 7.0 LTS, muitas configuracoes sao definidas diretamente no arquivo `zabbix_proxy.conf` dentro do Dockerfile, nao como variaveis de ambiente. Para alterar configuracoes de performance, edite o Dockerfile.proxy e reconstrua a imagem. 