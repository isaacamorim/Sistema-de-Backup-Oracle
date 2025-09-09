#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import zipfile
import subprocess
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate
import traceback
import locale
import glob
import json
import sys
from pathlib import Path
import html

# ===== CONFIGURAÇÕES =====
DB_FOLDER = r"C:\DMP_DIR"  # Pasta onde ficam os arquivos DMP
CLOUD_FOLDER = r"\\10.42.92.192\\Diversos\Eduardo\\Backup"  # Pasta para copiar os backups zipados
LOG_DIR = r"C:\DMP_DIR\Logs"  # Pasta para salvar logs

# Configurações do Oracle
ORACLE_DIRECTORY = "DMP_DIR"  # Nome do directory no Oracle
ORACLE_SERVICE = "ORCL"  # Nome do serviço Oracle

# Usuários e senhas do Oracle para backup - CORRIGIDO para usar schema correto
ORACLE_USERS = [
    {"user": "HORIZONTE", "password": "LARANJA", "schema": "HORIZONTE"},
    {"user": "SYSALL", "password": "LEGEND", "schema": "SYSALL"},
    {"user": "IMG_HORIZONTE", "password": "LARANJA", "schema": "IMG_HORIZONTE"},
]

# Configurações de e-mail
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "isaacvinicius.carvalho@gmail.com"
SMTP_PASSWORD = "holw hscs hwjl eawn"  # CONFIGURE AQUI - Use App Password do Gmail
EMAIL_FROM = "isaac.ti.nh@gmail.com"
EMAIL_TO = [
            "isaacvinicius.carvalho@gmail.com",
            "eduardo@nh.ind.br"
]

# Configurações de compressão
COMPRESSION_METHOD = zipfile.ZIP_DEFLATED
COMPRESSION_LEVEL = 6

# Configurações de retenção (OTIMIZADO PARA ARQUIVOS GRANDES)
RETENTION_DAYS = 10  # Mantém 10 dias para margem de segurança
KEEP_MINIMUM_BACKUPS = 2  # Sempre mantém pelo menos 2 backups recentes
MAX_TOTAL_BACKUPS = 7  # Máximo de backups simultâneos

# Criar diretórios
for directory in [LOG_DIR, DB_FOLDER, CLOUD_FOLDER]:
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception as e:
        print(f"❌ Erro ao criar diretório {directory}: {e}")


