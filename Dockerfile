# Dockerfile para Zabbix Proxy
FROM zabbix/zabbix-proxy-sqlite3:alpine-7.0-latest

# Instalar dependências Python
RUN apk add --no-cache \
    python3 \
    py3-pip \
    openssh-client \
    curl \
    bash \
    snmp-utils \
    dcron

# Instalar bibliotecas Python
RUN pip3 install --no-cache-dir \
    paramiko \
    requests \
    netmiko

# Copiar scripts para o diretório de scripts externos
COPY scripts/ /usr/lib/zabbix/externalscripts/

# Dar permissão de execução aos scripts
RUN chmod +x /usr/lib/zabbix/externalscripts/*.py

# Criar diretório para logs
RUN mkdir -p /var/log/corewise

# Configurar timezone
ENV TZ=America/Sao_Paulo

# Expor porta do Zabbix Proxy
EXPOSE 10051

# Configurar variáveis de ambiente
ENV ZBX_HOSTNAME=corewise-proxy
ENV ZBX_SERVER_HOST=45.161.89.183
ENV ZBX_SERVER_PORT=10051

# Comando para iniciar o Zabbix Proxy
CMD ["zabbix_proxy", "-f"] 