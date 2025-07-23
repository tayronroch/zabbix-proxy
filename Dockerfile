# Dockerfile principal para Zabbix Proxy
FROM alpine:latest

# Instalar Docker Compose
RUN apk add --no-cache docker-compose

# Copiar arquivos do projeto
COPY . /app
WORKDIR /app

# Expor porta do Zabbix Proxy
EXPOSE 10051

# Comando para iniciar os serviços
CMD ["docker-compose", "-f", "docker-compose.proxy.yml", "up", "-d"] 