class BackupLogger:
    def __init__(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = os.path.join(LOG_DIR, f"backup_completo_{today}.log")
        self.errors = 0
        self.warnings = 0
        self.dmp_success = 0
        self.dmp_total = 0
        self.start_time = datetime.now()

        # Limpar logs antigos (mais de 30 dias)
        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        """Remove logs com mais de 30 dias"""
        try:
            cutoff_date = datetime.now() - timedelta(days=30)
            for log_file in Path(LOG_DIR).glob("backup_completo_*.log"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
        except Exception:
            pass

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {msg}"

        if level == "ERROR":
            self.errors += 1
        elif level == "WARNING":
            self.warnings += 1

        try:
            with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            print(f"Erro ao escrever log: {e}")

        print(log_entry)

    def get_duration(self):
        """Retorna duração total da execução"""
        return (datetime.now() - self.start_time).total_seconds()

def get_file_size_mb(file_path):
    try:
        size = os.path.getsize(file_path) / (1024 * 1024)  # bytes → MB
        return round(size, 2)
    except Exception:
        return 0

def get_weekday_name():
    """Obtém o nome do dia da semana em português - CORRIGIDO"""
    # Mapa direto dos dias da semana (0=segunda, 6=domingo no Python)
    dias_semana = {
        0: "segunda-feira",    # Monday
        1: "terça-feira",      # Tuesday  
        2: "quarta-feira",     # Wednesday
        3: "quinta-feira",     # Thursday
        4: "sexta-feira",      # Friday
        5: "sábado",           # Saturday
        6: "domingo"           # Sunday
    }
    
    hoje = datetime.now()
    return dias_semana[hoje.weekday()]

def ensure_drive_access(logger):
    """Tenta garantir acesso ao drive J:\ mapeando se necessário"""

    # Primeiro testa se J:\ já funciona
    if os.path.exists(r"J:\\"):
        logger.log("✅ Drive J:\\ já está acessível")
        return True

    logger.log("⚠️ Drive J:\\ não acessível - tentando mapear", "WARNING")

    # Opções de mapeamento (ajuste conforme sua rede)
    mapping_options = [
        ("\\\\10.42.92.192\\Diversos\\Eduardo\\Backup", "J:"),
        # Se precisar de usuário/senha:
        # ("\\\\10.42.92.192\\Eduardo\\Backup", "J:", "USUARIO", "SENHA"),
    ]

    for option in mapping_options:
        try:
            if len(option) == 2:
                unc_path, drive_letter = option
                cmd = ["net", "use", drive_letter, unc_path]
            else:
                unc_path, drive_letter, user, pwd = option
                cmd = ["net", "use", drive_letter, unc_path, "/user:" + user, pwd]

            logger.log(f"🔄 Tentando mapear {unc_path} como {drive_letter}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                logger.log(f"✅ Drive {drive_letter} mapeado com sucesso")
                return True
            else:
                logger.log(f"❌ Falha ao mapear: {result.stderr.strip()}", "WARNING")

        except Exception as e:
            logger.log(f"❌ Erro no mapeamento: {e}", "WARNING")

    logger.log("⚠️ Não foi possível mapear J:\\ - backup ficará apenas local", "WARNING")
    return False

def check_disk_space(path, min_gb_required=50):
    """Verifica espaço em disco disponível"""
    try:
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024**3)
        total_gb = total / (1024**3)
        used_gb = used / (1024**3)

        return free_gb >= min_gb_required, free_gb, total_gb, used_gb
    except:
        return False, 0, 0, 0


def find_oracle_expdp():
    """Encontra o executável expdp do Oracle - MELHORADO"""
    # Primeiro testa se está no PATH (mais rápido)
    try:
        result = subprocess.run(["expdp", "-help"], capture_output=True, timeout=10, 
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode in [0, 1]:
            return "expdp"
    except:
        pass

    # Verifica ORACLE_HOME
    oracle_home = os.environ.get("ORACLE_HOME")
    if oracle_home:
        expdp_path = os.path.join(oracle_home, "bin", "expdp.exe")
        if os.path.exists(expdp_path):
            return expdp_path

    # Procura em locais comuns
    search_paths = [
        r"C:\oracle\product\*\*\bin\expdp.exe",
        r"C:\app\oracle\product\*\*\bin\expdp.exe",
        r"D:\oracle\product\*\*\bin\expdp.exe",
        r"C:\app\*\product\*\*\bin\expdp.exe",
    ]

    for pattern in search_paths:
        for path in glob.glob(pattern):
            if os.path.exists(path):
                return path

    return None


def execute_oracle_exports(logger):
    """
    Executa os exports do Oracle para gerar os arquivos DMP - CORRIGIDO
    """
    logger.log("🗄️ ===== INICIANDO EXPORTS ORACLE =====")

    # Verificar espaço em disco
    has_space, free_gb, total_gb, used_gb = check_disk_space(DB_FOLDER, 10)
    if not has_space:
        logger.log(f"❌ Espaço insuficiente! Apenas {free_gb:.1f}GB disponível", "ERROR")
        return []

    logger.log(f"💾 Espaço disponível: {free_gb:.1f}GB / {total_gb:.1f}GB")

    # Encontrar expdp
    expdp_path = find_oracle_expdp()
    if not expdp_path:
        logger.log("❌ Oracle expdp não encontrado!", "ERROR")
        return []

    logger.log(f"✅ Oracle expdp encontrado: {expdp_path}")

    dia_semana = get_weekday_name()
    logger.log(f"📅 Gerando backups para: {dia_semana}")

    dmp_files_created = []
    logger.dmp_total = len(ORACLE_USERS)

    for i, user_config in enumerate(ORACLE_USERS, 1):
        user = user_config["user"]
        password = user_config["password"]
        schema = user_config["schema"]

        # Nome do arquivo DMP - CORRIGIDO para seguir padrão do .bat
        if schema == "IMG_HORIZONTE":
            # No .bat era: img_HORIZONTE_%DIA_SEMANA%.DMP
            dmp_filename = f"img_HORIZONTE_{dia_semana}.DMP"
        else:
            # No .bat era: SCHEMA_%DIA_SEMANA%.DMP
            dmp_filename = f"{schema}_{dia_semana}.DMP"

        log_filename = f"{schema}_{dia_semana}.LOG"
        dmp_path = os.path.join(DB_FOLDER, dmp_filename)

        # Remover arquivo existente
        if os.path.exists(dmp_path):
            try:
                os.remove(dmp_path)
                logger.log(f"🗑️ Arquivo DMP anterior removido: {dmp_filename}")
            except Exception as e:
                logger.log(f"⚠️ Não foi possível remover DMP anterior: {e}", "WARNING")

        # Comando expdp - CORRIGIDO para seguir exatamente o padrão do .bat
        connection_string = f"{user}/{password}@{ORACLE_SERVICE}"
        
        cmd_params = [
            connection_string,
            f"DIRECTORY={ORACLE_DIRECTORY}",
            f"DUMPFILE={dmp_filename}",
            f"LOGFILE={ORACLE_DIRECTORY}:{log_filename}",
            "REUSE_DUMPFILES=YES"
            # Removido COMPRESSION=ALL para seguir exatamente o .bat
        ]

        if expdp_path == "expdp":
            cmd = ["expdp"] + cmd_params
        else:
            cmd = [expdp_path] + cmd_params

        logger.log(f"\n[{i}/{len(ORACLE_USERS)}] 🔄 Exportando: {schema}")
        logger.log(f"📁 Arquivo: {dmp_filename}")
        logger.log(f"🔧 Comando: {' '.join(cmd[:2])} [parâmetros ocultos por segurança]")

        # Timeout específico por schema
        timeout_minutes = 180 if schema == "IMG_HORIZONTE" else 60
        timeout_seconds = timeout_minutes * 60

        try:
            start_time = datetime.now()

            # Executar com configurações melhoradas para Windows
            creation_flags = 0
            if os.name == 'nt':  # Windows
                creation_flags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                encoding="cp1252" if os.name == 'nt' else "utf-8",
                errors="replace",
                creationflags=creation_flags,
                cwd=DB_FOLDER  # Define diretório de trabalho
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Log da saída do comando (para debug)
            if result.stdout:
                logger.log("📋 Saída do expdp:", "INFO")
                for line in result.stdout.split('\n')[:10]:  # Primeiras 10 linhas
                    if line.strip():
                        logger.log(f"   {line.strip()}", "INFO")

            # Verificar se o arquivo DMP foi criado
            if os.path.exists(dmp_path):
                file_size = get_file_size_mb(dmp_path)

                # Verificar tamanho mínimo
                min_size = 0.1  # 100KB mínimo
                if file_size < min_size:
                    logger.log(f"❌ {schema}: Arquivo muito pequeno ({file_size:.3f}MB)", "ERROR")
                    continue

                # Sucesso
                logger.log(f"✅ {schema}: Export concluído!")
                logger.log(f"📊 Tamanho: {file_size:.1f}MB | Tempo: {duration/60:.1f}min")

                # Verificar código de retorno
                if result.returncode == 0:
                    logger.log(f"✅ {schema}: Sucesso completo (código 0)")
                elif result.returncode in [1, 5]:  # Códigos comuns de sucesso com avisos
                    logger.log(f"⚠️ {schema}: Sucesso com avisos (código {result.returncode})", "WARNING")
                else:
                    logger.log(f"⚠️ {schema}: Código de retorno incomum: {result.returncode}", "WARNING")

                # Log de possíveis avisos/erros
                if result.stderr and result.stderr.strip():
                    logger.log(f"⚠️ {schema}: Avisos encontrados:", "WARNING")
                    for line in result.stderr.split('\n')[:5]:
                        if line.strip():
                            logger.log(f"   {line.strip()}", "WARNING")

                dmp_files_created.append(dmp_filename)
                logger.dmp_success += 1

            else:
                logger.log(f"❌ {schema}: Arquivo DMP não foi criado", "ERROR")
                logger.log(f"🔍 Código retorno: {result.returncode}", "ERROR")

                if result.stderr and result.stderr.strip():
                    logger.log("📋 Erro detalhado:", "ERROR")
                    for line in result.stderr.split('\n')[:10]:
                        if line.strip():
                            logger.log(f"   {line.strip()}", "ERROR")

                # Verificar se existe arquivo de log do Oracle
                oracle_log_path = os.path.join(DB_FOLDER, log_filename)
                if os.path.exists(oracle_log_path):
                    logger.log("📋 Verificando log do Oracle:", "INFO")
                    try:
                        with open(oracle_log_path, 'r', encoding='utf-8', errors='replace') as f:
                            log_content = f.read()
                            # Mostrar últimas linhas do log
                            lines = log_content.split('\n')[-10:]
                            for line in lines:
                                if line.strip():
                                    logger.log(f"   {line.strip()}", "INFO")
                    except Exception as e:
                        logger.log(f"   Erro ao ler log: {e}", "WARNING")

        except subprocess.TimeoutExpired:
            logger.log(f"⏰ {schema}: TIMEOUT após {timeout_minutes/60:.1f} horas", "ERROR")
            logger.log("   💡 Considere verificar se há locks no banco ou processos longos", "WARNING")
        except Exception as e:
            logger.log(f"💥 {schema}: Erro inesperado - {str(e)}", "ERROR")
            logger.log(f"🔍 Detalhes: {traceback.format_exc()}", "ERROR")

        logger.log("-" * 60)

    # Resumo dos exports
    logger.log(f"📊 RESUMO EXPORTS: {logger.dmp_success}/{logger.dmp_total} sucessos")

    if dmp_files_created:
        logger.log("✅ Arquivos DMP criados:")
        total_size = 0
        for dmp_file in dmp_files_created:
            size = get_file_size_mb(os.path.join(DB_FOLDER, dmp_file))
            total_size += size
            logger.log(f"   📁 {dmp_file} ({size:.1f}MB)")
        logger.log(f"📊 Tamanho total dos DMPs: {total_size:.1f}MB")
    else:
        logger.log("❌ Nenhum arquivo DMP foi criado!", "ERROR")

    return dmp_files_created


def create_daily_zip(dmp_files, logger):
    """Cria arquivo ZIP com os DMPs do dia atual"""
    if not dmp_files:
        logger.log("❌ Nenhum arquivo DMP para compactar!", "ERROR")
        return None

    logger.log("📦 ===== INICIANDO COMPACTAÇÃO =====")

    # Verificar espaço para compactação
    total_original_size = sum(
        get_file_size_mb(os.path.join(DB_FOLDER, dmp)) for dmp in dmp_files
    )
    estimated_zip_size = total_original_size * 0.7

    has_space, free_gb, total_gb, used_gb = check_disk_space(
        DB_FOLDER, estimated_zip_size / 1024
    )
    if not has_space:
        logger.log(f"❌ Espaço insuficiente para ZIP! Precisa ~{estimated_zip_size/1024:.1f}GB", "ERROR")
        return None

    # Nome do ZIP baseado no dia
    hoje = datetime.now()
    dia_semana = get_weekday_name()
    zip_name = f"backup_{dia_semana}_{hoje.strftime('%Y-%m-%d')}.zip"
    zip_path = os.path.join(DB_FOLDER, zip_name)

    logger.log(f"📦 Criando: {zip_name}")
    logger.log(f"📁 Arquivos: {len(dmp_files)} DMPs ({total_original_size:.1f}MB total)")

    try:
        start_time = datetime.now()

        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=COMPRESSION_METHOD,
            compresslevel=COMPRESSION_LEVEL,
            allowZip64=True,
        ) as zipf:

            for i, dmp_file in enumerate(dmp_files, 1):
                file_path = os.path.join(DB_FOLDER, dmp_file)

                if not os.path.exists(file_path):
                    logger.log(f"⚠️ Arquivo não encontrado: {dmp_file}", "WARNING")
                    continue

                file_size = get_file_size_mb(file_path)
                logger.log(f"[{i}/{len(dmp_files)}] 📦 Compactando: {dmp_file} ({file_size:.1f}MB)")

                file_start = datetime.now()
                zipf.write(file_path, dmp_file)
                file_duration = (datetime.now() - file_start).total_seconds()

                if file_duration > 0:
                    speed = file_size / file_duration
                    logger.log(f"✅ Concluído em {file_duration:.1f}s ({speed:.1f}MB/s)")

        # Verificar se ZIP foi criado com sucesso
        if not os.path.exists(zip_path):
            logger.log("❌ Arquivo ZIP não foi criado!", "ERROR")
            return None

        # Estatísticas finais
        total_duration = (datetime.now() - start_time).total_seconds()
        zip_size = get_file_size_mb(zip_path)

        if zip_size == 0:
            logger.log("❌ ZIP criado mas está vazio!", "ERROR")
            return None

        compression_ratio = (
            ((total_original_size - zip_size) / total_original_size) * 100
            if total_original_size > 0
            else 0
        )

        logger.log("🎉 ZIP criado com sucesso!")
        logger.log(f"📊 Original: {total_original_size:.1f}MB")
        logger.log(f"📦 Compactado: {zip_size:.1f}MB")
        logger.log(f"⚡ Compressão: {compression_ratio:.1f}%")
        logger.log(f"⏱️ Tempo total: {total_duration/60:.1f} minutos")

        return zip_path

    except Exception as e:
        logger.log(f"❌ Erro na compactação: {str(e)}", "ERROR")
        logger.log(f"🔍 Detalhes: {traceback.format_exc()}", "ERROR")

        # Tentar remover ZIP corrompido
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
                logger.log("🗑️ ZIP corrompido removido", "INFO")
        except:
            pass

        return None


def remove_old_files(logger):
    """Remove arquivos DMP e ZIP antigos"""
    logger.log("🗑️ ===== LIMPANDO ARQUIVOS ANTIGOS =====")
    logger.log(f"📊 Estratégia: manter {MAX_TOTAL_BACKUPS} ZIPs mais recentes")

    removed_count = 0
    removed_size = 0
    kept_count = 0

    try:
        # Listar todos os arquivos ZIP (manter apenas ZIPs, DMPs são temporários)
        zip_files = []
        for file in os.listdir(DB_FOLDER):
            if file.lower().endswith(".zip") and "backup_" in file.lower():
                file_path = os.path.join(DB_FOLDER, file)
                try:
                    file_date = datetime.fromtimestamp(os.path.getmtime(file_path))
                    file_size = get_file_size_mb(file_path)
                    zip_files.append({
                        "name": file,
                        "path": file_path,
                        "date": file_date,
                        "size": file_size,
                    })
                except Exception as e:
                    logger.log(f"⚠️ Erro ao processar {file}: {e}", "WARNING")

        # Ordenar por data (mais recente primeiro)
        zip_files.sort(key=lambda x: x["date"], reverse=True)

        logger.log(f"📦 Encontrados: {len(zip_files)} arquivos ZIP de backup")

        # Remover DMPs antigos (manter apenas do dia atual)
        today = datetime.now().date()
        for file in os.listdir(DB_FOLDER):
            if file.lower().endswith(".dmp"):
                file_path = os.path.join(DB_FOLDER, file)
                try:
                    file_date = datetime.fromtimestamp(os.path.getmtime(file_path)).date()
                    file_size = get_file_size_mb(file_path)
                    
                    if file_date < today:
                        os.remove(file_path)
                        logger.log(f"🗑️ DMP REMOVIDO: {file} ({file_size:.1f}MB)")
                        removed_count += 1
                        removed_size += file_size
                    else:
                        logger.log(f"📅 DMP ATUAL mantido: {file} ({file_size:.1f}MB)")
                        kept_count += 1
                except Exception as e:
                    logger.log(f"⚠️ Erro ao processar DMP {file}: {e}", "WARNING")

        # Processar ZIPs - manter apenas os mais recentes
        for i, file_info in enumerate(zip_files):
            if i < MAX_TOTAL_BACKUPS:
                # Manter os N mais recentes
                logger.log(f"✅ ZIP MANTIDO [{i+1}]: {file_info['name']} ({file_info['size']:.1f}MB)")
                kept_count += 1
            else:
                # Remover os mais antigos
                try:
                    os.remove(file_info["path"])
                    logger.log(f"🗑️ ZIP REMOVIDO: {file_info['name']} ({file_info['size']:.1f}MB)")
                    removed_count += 1
                    removed_size += file_info["size"]
                except Exception as e:
                    logger.log(f"❌ Erro ao remover ZIP {file_info['name']}: {e}", "ERROR")
                    kept_count += 1

        # Estatísticas
        space_freed_gb = removed_size / 1024

        logger.log("=" * 60)
        logger.log(f"📊 LIMPEZA CONCLUÍDA:")
        logger.log(f"   🗑️ Removidos: {removed_count} arquivos")
        logger.log(f"   📦 Mantidos: {kept_count} arquivos")

        if space_freed_gb > 1:
            logger.log(f"   💾 ESPAÇO LIBERADO: {space_freed_gb:.1f}GB 🎉")
        else:
            logger.log(f"   💾 Espaço liberado: {removed_size:.1f}MB")

        return removed_count, removed_size

    except Exception as e:
        logger.log(f"❌ Erro na limpeza: {str(e)}", "ERROR")
        return 0, 0


def copy_to_cloud(zip_path, logger):
    """Copia o ZIP para a pasta nuvem"""
    logger.log("☁️ ===== COPIANDO PARA NUVEM =====")

    try:
        if not zip_path or not os.path.exists(zip_path):
            logger.log("❌ Arquivo ZIP não existe!", "ERROR")
            return False

        if not os.path.exists(CLOUD_FOLDER):
            logger.log(f"❌ Pasta nuvem não acessível: {CLOUD_FOLDER}", "ERROR")
            return False

        dest_path = os.path.join(CLOUD_FOLDER, os.path.basename(zip_path))
        file_size = get_file_size_mb(zip_path)

        logger.log(f"📁 Origem: {zip_path}")
        logger.log(f"☁️ Destino: {dest_path}")
        logger.log(f"📊 Tamanho: {file_size:.1f}MB")

        # Verificar espaço no destino
        has_space, free_gb, total_gb, used_gb = check_disk_space(CLOUD_FOLDER, file_size / 1024)
        if not has_space:
            logger.log(f"❌ Espaço insuficiente na nuvem!", "ERROR")
            return False

        start_time = datetime.now()
        shutil.copy2(zip_path, dest_path)
        copy_duration = (datetime.now() - start_time).total_seconds()

        # Verificar integridade
        if os.path.exists(dest_path):
            dest_size = get_file_size_mb(dest_path)
            if abs(file_size - dest_size) < 0.1:
                logger.log(f"✅ Cópia realizada com sucesso!")
                logger.log(f"⏱️ Tempo: {copy_duration:.1f}s")
                return True

        logger.log("❌ Falha na verificação de integridade!", "ERROR")
        return False

    except Exception as e:
        logger.log(f"❌ Erro na cópia: {str(e)}", "ERROR")
        return False


def send_email_report(logger, overall_success, zip_created):
    """Envia relatório por e-mail com design melhorado"""
    logger.log("📧 ===== ENVIANDO RELATÓRIO =====")

    try:
        if SMTP_PASSWORD in ["sua_senha_aqui", "", "goeo ownj wcoz jijg"]:
            logger.log("⚠️ Configure SMTP_PASSWORD para receber relatórios", "WARNING")
            return False

        # Determinar status
        if overall_success and logger.errors == 0:
            status = "✅ SUCESSO COMPLETO"
            status_color = "#4CAF50"
            status_icon = "✅"
        elif logger.dmp_success > 0 and zip_created:
            status = "⚠️ SUCESSO PARCIAL"
            status_color = "#FF9800"
            status_icon = "⚠️"
        else:
            status = "❌ FALHA CRÍTICA"
            status_color = "#F44336"
            status_icon = "❌"

        # Calcular estatísticas adicionais
        duration_minutes = logger.get_duration() / 60
        success_rate = (logger.dmp_success / logger.dmp_total * 100) if logger.dmp_total > 0 else 0

        # Ler log - apenas as últimas 100 linhas para não sobrecarregar o e-mail
        try:
            with open(logger.log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                # Processar cada linha do log para melhor formatação
                formatted_log = []
                for line in lines[-100:]:  # Últimas 100 linhas
                    # Adicionar quebras de linha e estilos baseados no conteúdo
                    if "ERROR" in line:
                        formatted_line = f'<div style="color: #dc3545; margin-bottom: 2px;">{html.escape(line)}</div>'
                    elif "WARNING" in line:
                        formatted_line = f'<div style="color: #ffc107; margin-bottom: 2px;">{html.escape(line)}</div>'
                    elif "SUCCESS" in line or "✅" in line:
                        formatted_line = f'<div style="color: #28a745; margin-bottom: 2px;">{html.escape(line)}</div>'
                    else:
                        formatted_line = f'<div style="margin-bottom: 2px;">{html.escape(line)}</div>'
                    formatted_log.append(formatted_line)
                
                log_content = "".join(formatted_log)
        except Exception as e:
            log_content = f"<div style='color: #dc3545;'>Erro ao ler log: {html.escape(str(e))}</div>"

        # Criar mensagem
        msg = MIMEMultipart()
        msg["From"] = EMAIL_FROM
        msg["To"] = ", ".join(EMAIL_TO)  # Converte a lista em string separada por vírgulas
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = f"{status_icon} Backup Oracle - {status} - {datetime.now().strftime('%d/%m/%Y')}"

        # Template HTML moderno - SEÇÃO DO LOG ATUALIZADA
        body = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Relatório de Backup Oracle</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .header {{
                    background: linear-gradient(135deg, {status_color}, #2c3e50);
                    color: white;
                    padding: 25px;
                    border-radius: 10px;
                    text-align: center;
                    margin-bottom: 25px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .header p {{
                    margin: 10px 0 0;
                    opacity: 0.9;
                }}
                .card {{
                    background: white;
                    border-radius: 10px;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}
                .card h2 {{
                    color: #2c3e50;
                    margin-top: 0;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                .stat-box {{
                    background: #f8f9fa;
                    border-left: 4px solid {status_color};
                    padding: 15px;
                    border-radius: 5px;
                }}
                .stat-value {{
                    font-size: 24px;
                    font-weight: bold;
                    color: {status_color};
                }}
                .stat-label {{
                    font-size: 14px;
                    color: #6c757d;
                }}
                .progress-bar {{
                    height: 20px;
                    background: #e9ecef;
                    border-radius: 10px;
                    margin: 10px 0;
                    overflow: hidden;
                }}
                .progress-fill {{
                    height: 100%;
                    background: {status_color};
                    border-radius: 10px;
                    transition: width 0.3s ease;
                    width: {success_rate}%;
                }}
                .log-container {{
                    background: #2c3e50;
                    color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    max-height: 300px;
                    overflow-y: auto;
                    line-height: 1.4;
                }}
                .log-line {{
                    margin-bottom: 3px;
                    white-space: pre-wrap;
                    word-break: break-all;
                }}
                .success {{
                    color: #28a745;
                }}
                .warning {{
                    color: #ffc107;
                }}
                .error {{
                    color: #dc3545;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    color: #6c757d;
                    font-size: 12px;
                }}
                .icon {{
                    font-size: 18px;
                    margin-right: 5px;
                    vertical-align: middle;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{status_icon} Backup Oracle - {status}</h1>
                <p>{datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>
            </div>

            <div class="card">
                <h2>📊 Estatísticas do Backup</h2>
                
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-value">{logger.dmp_success}/{logger.dmp_total}</div>
                        <div class="stat-label">DMPs Criados</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{'✅' if zip_created else '❌'}</div>
                        <div class="stat-label">ZIP Criado</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{logger.warnings}</div>
                        <div class="stat-label">Avisos</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{logger.errors}</div>
                        <div class="stat-label">Erros</div>
                    </div>
                </div>

                <div>
                    <strong>Taxa de Sucesso:</strong> {success_rate:.1f}%
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                </div>

                <div>
                    <strong>Duração Total:</strong> {duration_minutes:.1f} minutos
                </div>
            </div>

            <div class="card">
                <h2>📋 Resumo da Execução</h2>
                <p><span class="icon success">✅</span> <strong>DMPs com sucesso:</strong> {logger.dmp_success}</p>
                <p><span class="icon warning">⚠️</span> <strong>Avisos detectados:</strong> {logger.warnings}</p>
                <p><span class="icon error">❌</span> <strong>Erros encontrados:</strong> {logger.errors}</p>
                <p><span class="icon">📦</span> <strong>Arquivo ZIP:</strong> {'Criado com sucesso' if zip_created else 'Falha na criação'}</p>
                <p><span class="icon">⏱️</span> <strong>Tempo de execução:</strong> {duration_minutes:.1f} minutos</p>
            </div>

            <div class="card">
                <h2>📝 Últimas Linhas do Log</h2>
                <div class="log-container">
                    {log_content}
                </div>
                <p><em>Mostrando as últimas 100 linhas. Log completo disponível em: {logger.log_file}</em></p>
            </div>

            <div class="footer">
                <p>Backup Oracle Automático • Sistema de backup desenvolvido por Isaac Carvalho</p>
                <p>💡 Este é um e-mail automático, por favor não responda.</p>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, "html", "utf-8"))

        # Enviar e-mail
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        logger.log("📧 E-mail enviado com sucesso!")
        return True

    except Exception as e:
        logger.log(f"❌ Falha no envio do e-mail: {str(e)}", "ERROR")
        logger.log(f"🔍 Detalhes do erro: {traceback.format_exc()}", "ERROR")
        return False
        
def validate_configuration(logger):
    """Valida configurações antes de iniciar"""
    logger.log("🔧 ===== VALIDANDO CONFIGURAÇÕES =====")

    issues = []

    # Verificar diretórios
    for name, path in [("DMPs", DB_FOLDER), ("Nuvem", CLOUD_FOLDER), ("Logs", LOG_DIR)]:
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                logger.log(f"✅ Diretório {name} criado: {path}")
            except Exception as e:
                issues.append(f"Erro ao criar {name}: {path}")
                logger.log(f"❌ Erro ao criar {name}: {e}", "ERROR")
        else:
            logger.log(f"✅ Diretório {name}: OK")

    # Verificar Oracle
    oracle_path = find_oracle_expdp()
    if oracle_path:
        logger.log(f"✅ Oracle expdp: {oracle_path}")
    else:
        issues.append("Oracle expdp não encontrado")
        logger.log("❌ Oracle expdp não encontrado", "ERROR")

    # Verificar usuários
    if not ORACLE_USERS:
        issues.append("Nenhum usuário Oracle configurado")
        logger.log("❌ Nenhum usuário Oracle configurado", "ERROR")
    else:
        logger.log(f"✅ {len(ORACLE_USERS)} usuários Oracle configurados")

    # Verificar espaço em disco
    for name, path in [("DMPs", DB_FOLDER), ("Nuvem", CLOUD_FOLDER)]:
        try:
            has_space, free_gb, total_gb, used_gb = check_disk_space(path, 5)
            if has_space:
                logger.log(f"💾 Espaço {name}: {free_gb:.1f}GB livre")
            else:
                issues.append(f"Pouco espaço em {name}: {free_gb:.1f}GB")
                logger.log(f"⚠️ Pouco espaço {name}: {free_gb:.1f}GB", "WARNING")
        except Exception as e:
            issues.append(f"Erro ao verificar espaço {name}")
            logger.log(f"❌ Erro espaço {name}: {e}", "ERROR")

    if issues:
        logger.log(f"⚠️ {len(issues)} problema(s) encontrado(s):", "WARNING")
        for issue in issues:
            logger.log(f"   • {issue}", "WARNING")
        return False
    else:
        logger.log("✅ Configurações validadas!")
        return True


def main():
    """Função principal"""
    logger = BackupLogger()
    overall_success = True
    zip_created = False

    try:
        logger.log("🚀 ===== BACKUP ORACLE DIÁRIO INICIADO =====")
        logger.log(f"⏰ Data/Hora: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}")
        logger.log(f"📅 Dia da semana: {get_weekday_name().title()}")

        # 1. Validar configurações
        if not validate_configuration(logger):
            logger.log("❌ Falhas na configuração - interrompendo", "ERROR")
            overall_success = False
            return 1

        # 2. Executar exports Oracle
        logger.log("\n🔄 Iniciando exports Oracle...")
        dmp_files = execute_oracle_exports(logger)

        if not dmp_files:
            overall_success = False
            logger.log("❌ Nenhum DMP gerado - falha crítica", "ERROR")
        else:
            logger.log(f"✅ {len(dmp_files)} DMP(s) gerado(s)")

            # 3. Compactar DMPs
            zip_path = create_daily_zip(dmp_files, logger)

            if zip_path:
                zip_created = True
                logger.log(f"✅ ZIP criado: {os.path.basename(zip_path)}")

                # 4. Copiar para nuvem
                if copy_to_cloud(zip_path, logger):
                    logger.log("✅ Copiado para nuvem")
                else:
                    overall_success = False
                    logger.log("❌ Falha na cópia para nuvem", "ERROR")

                # 5. Limpar arquivos antigos
                removed_count, removed_size = remove_old_files(logger)
                if removed_count > 0:
                    logger.log(f"🗑️ {removed_count} arquivos removidos ({removed_size:.1f}MB)")

            else:
                overall_success = False
                logger.log("❌ Falha na criação do ZIP", "ERROR")

        # Status final
        duration = logger.get_duration()
        logger.log("\n" + "=" * 50)
        logger.log("📊 ESTATÍSTICAS FINAIS:")
        logger.log(f"   ⏱️ Duração: {duration/60:.1f} min")
        logger.log(f"   🗄️ DMPs: {logger.dmp_success}/{logger.dmp_total}")
        logger.log(f"   📦 ZIP: {'✅' if zip_created else '❌'}")
        logger.log(f"   ⚠️ Avisos: {logger.warnings}")
        logger.log(f"   ❌ Erros: {logger.errors}")
        logger.log("=" * 50)

        if overall_success and logger.errors == 0:
            logger.log("🎉 BACKUP CONCLUÍDO COM SUCESSO!")
            return_code = 0
        elif zip_created and logger.dmp_success > 0:
            logger.log("⚠️ BACKUP CONCLUÍDO COM SUCESSOS PARCIAIS")
            return_code = 1
        else:
            logger.log("❌ BACKUP FALHOU")
            return_code = 2

    except KeyboardInterrupt:
        logger.log("⚠️ INTERROMPIDO PELO USUÁRIO", "WARNING")
        overall_success = False
        return_code = 130
    except Exception as e:
        overall_success = False
        logger.log(f"💥 ERRO CRÍTICO: {str(e)}", "ERROR")
        logger.log(f"🔍 Detalhes: {traceback.format_exc()}", "ERROR")
        return_code = 3

    finally:
        # Sempre tentar enviar relatório
        try:
            email_success = send_email_report(logger, overall_success, zip_created)
            if email_success:
                logger.log("📧 Relatório enviado")
            else:
                logger.log("⚠️ Relatório não enviado", "WARNING")
        except Exception as e:
            logger.log(f"💥 Erro no e-mail: {e}", "ERROR")

        # Status final
        status_map = {
            0: "✅ Sucesso completo",
            1: "⚠️ Sucesso parcial", 
            2: "❌ Falha crítica",
            3: "💥 Erro inesperado",
            130: "⚠️ Interrompido"
        }
        
        logger.log(f"\n🏁 FINALIZADO: {status_map.get(return_code, 'Desconhecido')} (código {return_code})")
        return return_code


def cleanup_and_exit(exit_code, logger=None):
    """Finalização forçada com limpeza completa"""
    try:
        if logger:
            logger.log(f"🔄 Finalizando processo com código {exit_code}")
        
        # Forçar flush de todos os outputs
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Tentar fechar arquivos de log abertos
        if logger and hasattr(logger, 'log_file'):
            try:
                # Força escrita final
                with open(logger.log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] 🏁 Processo finalizado - código {exit_code}\n")
                    f.flush()
                    os.fsync(f.fileno())  # Força sincronização com disco
            except:
                pass
        
        # Aguardar um momento para I/O finalizar
        import time
        time.sleep(1)
        
    except:
        pass  # Ignorar erros na finalização
    
    # Forçar saída
    os._exit(exit_code)

if __name__ == "__main__":
    logger_instance = None
    exit_code = 99
    
    try:
        # Garantir que estamos no diretório correto
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Executar backup
        exit_code = main()
        
        # Capturar logger se disponível
        if 'logger' in locals():
            logger_instance = logger
            
        print(f"\n🏁 Backup finalizado com código: {exit_code}")
        
        status_map = {
            0: "Sucesso completo",
            1: "Sucesso parcial", 
            2: "Falha crítica",
            3: "Erro inesperado",
            130: "Interrompido"
        }
        
        print(f"Status: {status_map.get(exit_code, 'Código desconhecido')}")
        
    except KeyboardInterrupt:
        print("\n⚠️ Backup interrompido pelo usuário")
        exit_code = 130
        
    except Exception as e:
        print(f"\n💥 Erro fatal durante execução: {e}")
        try:
            import traceback
            print(f"Detalhes: {traceback.format_exc()}")
        except:
            pass
        exit_code = 99
        
    finally:
        # Finalização forçada sempre
        cleanup_and_exit(exit_code, logger_instance)
