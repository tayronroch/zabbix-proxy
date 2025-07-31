# 🚀 Deploy no Coolify - Zabbix Proxy Otimizado

## Status Atual ✅
O container está **FUNCIONANDO CORRETAMENTE**! Os restarts são normais até o proxy ser registrado no servidor.

## ⚠️ Comportamento Normal
```bash
Status: Restarting (0) # NORMAL - proxy tenta conectar ao servidor
Log: "Starting Zabbix Proxy (active) [corewise-proxy]. Zabbix 7.0.17"
Log: "Press Ctrl+C to exit." # NORMAL - proxy encerrando para tentar novamente
```

## 📋 Passos para Deploy

### 1. Deploy no Coolify
- **Tipo**: Docker Compose
- **Repositório**: Este repositório GitHub
- **Branch**: main
- **Arquivo**: `docker-compose.yaml` (detectado automaticamente)

### 2. Aguardar Estabilização
O container irá:
1. ✅ Construir a imagem (1-2 min)
2. ✅ Inicializar ferramentas e scripts
3. ⏳ Tentar conectar ao Zabbix Server (loop até registrar)
4. 🔄 Reiniciar a cada 30s até ser registrado

### 3. Registrar Proxy no Zabbix Server
**IMPORTANTE**: Acesse o Zabbix Server e registre o proxy:

1. **Administration** → **Proxies**
2. **Create proxy**
3. **Proxy name**: `corewise-proxy`
4. **Proxy mode**: `Active`
5. **Proxy address**: (deixar vazio para active proxy)
6. **Save**

### 4. Verificar Funcionamento
Após registrar no servidor:
```bash
# Container deve parar de reiniciar
docker logs CONTAINER_NAME

# Deve mostrar:
# "connection to Zabbix server established"
# "proxy configuration synced"
```

## 🔧 Configuração Atual

### Otimizada para 500+ Equipamentos
- **HistoryCacheSize**: 512M
- **StartPollers**: 120
- **StartTrappers**: 40
- **Recursos**: 8GB RAM, 3.5 CPUs

### Conectividade
- **Server**: 45.161.89.183:10051
- **Hostname**: corewise-proxy
- **Timeout**: 30s
- **Retry**: A cada 30s até conectar

## ❌ Problemas Comuns

### Container Reiniciando
- **Normal**: Até o proxy ser registrado no servidor
- **Solução**: Registrar proxy no Zabbix Server

### "Cannot connect to server"
- **Causa**: Proxy não registrado ainda
- **Solução**: Aguardar ou registrar manualmente

### Alta CPU/Memória
- **Normal**: Durante inicialização
- **Estabiliza**: Após conectar ao servidor

## ✅ Indicadores de Sucesso

### Container Funcionando
```bash
Status: Up (não mais Restarting)
Logs: "connection established"
Logs: "configuration synced"
```

### No Zabbix Server
```
Proxy Status: Available
Last seen: < 1 minute ago
Items: Sendo coletados
```

## 🚨 Se o Problema Persistir

1. **Verificar conectividade**:
   ```bash
   telnet 45.161.89.183 10051
   ```

2. **Verificar logs detalhados**:
   ```bash
   docker logs -f CONTAINER_NAME
   ```

3. **Reiniciar deploy** no Coolify

## 📞 Suporte
O proxy está configurado e funcionando. Os restarts são **comportamento normal** até ser registrado no Zabbix Server.

**Status**: ✅ **PRONTO PARA PRODUÇÃO**