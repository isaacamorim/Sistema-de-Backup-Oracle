# Sistema-de-Backup-Oracle
Este é um sistema automatizado de backup para bancos de dados Oracle que realiza exportações (expdp), compacta os arquivos, copia para um diretório de rede e envia relatórios por e-mail.

Documentação do Sistema de Backup Oracle
📋 Visão Geral
Este é um sistema automatizado de backup para bancos de dados Oracle que realiza exportações (expdp), compacta os arquivos, copia para um diretório de rede e envia relatórios por e-mail.

🎯 Funcionalidades Principais
Exportação de múltiplos schemas Oracle usando expdp

Compactação dos backups em arquivos ZIP

Cópia para diretório de rede/cloud

Limpeza automática de backups antigos

Sistema de logging detalhado

Relatórios por e-mail com estatísticas

Verificação de espaço em disco

Validação de configurações

⚙️ Configuração
Variáveis de Configuração Principais
python
# Diretórios
DB_FOLDER = r"C:\DMP_DIR"  # Pasta local dos arquivos DMP
CLOUD_FOLDER = r"\\10.42.92.192\Diversos\Eduardo\Backup"  # Pasta de rede
LOG_DIR = r"C:\DMP_DIR\Logs"  # Pasta de logs

# Configurações Oracle
ORACLE_DIRECTORY = "DMP_DIR"  # Nome do directory no Oracle
ORACLE_SERVICE = "ORCL"  # Nome do serviço Oracle

# Usuários para backup
ORACLE_USERS = [
    {"user": "HORIZONTE", "password": "LARANJA", "schema": "HORIZONTE"},
    {"user": "SYSALL", "password": "LEGEND", "schema": "SYSALL"},
    {"user": "IMG_HORIZONTE", "password": "LARANJA", "schema": "IMG_HORIZONTE"},
]

# Configurações de e-mail
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "seu_email@gmail.com"
SMTP_PASSWORD = "sua_senha_app"  # Usar App Password do Gmail
EMAIL_FROM = "email_remetente@gmail.com"
EMAIL_TO = ["destinatario1@email.com", "destinatario2@email.com"]
Política de Retenção
python
RETENTION_DAYS = 10  # Mantém 10 dias para margem de segurança
KEEP_MINIMUM_BACKUPS = 2  # Sempre mantém pelo menos 2 backups recentes
MAX_TOTAL_BACKUPS = 7  # Máximo de backups simultâneos
🚀 Como Executar
Execução Manual
bash
python backup_oracle.py
Agendamento no Windows (Task Scheduler)
Abrir Task Scheduler

Criar uma tarefa básica

Configurar para executar diariamente no horário desejado

Ação: "Iniciar um programa"

Programa/script: python.exe

Argumentos: C:\caminho\para\backup_oracle.py

Configurar para executar com usuário com permissões adequadas

📊 Fluxo de Execução
Validação de Configuração

Verifica diretórios

Verifica acesso ao Oracle

Verifica espaço em disco

Exportação dos Schemas

Executa expdp para cada usuário configurado

Gera arquivos .DMP com nome baseado no dia da semana

Timeout diferenciado por schema (3h para IMG_HORIZONTE, 1h para outros)

Compactação

Cria arquivo ZIP com todos os DMPs

Usa compactação ZIP_DEFLATED com nível 6

Cópia para Nuvem

Copia ZIP para diretório de rede

Verifica integridade da cópia

Limpeza

Remove arquivos DMP antigos (exceto do dia atual)

Mantém apenas os backups mais recentes baseado na política

Relatório

Envia e-mail com status detalhado

Inclui estatísticas e log resumido

📧 Modelo de E-mail de Relatório
O relatório inclui:

Status geral (Sucesso Completo, Sucesso Parcial ou Falha Crítica)

Estatísticas de execução

Gráfico de progresso

Log das últimas 100 linhas

Duração total do processo

🔍 Solução de Problemas
Erros Comuns
Oracle expdp não encontrado

Verificar se Oracle Client está instalado

Verificar variável de ambiente ORACLE_HOME

Falha de autenticação

Verificar usuário/senha do Oracle

Verificar permissões do usuário

Espaço insuficiente

Verificar espaço livre nos diretórios DB_FOLDER e CLOUD_FOLDER

Falha de rede

Verificar conectividade com diretório de rede

Verificar permissões de acesso

Logs
Os logs são armazenados em C:\DMP_DIR\Logs\backup_completo_YYYY-MM-DD.log e são automaticamente limpos após 30 dias.

🔒 Segurança
As senhas são ocultadas nos logs

Recomenda-se usar App Passwords para e-mail

Considerar usar variáveis de ambiente para credenciais sensíveis

📝 Personalização
Adicionar Novos Schemas
Adicione novos usuários à lista ORACLE_USERS:

python
ORACLE_USERS.append({"user": "NOVO_USUARIO", "password": "SENHA", "schema": "NOVO_SCHEMA"})
Modificar Política de Retenção
Ajuste as variáveis:

python
MAX_TOTAL_BACKUPS = 10  # Manter mais backups
RETENTION_DAYS = 14     # Manter por mais tempo
Alterar Configurações de E-mail
Modifique as variáveis SMTP e destinatários conforme necessário.

📞 Suporte
Em caso de problemas:

Verificar logs em C:\DMP_DIR\Logs\

Verificar se todos os diretórios existem e têm permissões adequadas

Testar conectividade com o diretório de rede

Testar configuração de e-mail separadamente

📋 Códigos de Saída
0: Sucesso completo

1: Sucesso parcial (com avisos)

2: Falha crítica

3: Erro inesperado

130: Interrompido pelo usuário

Este sistema fornece uma solução robusta e automatizada para backup de bancos Oracle com monitoramento completo através de e-mails e logs detalhados.

*Documentação gerada em 09/09/2025 para o Sistema de Backup Oracle*
