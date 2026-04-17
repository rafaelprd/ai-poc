# AI

## Purpose

Help AI agents understand and extend the system.

## Core Concepts

-   Transactions are immutable except category edits
-   Data pipeline is batch-oriented
-   Source of truth: database

## Coding Rules

-   Always normalize data before saving
-   Never trust input formats
-   Use idempotent operations

## Architecture

-   Backend: FastAPI
-   Frontend: Vue3 + Vite + shadcn
-   Database: PostgreSQL

## Naming Conventions

-   snake_case (backend)
-   camelCase (frontend)

## Key Entities

-   Transaction
-   Category
-   Import
-   Account

## AI Usage

-   Categorization suggestions
-   Anomaly detection
