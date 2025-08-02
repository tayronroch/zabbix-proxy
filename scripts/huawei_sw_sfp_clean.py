#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Huawei Switch SFP collector - VERSÃO LIMPA SEM CACHE
"""

import sys
import re
import subprocess
import paramiko
import json
import time
import signal

def timeout_handler(signum, frame):
    """Handler para timeout geral"""
    raise TimeoutError("Script timeout - execução excedeu 30 segundos")

def set_timeout(seconds=30):
    """Define timeout geral para o script"""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

def ssh_command_simple(ip, port, user, password, command, debug=False):
    """Executa comando SSH simples"""
    ssh = None
    try:
        if debug:
            print(f"DEBUG: Executando comando SSH: '{command}'")
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=port, username=user, password=password, 
                   look_for_keys=False, timeout=3, banner_timeout=5)
        
        full_command = f"screen-length 0 temporary; {command}"
        _, stdout, stderr = ssh.exec_command(full_command, timeout=8)
        raw = stdout.read()
        
        try:
            output = raw.decode("utf-8")
        except UnicodeDecodeError:
            output = raw.decode("latin1")
        
        ssh.close()
        return output
        
    except Exception as e:
        if ssh:
            try:
                ssh.close()
            except:
                pass
        if debug:
            print(f"DEBUG: Erro SSH: {str(e)}")
        raise Exception(f"Erro SSH em '{command}': {str(e)}")

def get_interfaces(ip, port, user, password, debug=False):
    """Obtem interfaces com descrição"""
    output = ssh_command_simple(ip, port, user, password, "display interface description", debug)
    
    interfaces = {}
    for line in output.splitlines():
        line = line.strip()
        # Ignora linhas de cabeçalho e informações
        if line.startswith("PHY:") or line.startswith("*down:") or line.startswith("#down:"):
            continue
        if line.startswith("(") or line.startswith("Interface"):
            continue
        if not line:
            continue
            
        # Parse das linhas de interface: Interface PHY Protocol Description
        parts = line.split()
        if len(parts) >= 3:
            ifname = parts[0]
            phy_status = parts[1] 
            proto_status = parts[2]
            # Descrição pode ter espaços, junta tudo depois da 3ª coluna
            ifalias = " ".join(parts[3:]) if len(parts) > 3 else ""
            
            # Inclui apenas interfaces físicas com SFP/transceivers
            if any(x in ifname for x in ["XGE", "100GE", "25GE", "40GE", "GigabitEthernet"]):
                # Só inclui interfaces que estão UP fisicamente (têm transceiver)
                if phy_status == "up":
                    interfaces[ifname] = ifalias if ifalias else "No Description"
    
    return interfaces

def parse_transceiver_output(output, interface, debug=False):
    """Parse da saída do comando display transceiver verbose interface"""
    transceiver_data = {}
    
    # Parse temperatura - formato: "  Temperature(°C)             :41.74"
    temp_match = re.search(r"Temperature\([^)]+\)\s*:\s*([+-]?\d+\.?\d*)", output)
    if temp_match:
        transceiver_data["temperature"] = temp_match.group(1)
        if debug:
            print(f"DEBUG: {interface} temperature: {temp_match.group(1)}°C")
    
    # Parse voltagem - formato: "  Voltage(V)                    :3.30"
    volt_match = re.search(r"Voltage\(V\)\s*:\s*(\d+\.?\d*)", output)
    if volt_match:
        transceiver_data["voltage"] = volt_match.group(1)
        if debug:
            print(f"DEBUG: {interface} voltage: {volt_match.group(1)}V")
    
    # Parse bias current
    if "100GE" in interface:
        # Multi-lane: procura por padrões como "66.68|69.75(Lane0|Lane1)"
        bias_match = re.search(r"Bias Current\(mA\)\s*:\s*([\d\.\|]+)", output)
        if bias_match and '|' in bias_match.group(1):
            bias_values = bias_match.group(1).split('|')
            for i, value in enumerate(bias_values):
                transceiver_data[f"bias_current_lane_{i}"] = value.strip()
    else:
        # Single-lane: "  Bias Current(mA)              :7.23"
        bias_match = re.search(r"Bias Current\(mA\)\s*:\s*(\d+\.?\d*)", output)
        if bias_match:
            transceiver_data["bias_current"] = bias_match.group(1)
    
    # Parse TX power
    if "100GE" in interface:
        # Multi-lane
        tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([\d\.\-\|]+)", output)
        if tx_match and '|' in tx_match.group(1):
            tx_values = tx_match.group(1).split('|')
            for i, value in enumerate(tx_values):
                transceiver_data[f"tx_power_lane_{i}"] = value.strip()
    else:
        # Single-lane
        tx_match = re.search(r"TX Power\(dBM\)\s*:\s*([+-]?\d+\.?\d*)", output)
        if tx_match:
            transceiver_data["tx_power"] = tx_match.group(1)
    
    # Parse RX power
    if "100GE" in interface:
        # Multi-lane
        rx_match = re.search(r"RX Power\(dBM\)\s*:\s*([\d\.\-\|]+)", output)
        if rx_match and '|' in rx_match.group(1):
            rx_values = rx_match.group(1).split('|')
            for i, value in enumerate(rx_values):
                transceiver_data[f"rx_power_lane_{i}"] = value.strip()
    else:
        # Single-lane
        rx_match = re.search(r"RX Power\(dBM\)\s*:\s*([+-]?\d+\.?\d*)", output)
        if rx_match:
            transceiver_data["rx_power"] = rx_match.group(1)
    
    if debug:
        print(f"DEBUG: {interface} transceiver data: {len(transceiver_data)} metrics")
    
    return transceiver_data

def launch_discovery_and_collect(ip, port, user, password, hostname, debug=False):
    """Executa discovery e coleta SUPER SIMPLES - VERSÃO LIMPA"""
    try:
        start_time = time.time()
        
        if debug:
            print("DEBUG: Iniciando coleta SFP simplificada...")
        
        # Executa comandos SSH
        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, port=port, username=user, password=password, 
                       look_for_keys=False, timeout=3, banner_timeout=5)
            
            # Comando combinado
            full_command = """screen-length 0 temporary
