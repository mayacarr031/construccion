-- =============================================================
-- Script de Inicialización para MariaDB
-- Este archivo se ejecuta automáticamente si se monta en:
-- /docker-entrypoint-initdb.d/init.sql
-- =============================================================

CREATE DATABASE IF NOT EXISTS db_sentimientos;
USE db_sentimientos;

CREATE TABLE IF NOT EXISTS tweets (
    id_tweet INT PRIMARY KEY,
    entity VARCHAR(255) NOT NULL,
    sentiment_real VARCHAR(50) NOT NULL,
    tweet_text TEXT NOT NULL,
    sentiment_prediction VARCHAR(50) NULL,
    confidence FLOAT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
