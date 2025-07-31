#!/usr/bin/env python3
"""
Script para monitorar o tamanho do banco SQLite do Zabbix Proxy
e executar limpeza automática quando necessário.
"""
import os
import sqlite3
import logging
import sys
from datetime import datetime, timedelta

# Configurações
DB_PATH = "/var/lib/zabbix/zabbix_proxy.db"
MAX_SIZE_GB = 280  # Limite de 280GB
HISTORY_RETENTION_DAYS = 365  # 1 ano
TRENDS_RETENTION_DAYS = 1825  # 5 anos
LOG_PATH = "/var/log/zabbix/db_monitor.log"

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

def get_db_size_gb():
    """Retorna o tamanho do banco em GB"""
    if not os.path.exists(DB_PATH):
        return 0
    size_bytes = os.path.getsize(DB_PATH)
    return size_bytes / (1024**3)  # Converter para GB

def get_table_sizes(cursor):
    """Retorna o tamanho das principais tabelas"""
    tables = ['history', 'history_uint', 'history_str', 'history_log', 'history_text', 'trends', 'trends_uint']
    sizes = {}
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            sizes[table] = count
        except sqlite3.Error as e:
            logging.warning(f"Erro ao consultar tabela {table}: {e}")
            sizes[table] = 0
    
    return sizes

def cleanup_old_data(cursor, days_to_keep, table_name, date_column='clock'):
    """Remove dados antigos de uma tabela"""
    cutoff_timestamp = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())
    
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {date_column} < ?", (cutoff_timestamp,))
        old_records = cursor.fetchone()[0]
        
        if old_records > 0:
            logging.info(f"Removendo {old_records} registros antigos da tabela {table_name}")
            cursor.execute(f"DELETE FROM {table_name} WHERE {date_column} < ?", (cutoff_timestamp,))
            logging.info(f"Removidos {cursor.rowcount} registros da tabela {table_name}")
        else:
            logging.info(f"Nenhum registro antigo encontrado na tabela {table_name}")
            
    except sqlite3.Error as e:
        logging.error(f"Erro ao limpar tabela {table_name}: {e}")

def vacuum_database(cursor):
    """Executa VACUUM para compactar o banco"""
    logging.info("Iniciando VACUUM do banco de dados...")
    try:
        cursor.execute("VACUUM")
        logging.info("VACUUM concluído com sucesso")
    except sqlite3.Error as e:
        logging.error(f"Erro durante VACUUM: {e}")

def optimize_database(cursor):
    """Otimiza o banco de dados"""
    logging.info("Otimizando banco de dados...")
    try:
        cursor.execute("ANALYZE")
        cursor.execute("PRAGMA optimize")
        logging.info("Otimização concluída")
    except sqlite3.Error as e:
        logging.error(f"Erro durante otimização: {e}")

def main():
    logging.info("=== Iniciando monitoramento do banco de dados ===")
    
    # Verificar tamanho atual
    current_size = get_db_size_gb()
    logging.info(f"Tamanho atual do banco: {current_size:.2f} GB")
    
    if current_size < MAX_SIZE_GB * 0.8:  # 80% do limite
        logging.info(f"Banco dentro do limite seguro (< {MAX_SIZE_GB * 0.8:.1f} GB)")
        return 0
    
    if not os.path.exists(DB_PATH):
        logging.error(f"Banco de dados não encontrado: {DB_PATH}")
        return 1
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar tamanhos das tabelas
        table_sizes = get_table_sizes(cursor)
        logging.info("Tamanhos das tabelas:")
        for table, size in table_sizes.items():
            logging.info(f"  {table}: {size:,} registros")
        
        if current_size >= MAX_SIZE_GB * 0.8:  # 80% do limite
            logging.warning(f"Banco próximo ao limite! Iniciando limpeza...")
            
            # Limpar dados antigos das tabelas de histórico
            history_tables = ['history', 'history_uint', 'history_str', 'history_log', 'history_text']
            for table in history_tables:
                cleanup_old_data(cursor, HISTORY_RETENTION_DAYS, table)
            
            # Limpar dados antigos das tabelas de trends
            trends_tables = ['trends', 'trends_uint']
            for table in trends_tables:
                cleanup_old_data(cursor, TRENDS_RETENTION_DAYS, table)
            
            # Commit das mudanças
            conn.commit()
            
            # Compactar banco se necessário
            if current_size >= MAX_SIZE_GB * 0.9:  # 90% do limite
                vacuum_database(cursor)
            
            # Otimizar banco
            optimize_database(cursor)
            
            # Verificar tamanho final
            conn.close()
            final_size = get_db_size_gb()
            logging.info(f"Tamanho final do banco: {final_size:.2f} GB")
            logging.info(f"Espaço liberado: {current_size - final_size:.2f} GB")
        
        else:
            conn.close()
    
    except sqlite3.Error as e:
        logging.error(f"Erro ao acessar banco de dados: {e}")
        return 1
    except Exception as e:
        logging.error(f"Erro inesperado: {e}")
        return 1
    
    logging.info("=== Monitoramento concluído ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())