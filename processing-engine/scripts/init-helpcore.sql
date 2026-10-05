-- init-helpcore.sql
-- Inicialização do banco de dados Help Core para a instância PE dedicada.
--
-- IMPORTANTE: Este script é montado em /docker-entrypoint-initdb.d/init.sql
-- dentro do container pg-helpcore. O PostgreSQL EXECUTA este script APENAS
-- no primeiro boot (quando o data directory está vazio / volume vazio).
--
-- Se o volume hc-pgdata já existir, o script é IGNORADO silenciosamente.
-- Para recriar o banco do zero: make -f Makefile.helpcore down -v
-- (o flag -v remove os volumes nomeados e força re-execução no próximo boot)
--
-- O database processing_engine é criado automaticamente pelo POSTGRES_DB env var.
-- Este script cria o segundo database help_core.

\connect postgres

SELECT 'CREATE DATABASE help_core'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'help_core')\gexec
