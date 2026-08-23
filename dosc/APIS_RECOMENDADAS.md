# 🔌 Mapa de Ruta de APIs: Agentes Existentes y Futuros

Este documento detalla el ecosistema de APIs recomendadas para potenciar los agentes de la **Agencia de Marketing MCP**. Las APIs están estructuradas por agente, clasificadas en opciones **Gratis (o con Capa Gratuita)** y de **Pago (Premium/Profesionales)**, permitiendo escalar el sistema desde el desarrollo local hasta una operación comercial masiva.

---

## 🗺️ Índice
1. [Agentes Existentes (Ecosistema Actual)](#1-agentes-existentes-ecosistema-actual)
   - [Investigador de Identidad Corporativa](#investigador-de-identidad-corporativa)
   - [Auditor de Huella Digital para PYMES](#auditor-de-huella-digital-para-pymes)
   - [Analista de Competencia Local](#analista-de-competencia-local)
   - [Estratega Supervisor (Orquestador)](#estratega-supervisor-orquestador)
2. [Agentes Futuros (Estructura de Expansión)](#2-agentes-futuros-estructura-de-expansión)
   - [Auditor Técnico y SEO Web](#auditor-técnico-y-seo-web)
   - [Estratega de Contenido y Estética Social](#estratega-de-contenido-y-estética-social)
   - [Auditor de Campañas Publicitarias (Ads Auditor)](#auditor-de-campañas-publicitarias-ads-auditor)
   - [Auditor de Canales de Conversión (WhatsApp & CRM)](#auditor-de-canales-de-conversión-whatsapp--crm)
3. [Resumen de Costos y Estrategia de Implementación](#3-resumen-de-costos-y-estrategia-de-implementación)

---

## 1. Agentes Existentes (Ecosistema Actual)

### Investigador de Identidad Corporativa
* **Misión:** Rastrear menciones, reputación de marca, noticias y presencia en directorios web generales.
* **Estado actual:** Usa búsquedas simples en SerpAPI o Serper en [servidor_mcp.py:L381-438](file:///c:/Users/angel/Desktop/Proyectos/agen_mrk/servidor_mcp.py#L381-438).

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **DuckDuckGo Search API (Python)** | Scraping directo y gratuito de resultados web orgánicos. | **100% Gratis** (Sin API Key, propenso a límites si se satura). |
| **Gratis** | **Serper.dev (Organic)** | Búsquedas en Google super rápidas para encontrar menciones de la marca. | **2,500 búsquedas gratis** al registrarse. Luego muy barato ($1 USD por 1,000 búsquedas). |
| **Gratis** | **NewsAPI** | Busca menciones del negocio en periódicos y blogs digitales locales. | **100 peticiones diarias gratis** (Solo uso no comercial). |
| **Pago** | **SerpAPI (Google Search)** | Búsquedas altamente personalizables simulando ubicaciones geográficas exactas. | Capa gratuita de 100 búsquedas/mes. Planes desde **$75 USD/mes** para uso intensivo. |
| **Pago** | **Brand24 API** | Monitorización profesional de menciones de marca en redes, foros y blogs. | Prueba de 14 días. Planes desde **$79 USD/mes**. Ideal para clientes grandes (Upsell). |

---

### Auditor de Huella Digital para PYMES
* **Misión:** Auditar técnicamente perfiles de Google Maps, Instagram, Facebook y verificar la existencia de canales clave.
* **Estado actual:** Usa llamadas básicas de Google Places/SerpAPI y HTTP GET simples propensos a bloqueos en [servidor_mcp.py:L261-319](file:///c:/Users/angel/Desktop/Proyectos/agen_mrk/servidor_mcp.py#L261-319).

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **Google Places API** | Obtiene detalles de contacto, rating, coordenadas, teléfono y si tiene web. | **$200 USD de crédito gratis al mes** por parte de Google Cloud (suficiente para ~10,000 consultas básicas). |
| **Gratis** | **Apify (Free Credits)** | Plataforma donde corren los mejores scrapers para evadir muros de login en Meta. | **$5 USD gratis al mes** (suficiente para correr ~500 búsquedas de perfiles de Instagram/mes). |
| **Pago** | **Apify - Instagram Profile Scraper** | Extrae número de seguidores, posts totales, fecha de último post (actividad) y tasa de interacción (engagement). | Pago por uso (aprox. **$0.005 USD** por perfil auditado con los créditos de Apify). |
| **Pago** | **Apify - Facebook Page Scraper** | Extrae número de me gusta, seguidores, posts recientes y las últimas opiniones escritas por clientes en FB. | Pago por uso (aprox. **$0.008 USD** por página auditada). |
| **Pago** | **Outscraper (Google Maps & Contacts)** | API premium especializada en raspar Google Maps y extraer emails públicos del negocio. | **$0.003 USD** por negocio auditado. |

---

### Analista de Competencia Local
* **Misión:** Identificar y evaluar a los 3 mejores competidores locales en la misma categoría y ciudad para crear un reporte comparativo.
* **Estado actual:** Realiza búsquedas de mapas locales y genera comparativas rudimentarias.

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **Google Places API (Nearby Search)** | Busca negocios del mismo rubro en un radio geográfico determinado. | Incluido en los **$200 USD de crédito gratuito** mensual de Google Cloud. |
| **Gratis** | **Serper.dev (Maps Engine)** | Obtiene listados de competidores locales con sus ratings promedio. | Consume del saldo de **2,500 búsquedas gratis**. |
| **Pago** | **Apify - Google Maps Scraper** | Scrapea en masa competidores con todo su historial de reseñas, fotos y horarios para comparaciones ultra detalladas. | Pago por uso (aprox. **$0.05 USD** por búsqueda de zona/competidor). |

---

### Estratega Supervisor (Orquestador)
* **Misión:** Analizar toda la información de los agentes anteriores, calcular el Score definitivo y estructurar el reporte final JSON para venta técnica y comercial.
* **Estado actual:** Ejecuta LLM locales mediante Ollama o modelos cloud en [agente.py:L28-61](file:///c:/Users/angel/Desktop/Proyectos/agen_mrk/agente.py#L28-61).

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **Ollama (Llama 3.1 8B / Qwen 2.5 7B)** | Ejecución 100% local del cerebro del agente. Excelente para pruebas y desarrollo. | **100% Gratis y Privado** (Requiere hardware decente con GPU). |
| **Gratis** | **Groq API** | Acceso a LLMs en la nube (Llama 3.1 70B) a velocidades extremas. Ideal para un formateo JSON perfecto sin costo. | **Capa gratuita extremadamente generosa** con límites de RPM/TPM. |
| **Pago** | **OpenAI API (GPT-4o-mini)** | Modelo ultra inteligente, rápido y económico para garantizar que el JSON de salida no contenga errores de parseo. | Pago por uso (aprox. **$0.002 USD** por reporte generado debido a su bajo costo de tokens). |
| **Pago** | **Anthropic API (Claude 3.5 Sonnet)** | El mejor modelo del mundo para redacción comercial y análisis estratégico de marketing. | Pago por uso (aprox. **$0.04 USD** por reporte generado; ideal para la fase final del PDF). |

---

## 2. Agentes Futuros (Estructura de Expansión)

Para transformar la agencia en una solución de marketing integral de alta gama, se proponen los siguientes 4 agentes adicionales:

### Auditor Técnico y SEO Web
* **Misión:** Analizar a fondo el sitio web del cliente (si tiene) evaluando velocidad, SEO técnico on-page, optimización móvil y accesibilidad.
* **Valor para la Agencia:** Vender servicios de Rediseño Web, SEO Mensual y Optimización de Velocidad.

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **Google PageSpeed Insights API** | API oficial de Google. Devuelve métricas de Lighthouse (Core Web Vitals), rendimiento móvil, errores de SEO y velocidad. | **100% Gratis** (Hasta 25,000 peticiones diarias). **¡Altamente recomendada!** |
| **Gratis** | **Python Requests / Beautiful Soup** | Permite parsear el `robots.txt`, buscar si tiene instalado el píxel de Facebook/Google Analytics y verificar la jerarquía de tags H1, H2, H3. | **100% Gratis** (Ejecutado de forma nativa por el agente). |
| **Pago** | **SEMrush API / Ahrefs API** | Auditoría profunda de palabras clave posicionadas del cliente, tráfico estimado mensual y enlaces rotos. | Requiere planes premium corporativos (desde **$120 USD/mes**). Solo recomendable en agencias consolidadas. |
| **Pago** | **Whois XML API** | Verifica la antigüedad del dominio del cliente y su fecha de expiración para alertarle si está por vencer. | 500 consultas gratis al mes. Luego planes de pago. |

---

### Estratega de Contenido y Estética Social
* **Misión:** Analizar visual y textualmente las últimas 10 publicaciones de las redes sociales del cliente para calificar su branding y proponer un calendario editorial de 30 días.
* **Valor para la Agencia:** Vender servicios de "Social Media Management" y Creación de Contenido.

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **Instagram Graph API (Meta)** | API oficial de Facebook/Instagram. Permite leer legalmente estadísticas de cuentas comerciales del cliente. | **100% Gratis** (Requiere que el cliente dé de alta tu app en su panel de Meta Business). |
| **Pago** | **Apify - Instagram Post Scraper** | Extrae las imágenes, captions (copys), hashtags, likes y comentarios de las últimas publicaciones del cliente de forma externa. | Pago por uso (aprox. **$0.01 USD** por perfil auditado). |
| **Pago** | **OpenAI GPT-4o / Claude 3.5 (Vision)** | Permite que el agente "vea" y analice la estética visual de las imágenes/videos recopilados (evaluar colores de marca, tipografías y calidad gráfica). | Pago por uso (aprox. **$0.02 USD** por imagen analizada con visión de IA). |

---

### Auditor de Campañas Publicitarias (Ads Auditor)
* **Misión:** Investigar si el cliente o sus competidores están invirtiendo dinero en anuncios digitales y auditar la calidad técnica de sus campañas activas.
* **Valor para la Agencia:** Vender servicios de Trafficking / Media Buying (Meta Ads, Google Ads).

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **Facebook Ads Library API** | API oficial de Meta para consultar qué anuncios están activos en tiempo real para cualquier negocio. | **100% Gratis** (Requiere verificar tu cuenta de desarrollador en Meta). |
| **Pago** | **Apify - Facebook Ads Library Scraper** | Extrae de forma limpia todos los anuncios activos (imágenes, textos, fechas de inicio) sin pasar por el complejo proceso de validación oficial de Meta. | Pago por uso (aprox. **$0.03 USD** por negocio consultado). **La mejor opción para agilidad técnica.** |

---

### Auditor de Canales de Conversión (WhatsApp & CRM)
* **Misión:** Evaluar si el negocio tiene un proceso automatizado para atender leads. Prueba los enlaces de WhatsApp, simula una conversación de prueba para medir tiempos de respuesta y audita si tienen un CRM activo.
* **Valor para la Agencia:** Vender Automatizaciones con Make/n8n, creación de Chatbots con IA y configuración de CRMs (ej. Kommo o ActiveCampaign).

| Tipo | API / Herramienta | Capacidad / Utilidad | Costo / Capa Gratuita |
| :--- | :--- | :--- | :--- |
| **Gratis** | **Python HTTP Validation** | Script local para verificar si los enlaces de WhatsApp (`wa.me`) del cliente son válidos y están bien construidos. | **100% Gratis** (Lógica nativa). |
| **Pago** | **Evolution API / Twilio** | Permite enviar un mensaje de prueba automático de forma controlada y medir exactamente cuántos minutos (u horas) tarda el negocio en responder. | Requiere servidor propio (Evolution API es Open Source, Twilio cobra **$0.0085 USD** por mensaje). |

---

## 3. Resumen de Costos y Estrategia de Implementación

### 📈 Tabla Comparativa de Costo de Operación (Por Auditoría)

Si decides implementar el flujo con APIs premium para lograr resultados 100% profesionales y precisos:

| Concepto | Proveedor Recomendado | Costo Promedio por Cliente Auditado |
| :--- | :--- | :--- |
| **Google Maps & Competidores** | Google Places API | $0.00 USD (Cubre la capa de $200 gratis) |
| **Scraping de Redes (IG/FB)** | Apify | $0.015 USD |
| **Auditoría de Velocidad/SEO** | Google PageSpeed | $0.00 USD (Totalmente gratis) |
| **Cerebro del Supervisor** | OpenAI GPT-4o-mini | $0.002 USD |
| **Total Estimado por Auditoría** | | **~$0.017 USD (Menos de 1 centavo de dólar)** |

### 🚀 Recomendación de Plan de Acción para la Agencia

1. **Fase 1: Implementar de Inmediato (Costo $0 USD)**
   * Integra **Google PageSpeed Insights API** en un nuevo script para auditar sitios web. Es gratis y aporta un valor técnico inmenso en el reporte final.
   * Utiliza la capa gratuita de **Apify** ($5 USD/mes) para sustituir las búsquedas rudimentarias de Instagram de tu `servidor_mcp.py` por el actor `apify/instagram-profile-scraper`.
   * Usa **Groq** o **Ollama** local para procesar las auditorías iniciales de prueba.

2. **Fase 2: Escalamiento Comercial (Costo Variable Mínimo)**
   * Cuando lances tu campaña de prospección en frío (lote de 100 negocios):
     * Carga tu cuenta de **Apify** con $10 USD para procesar el lote sin riesgo de límites.
     * Utiliza **GPT-4o-mini** de OpenAI para garantizar que el análisis de las reseñas reales de Google Maps y las métricas de redes sociales se resuma en un JSON robusto y estructurado.
     * Cobrarás estos costos (que son ínfimos, menos de $2 USD por lote de 100) del primer cliente cerrado por tu estrategia de prospección.