display interface description
display transceiver verbose"""
            
            if debug:
                print("DEBUG: Executando comando combinado...")
            
            _, stdout, stderr = ssh.exec_command(full_command, timeout=15)
            raw_output = stdout.read()
            
            try:
                full_output = raw_output.decode("utf-8")
            except UnicodeDecodeError:
                full_output = raw_output.decode("latin1")
            
            ssh.close()
            
            if debug:
                print(f"DEBUG: Comando executado. Output size: {len(full_output)} chars")
            
            # Parse interfaces da saída combinada
            interfaces = {}
            lines = full_output.splitlines()
            
            # Procura pela seção de interfaces
            interface_section = False
            for line in lines:
                line = line.strip()
                
                if "display interface description" in line:
                    interface_section = True
                    continue
                elif "display transceiver verbose" in line:
                    interface_section = False
                    break
                
                if interface_section:
                    # Ignora linhas de cabeçalho
                    if line.startswith("PHY:") or line.startswith("*down:") or line.startswith("#down:"):
                        continue
                    if line.startswith("(") or line.startswith("Interface"):
                        continue
                    if not line or line.endswith(">"):
                        continue
                        
                    # Parse das linhas de interface
                    parts = line.split()
                    if len(parts) >= 3:
                        ifname = parts[0]
                        phy_status = parts[1] 
                        ifalias = " ".join(parts[3:]) if len(parts) > 3 else "No Description"
                        
                        # Inclui apenas interfaces físicas com SFP UP
                        if any(x in ifname for x in ["XGE", "100GE", "25GE", "40GE"]) and phy_status == "up":
                            interfaces[ifname] = ifalias
            
            if debug:
                print(f"DEBUG: Interfaces encontradas: {len(interfaces)} - {list(interfaces.keys())}")
            
            # Discovery separado por tipo
            discovery_single = []
            discovery_multi = []
            
            for ifname, ifalias in interfaces.items():
                if "100GE" in ifname:
                    discovery_multi.append({
                        "{#IFNAME}": ifname,
                        "{#IFALIAS}": ifalias,
                        "{#GBIC_LANE}": "0"
                    })
                else:
                    discovery_single.append({
                        "{#IFNAME}": ifname,
                        "{#IFALIAS}": ifalias
                    })
            
            if debug:
                print(f"DEBUG: Single-lane discovery: {len(discovery_single)} interfaces")
                print(f"DEBUG: Multi-lane discovery: {len(discovery_multi)} interfaces")
            
            # Envia discoveries
            if discovery_single:
                subprocess.run([
                    "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic_single", 
                    "-o", json.dumps({"data": discovery_single})
                ], capture_output=True, timeout=5, text=True)
                
            if discovery_multi:
                subprocess.run([
                    "zabbix_sender", "-z", "127.0.0.1", "-s", hostname, "-k", "discovery_gbic_multi", 
                    "-o", json.dumps({"data": discovery_multi})
                ], capture_output=True, timeout=5, text=True)
            
            # Aguarda processamento do discovery
            if debug:
                print("DEBUG: Aguardando processamento do discovery...")
            time.sleep(2)
            
            # Parse e envio de métricas
            success_count = 0
            error_count = 0
            metrics_batch = []
            
            for ifname in interfaces.keys():
                try:
                    # Procura pela seção desta interface na saída do transceiver verbose
                    interface_pattern = f"{ifname} transceiver information:"
                    start_idx = full_output.find(interface_pattern)
                    
                    if start_idx != -1:
                        # Encontra o fim da seção
                        next_interface = full_output.find(" transceiver information:", start_idx + 1)
                        if next_interface == -1:
                            interface_output = full_output[start_idx:]
                        else:
                            interface_output = full_output[start_idx:next_interface]
                        
                        # Parse dos dados SFP
                        transceiver_data = parse_transceiver_output(interface_output, ifname, debug)
                        
                        if debug:
                            print(f"DEBUG: Interface {ifname} - coletadas {len(transceiver_data)} métricas")
                        
                        # Envia métricas com as chaves corretas baseadas no tipo de interface
                        if "100GE" in ifname:
                            # Multi-lane interface
                            for metric, value in transceiver_data.items():
                                if metric.endswith("_lane_0") or metric.endswith("_lane_1") or metric.endswith("_lane_2") or metric.endswith("_lane_3"):
                                    # Extrai número da lane
                                    lane_num = metric.split("_")[-1]
                                    base_metric = "_".join(metric.split("_")[:-2])
                                    
                                    if base_metric == "bias_current":
                                        key = f"currML[{ifname},{lane_num}]"
                                    elif base_metric == "tx_power":
                                        key = f"txpowerML[{ifname},{lane_num}]"
                                    elif base_metric == "rx_power":
                                        key = f"rxpowerML[{ifname},{lane_num}]"
                                    else:
                                        continue
                                        
                                    metrics_batch.append(f"{hostname} {key} {value}")
                                    success_count += 1
                                elif metric == "temperature":
                                    key = f"tempML[{ifname},0]"
                                    metrics_batch.append(f"{hostname} {key} {value}")
                                    success_count += 1
                                elif metric == "voltage":
                                    key = f"voltML[{ifname},0]"
                                    metrics_batch.append(f"{hostname} {key} {value}")
                                    success_count += 1
                        else:
                            # Single-lane interface
                            for metric, value in transceiver_data.items():
                                if metric == "bias_current":
                                    key = f"curr[{ifname}]"
                                elif metric == "tx_power":
                                    key = f"txpower[{ifname}]"
                                elif metric == "rx_power":
                                    key = f"rxpower[{ifname}]"
                                elif metric == "temperature":
                                    key = f"temp[{ifname}]"
                                elif metric == "voltage":
                                    key = f"volt[{ifname}]"
                                else:
                                    continue
                                    
                                metrics_batch.append(f"{hostname} {key} {value}")
                                success_count += 1
                    else:
                        if debug:
                            print(f"DEBUG: Seção transceiver não encontrada para {ifname}")
                        error_count += 1
                        
                except Exception as ex:
                    if debug:
                        print(f"DEBUG: Erro processando {ifname}: {str(ex)}")
                    error_count += 1
            
            # Envia todas as métricas em lote
            if metrics_batch:
                try:
                    batch_data = "\n".join(metrics_batch)
                    process = subprocess.run([
                        "zabbix_sender", "-z", "127.0.0.1", "-i", "-"
                    ], input=batch_data, capture_output=True, timeout=5, text=True)
                    if process.returncode != 0:
                        if debug:
                            print(f"DEBUG: Zabbix sender falhou: {process.stderr}")
                        error_count += len(metrics_batch)
                        success_count = 0
                except Exception as e:
                    if debug:
                        print(f"DEBUG: Erro enviando métricas: {str(e)}")
                    error_count += len(metrics_batch)
                    success_count = 0
            
        except Exception as ssh_error:
            if ssh:
                try:
                    ssh.close()
                except:
                    pass
            raise ssh_error
        
        elapsed = time.time() - start_time
        
        # Feedback de performance
        if error_count == 0:
            print("SUCESSO: Discovery e coleta SFP executados com sucesso!")
            print(f"Metricas SFP: {success_count} processadas em {elapsed:.1f}s")
        else:
            print(f"PARCIAL: {error_count} falhas de {success_count + error_count} metricas SFP em {elapsed:.1f}s")
        
    except Exception as e:
        print(f"ERRO: Falha na execucao do processo - {str(e)}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()

def main():
    # Define timeout geral de 30 segundos
    set_timeout(30)
    
    try:
        if len(sys.argv) < 2:
            print("Uso: huawei_sw_sfp_clean.py <launch_discovery|collect> <ip> <port> <user> <password> <hostname> [debug]", file=sys.stderr)
            sys.exit(1)
        
        # Verifica se debug foi habilitado
        debug = len(sys.argv) > 7 and sys.argv[7].lower() == "debug"
        
        mode = sys.argv[1]
        if mode == "launch_discovery":
            if len(sys.argv) < 7:
                print("Uso: huawei_sw_sfp_clean.py launch_discovery <ip> <port> <user> <password> <hostname> [debug]", file=sys.stderr)
                sys.exit(1)
            _, _, ip, port, user, password, hostname = sys.argv[:7]
            
            # Validação de parâmetros
            if port.startswith('{$') or user.startswith('{$') or password.startswith('{$'):
                print("ERRO: Macros não foram substituídas pelo Zabbix. Verifique se {$SSH_PORT}, {$SSH_USER} e {$SSH_PASS} estão definidas no template.", file=sys.stderr)
                sys.exit(1)
            
            try:
                port_int = int(port)
            except ValueError:
                print(f"ERRO: Porta SSH inválida: '{port}'. Deve ser um número.", file=sys.stderr)
                sys.exit(1)
                
            launch_discovery_and_collect(ip, port_int, user, password, hostname, debug)
        else:
            print("ERRO: Modo desconhecido. Use launch_discovery.", file=sys.stderr)
            sys.exit(2)
            
    except TimeoutError as e:
        print(f"ERRO: {str(e)}", file=sys.stderr)
        sys.exit(3)
    finally:
        # Cancela o alarme
        signal.alarm(0)

if __name__ == "__main__":
    main()