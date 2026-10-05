# Praxis — FDS Layout & Configuration Generator

> Plataforma desktop *No-Code* para design de layouts, configuração de racks/cubículos e geração automatizada de pacotes de diagnóstico para o Frauscher Diagnostic System (FDS).

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![No Code](https://img.shields.io/badge/Workflow-No--Code-orange?style=for-the-badge)](#)
[![Impact](https://img.shields.io/badge/Time_Saved-90%25-brightgreen?style=for-the-badge)](#-impacto-e-resultados)

---
<img width="1396" height="920" alt="Screenshot 2026-10-05 173251" src="https://github.com/user-attachments/assets/3e82572c-3d28-4c8e-8475-683130c5f8fc" />

## Sobre o Praxis

O **Praxis** foi concebido para revolucionar o fluxo de trabalho de configuração de racks e cubículos do **FDS (Frauscher Diagnostic System)**. 

Anteriormente, o processo exigia a edição manual e suscetível a erros de arquivos XML complexos, além de testes empíricos via mídias físicas (pendrives) direto no equipamento. Com o Praxis, engenheiros e técnicos conseguem montar visualmente a disposição dos elementos e gerar, com um clique, os arquivos estruturados necessários.

---

## Impacto e Resultados

* **Redução Drástica no Tempo de Entrega:** O processo de configuração que costumava levar cerca de **1 mês** (incluindo correções e testes) foi reduzido para apenas **2 dias**.
* **Ganho de Eficiência de ~90%:** Eliminação do ciclo entediante de tentativa e erro manual.
* **Zero-Error Deployment:** Mecanismo de validação em tempo real que impede a exportação de configurações inválidas ou inconsistentes.
* **Abordagem No-Code:** Permite que especialistas de domínio configurem e validem sistemas complexos sem a necessidade de escrever uma única linha de código XML.

---

<img width="1395" height="926" alt="Screenshot 2026-10-05 173259" src="https://github.com/user-attachments/assets/da39ca50-2f71-49ca-abc3-7bfff0370e3e" />

## Principais Funcionalidades

* **Editor de Layout e Racks:** Interface visual interativa para arranjo e personalização de cubículos dentro do rack do FDS.
* **Geração Automática de Artefatos:**
  * `FDS Config.xml` — Arquivo de parâmetros e regras de sistema.
  * `Track Plan.xml` — Mapeamento do plano de vias e elementos de campo.
* **Pacote de Recuperação (`FDS Recovery.zip`):** Empacotamento automático dos arquivos XML gerados e validados, prontos para importação direta no equipamento FDS.
* **Validador Embutido (Preventive Validation):** 
  * Verificação rigorosa antes do salvamento/exportação.
  * Alertas visuais e impedimento de geração de arquivos inconsistentes.
  * Feedback imediato durante o processo de design (visualize se está correto enquanto programa).

---

<img width="1407" height="938" alt="Screenshot 2026-10-05 173321" src="https://github.com/user-attachments/assets/d412f39c-24bd-4653-ba17-e60b197c34e9" />

Arquitetura e Engenharia

O projeto foi construído focando em modularidade e integridade dos dados:

```text
Praxis/
├── core/           # Motor de validação e regras de negócio de hardware/cubículos
├── layout/         # Gerenciamento de elementos visuais do rack e plano de vias
├── generators/     # Gerador de esquemas XML (FDS Config & Track Plan) e compactação ZIP
└── gui/            # Interface gráfica do usuário
