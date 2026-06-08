# Guía de Uso — Kairos CRM

Manual completo del sistema para el equipo de Kairos Distribuidora.

---

## Índice

1. [Dashboard](#1-dashboard)
2. [Leads](#2-leads)
3. [Mayoristas](#3-mayoristas)
4. [Pipeline de Ventas](#4-pipeline-de-ventas)
5. [Campañas](#5-campañas)
6. [Órdenes](#6-órdenes)
7. [Catálogo de Productos](#7-catálogo-de-productos)
8. [Scraper de Leads](#8-scraper-de-leads)

---

## 1. Dashboard

**Ruta:** `/` (pantalla de inicio)

El Dashboard es la vista general del negocio. Al entrar al sistema siempre arrancás acá.

### Qué vas a ver

| Tarjeta | Qué muestra |
|---|---|
| Total Leads | Cantidad total de contactos en la base |
| Con Email | Cuántos leads tienen email registrado |
| Sin Email | Cuántos leads faltan enriquecer (en rojo si son más de 500) |
| Clientes | Leads que ya pasaron a estado "cliente" |
| Revenue del Mes | Facturación acumulada del mes en curso |
| Tareas Vencidas | Seguimientos pendientes — aparece en rojo si hay alguno |
| Productos | Total de productos cargados en el catálogo |

Hacé click en cualquier tarjeta para ir directamente a la sección correspondiente.

### Gráficos

- **Leads por Provincia (top 8):** barras con la distribución geográfica de la base.
- **Leads por Estado (torta):** porcentaje de leads en cada etapa del embudo.
- **Embudo de Leads:** progresión visual de nuevo → contactado → interesado → cliente.
- **Últimos Leads agregados:** lista rápida de los 8 más recientes con link al detalle.
- **Órdenes por Mes:** línea de actividad comercial mensual.
- **Revenue por Mes:** barras de facturación en ARS.

### Importar catálogo desde Kairosdis

En la parte inferior del Dashboard aparece la preview del catálogo. El botón **"Importar Kairosdis"** descarga automáticamente todos los productos de kairosdis.com.ar y los agrega al catálogo. Mientras corre, muestra el progreso en tiempo real. No hace falta ir al Catálogo para lanzar esta importación.

---

## 2. Leads

**Ruta:** `/leads`

Esta es la base de datos principal de prospectos y clientes minoristas. Cada lead es una tienda, local o emprendedor que puede comprarle a Kairos.

### Cómo navegar la lista

- **Buscar:** escribí el nombre de la empresa en el campo de búsqueda.
- **Filtrar por Provincia:** desplegable con todas las provincias presentes en la base.
- **Filtrar por Rubro:** tipo de negocio (tienda holística, sahumerios, etc.).
- **Filtrar por Estado:** nuevo / contactado / interesado / cliente / descartado.
- **Solo con email:** toggle para ver únicamente leads que tienen email — útil antes de lanzar una campaña.
- **Solo con teléfono:** toggle para filtrar los que tienen número disponible.

Los resultados se muestran de a 50 por página. Usá los botones Anterior / Siguiente para navegar.

### Ver el detalle de un lead

Hacé click en cualquier fila o en el botón **"Ver"** para abrir la ficha completa del lead. Desde ahí podés:

- Editar todos los datos (empresa, teléfono, email, Instagram, WhatsApp, dirección).
- Cambiar el estado manualmente.
- Ver y agregar notas de seguimiento.
- Crear una orden directamente para ese lead.

### Cambiar el estado de un lead

Desde la lista podés cambiar el estado sin abrir el detalle: hacé click en el desplegable de la columna **Estado** directo en la fila. Los estados son:

- **Nuevo** — recién ingresado, sin contacto todavía.
- **Contactado** — se le mandó un email o se lo llamó.
- **Interesado** — mostró interés, está en conversación.
- **Cliente** — ya realizó al menos un pedido.
- **Descartado** — no corresponde seguir.

### Score IA

Cada lead tiene un puntaje del 0 al 10 calculado automáticamente según la información disponible:

- Verde (7–10): lead completo y de alta calidad.
- Amarillo (4–6): lead parcial, falta enriquecer.
- Rojo (0–3): lead muy incompleto.

### Acciones masivas (selección múltiple)

Marcá varios leads con el checkbox del lado izquierdo. Al seleccionar al menos uno, aparece una barra flotante en la parte inferior de la pantalla con estas acciones:

#### Enviar Email
1. Seleccioná los leads deseados.
2. Hacé click en **"Email"** en la barra flotante.
3. Opcional: presioná **"Generar con IA en español"** para que el sistema redacte automáticamente el asunto y el cuerpo según el segmento seleccionado.
4. Editá el texto como quieras. Podés usar `{empresa}` en el cuerpo para personalizar con el nombre de cada lead.
5. Hacé click en **"Enviar"**.

> El envío de emails requiere que Brevo (ex Sendinblue) esté configurado en el servidor.

#### Enviar por WhatsApp
1. Seleccioná los leads con teléfono registrado.
2. Hacé click en **"WhatsApp"** en la barra flotante.
3. Escribí el mensaje.
4. Hacé click en **"Generar Links"**.
5. Se genera una lista de links wa.me — hacé click en cada uno para abrir el chat directamente en WhatsApp.

#### Enviar Catálogo
1. Seleccioná los leads.
2. Hacé click en **"Catálogo"** en la barra flotante.
3. El sistema prepara automáticamente un email con el link al catálogo público.
4. Editá el mensaje si querés y hacé click en **"Enviar"**.

### Exportar leads a CSV

Botón **"Exportar CSV"** en la parte superior derecha. Exporta exactamente los leads que están filtrados en ese momento (si filtrás por provincia Buenos Aires, solo exporta esos).

### Importar leads desde CSV

Botón **"Importar CSV"** en la parte superior derecha.

- El archivo debe tener encabezados en la primera fila.
- Columnas reconocidas: `empresa` / `nombre`, `telefono`, `email`, `ciudad`, `provincia`, `rubro`, `website`.
- Los duplicados (mismo nombre de empresa) se omiten automáticamente.
- Acepta archivos exportados desde Excel (UTF-8 o con BOM).

---

## 3. Mayoristas

**Ruta:** `/mayoristas`

Funciona igual que la sección de Leads pero filtra únicamente los contactos de tipo **mayorista** (distribuidores, importadores, proveedores). La lógica de estados, score y acciones es idéntica a Leads.

Para agregar mayoristas a la base podés lanzar el scraper desde acá con las queries predefinidas de distribuidores (el botón **"Iniciar Scraper"** en la parte superior).

---

## 4. Pipeline de Ventas

**Ruta:** `/pipeline`

Vista tipo tablero Kanban con todos los leads organizados en columnas por estado. Es la forma más visual de gestionar el avance comercial.

### Las 5 columnas

| Columna | Color | Descripción |
|---|---|---|
| Nuevo | Gris | Lead recién ingresado |
| Contactado | Azul | Ya recibió un primer contacto |
| Interesado | Amarillo | Está en conversación activa |
| Cliente | Verde | Compra confirmada |
| Descartado | Rojo | Fuera del embudo |

### Mover leads entre columnas

Cada tarjeta tiene botones de flecha:
- **`<`** — retrocede el lead a la etapa anterior.
- **`>`** — avanza el lead a la siguiente etapa.
- **`✕`** — descarta el lead directamente.

El cambio se guarda en tiempo real. También podés hacer click en la tarjeta para abrir el detalle completo del lead.

### Score visible en el Pipeline

Cada tarjeta muestra el score IA del lead para priorizar con quién seguir primero.

---

## 5. Campañas

**Ruta:** `/campaigns`

Gestión de campañas de email marketing y seguimiento por WhatsApp.

### Panel de métricas

En la parte superior mostrá 4 indicadores:

- **Total Campañas:** cuántas campañas existen en total.
- **Emails Enviados:** volumen acumulado de todos los envíos.
- **Tasa de Apertura Promedio:** promedio de apertura entre todas las campañas.
- **Conversiones:** leads que pasaron a estado cliente tras una campaña.

### Crear una nueva campaña

1. Hacé click en **"Nueva Campaña"** (botón superior derecho).
2. Completá el nombre, tipo (email / WhatsApp) y el segmento de destinatarios.
3. Escribí o generá el contenido con IA.
4. Programá el envío o lanzalo al instante.

### Ver el detalle de una campaña

Hacé click en cualquier fila de la tabla para ver métricas detalladas: enviados, abiertos, clicks, y la lista de destinatarios.

### Duplicar una campaña

El ícono de copiar (dos cuadraditos) en la columna Acciones duplica la campaña con todos sus parámetros. Útil para reutilizar una campaña exitosa con un segmento diferente.

### Seguimiento por WhatsApp

El botón **"Seguimiento WA"** muestra todos los leads a los que se les envió un email hace más de 3 días y todavía no respondieron. Genera links wa.me para contactarlos con un seguimiento rápido sin tener que buscarlo uno por uno.

---

## 6. Órdenes

**Ruta:** `/orders`

Gestión de pedidos desde que se generan hasta que se entregan. La vista es un tablero Kanban con 5 etapas.

### Etapas de una orden

| Etapa | Descripción |
|---|---|
| Borrador | Orden cargada pero sin confirmar |
| Confirmado | El cliente confirmó el pedido |
| En Preparación | El pedido está siendo armado |
| Despachado | Fue enviado al cliente |
| Entregado | Recibido y cerrado |

### Crear una nueva orden

1. Hacé click en **"Nueva Orden"**.
2. Seleccioná el cliente (lead) en el desplegable — busca dentro de todos los leads.
3. Seleccioná el producto y la cantidad. Podés agregar varios productos con **"+ Agregar producto"**.
4. El precio mayorista se muestra al lado de cada producto para referencia.
5. Hacé click en **"Crear Orden"**.

La orden aparece automáticamente en la columna **Borrador**.

### Avanzar el estado de una orden

Hacé click en la tarjeta de la orden para abrir el detalle. Desde ahí podés cambiar la etapa y ver el resumen de productos y monto total.

### Ver órdenes de un cliente específico

Desde el detalle de un lead hay un acceso directo a sus órdenes. También podés filtrar por `lead_id` en la URL: `/orders?lead_id=123`.

---

## 7. Catálogo de Productos

**Ruta:** `/catalog`

El catálogo centraliza todos los productos con sus precios, stock e imágenes.

### Filtrar por categoría

En la parte superior hay chips de categorías: aceites esenciales, difusores, cristales, kits, etc. Hacé click en uno para filtrar. **"Todos"** muestra el catálogo completo.

### Agregar un producto manualmente

1. Hacé click en **"Agregar Producto"** (botón superior derecho).
2. Cargá la imagen arrastrando un archivo o haciendo click en el área de imagen (se redimensiona automáticamente a máximo 800px).
3. Completá:
   - **Nombre** (obligatorio)
   - **Categoría**
   - **Descripción**
   - **Precio Minorista** — precio de venta al público
   - **Precio Mayorista** — precio de venta a revendedores
   - **Stock** — unidades disponibles
4. Activá **"Activo"** para que aparezca en el catálogo público.
5. Activá **"Destacado"** (estrella) para que aparezca primero en la grilla.
6. Hacé click en **"Crear"**.

### Editar un producto o cambiar precios

1. Hacé click en el ícono de lápiz (✏️) en la esquina superior derecha de la tarjeta del producto.
2. Modificá los campos que necesitás (nombre, precios, stock, imagen, etc.).
3. Hacé click en **"Guardar"**.

Para actualizar precios en masa, usá la opción **Sync desde Sheet** (ver más abajo).

### Activar / Desactivar un producto

El toggle en la parte inferior de cada tarjeta activa o desactiva el producto. Un producto inactivo aparece con opacidad reducida y no se muestra en el catálogo público.

### Marcar como Destacado

El ícono de estrella en la tarjeta lo marca como destacado. Los destacados aparecen con un ícono dorado en la esquina.

### Importar productos desde Kairosdis

El botón **"Importar Kairosdis"** scrapea automáticamente kairosdis.com.ar y sincroniza todos los productos (nombre, precio, imágenes). Mientras corre muestra el porcentaje de avance. Al terminar informa cuántos productos son nuevos y cuántos fueron actualizados.

### Sincronizar precios desde Google Sheets

El botón **"Sync desde Sheet"** lee la planilla oficial de Google Sheets del catálogo y aplica los cambios de precios, stock y estado directamente al sistema. Es la forma más rápida de actualizar precios en masa.

#### Cómo preparar la planilla — paso a paso

1. En el Catálogo, hacé click en **"Exportar CSV"** (botón superior derecho).
2. Abrí el archivo CSV descargado en Excel o Google Sheets.
3. Si usás Google Sheets: **Archivo → Importar → Subir** el CSV.
4. Editá los valores que querés cambiar en estas columnas:

| Columna | Qué hace |
|---|---|
| **ID** | Identificador del producto — **no lo modifiques nunca** |
| **Precio Minorista** | Precio de venta al público (ARS) |
| **Precio Mayorista** | Precio de venta a revendedores (ARS) |
| **Precio Promo** | Precio promocional opcional (ARS) |
| **Stock** | Unidades disponibles (número entero) |
| **Activo** | `Sí` para visible / `No` para oculto |

5. Una vez editada, la planilla debe estar **compartida como "Cualquiera con el link puede ver"**:
   - En Google Sheets: click en "Compartir" → "Cambiar a cualquiera con el link" → rol "Lector".
6. Volvé al CRM, sección Catálogo, y hacé click en **"Sync desde Sheet"**.
7. El sistema informa cuántos productos fueron actualizados y cuántos no tuvieron cambios.

> **Importante:** el sistema identifica cada producto por su columna **ID**. No borres ni modifiques esa columna o el sync no podrá hacer la correspondencia.

> **Qué NO se actualiza por Sheet:** nombre, descripción, imagen, categoría. Para cambiar esos datos hay que editar el producto manualmente.

### Exportar el catálogo

- **Exportar PDF:** abre un diálogo donde podés elegir el título del PDF y seleccionar qué productos incluir (todos o una selección). Al confirmar descarga el PDF listo para enviar a clientes.
- **Exportar CSV:** descarga todos los productos en formato CSV compatible con Excel.

### Notificar clientes

El botón **"Notificar Clientes"** envía automáticamente un email con el link al catálogo público a todos los leads que están en estado "cliente". Muestra cuántos emails fueron encolados.

---

## 8. Scraper de Leads

**Ruta:** `/scraper`

El scraper busca automáticamente negocios potenciales en Google Places y los agrega a la base de leads. También tiene un enriquecedor que extrae emails y datos de contacto de los sitios web de los leads.

### Lanzar el Scraper de Google Places

1. Hacé click en **"Iniciar Scraper"**.
2. El sistema lanza búsquedas predefinidas: "sahumerios Argentina", "tienda holística Buenos Aires", "santería Córdoba", etc. (20 queries para leads minoristas).
3. Una barra de progreso muestra el avance query por query en tiempo real.
4. Al finalizar, el log muestra cuántos leads nuevos fueron encontrados y agregados.

Solo puede correr un job a la vez. Si intentás lanzar otro mientras hay uno corriendo, el sistema lo bloquea.

### Lanzar el Scraper para Mayoristas

Desde la sección **Mayoristas** el botón "Iniciar Scraper" usa un set diferente de queries enfocado en distribuidores, importadores y mayoristas: "distribuidor sahumerios Argentina", "mayorista productos holísticos", etc.

### Enriquecer leads con email

El botón **"Enriquecer con Email"** toma todos los leads que tienen website pero no tienen email, entra a cada sitio web y extrae:

- Email de contacto (desde mailto:, JSON-LD, footer, etc.)
- Instagram
- WhatsApp
- Teléfono

El proceso es automático y muestra progreso en tiempo real. Cuanto más leads tengas sin email, más tarda (es normal — visita cada sitio web uno por uno).

### Historial de jobs

La tabla inferior muestra todos los trabajos anteriores con:
- Fecha y hora de inicio y fin.
- Estado (completado / error / corriendo / pendiente).
- Total encontrados y nuevos agregados.
- Mensaje de error si el job falló.

Podés cancelar un job en curso con el botón **"Cancelar"** en la fila del job activo.

### Detener un job en curso

Mientras corre un scraper o un enriquecimiento, aparece un botón **"Detener"** que cancela el proceso de forma limpia, guardando los leads que ya se procesaron.

---

## Flujo recomendado de trabajo

Este es el flujo típico desde cero hasta cerrar una venta:

```
1. Scraper        →  Buscar nuevos leads en Google Places
2. Enriquecedor   →  Extraer emails de los sitios web
3. Leads          →  Revisar, filtrar y priorizar por score
4. Campañas       →  Enviar email o catálogo al segmento elegido
5. Pipeline       →  Mover leads de "contactado" a "interesado"
6. Seguimiento WA →  Hacer seguimiento a los que no respondieron
7. Órdenes        →  Crear la orden cuando el cliente confirma
8. Catálogo       →  Mantener precios y stock actualizados
```

---

## Preguntas frecuentes

**¿Puedo usar el sistema desde el celular?**
Sí. El diseño es responsivo. En pantallas chicas la tabla de leads se convierte en tarjetas apiladas y el Pipeline / Órdenes scrollean horizontalmente.

**¿Cómo actualizo los precios de muchos productos a la vez?**
Usá **Sync desde Sheet** en el Catálogo. Actualizá los precios en la planilla de Google Sheets y sincronizá con un click.

**¿Qué pasa si el scraper se cuelga?**
Tiene un timeout automático de 30 minutos. Si supera ese tiempo sin actividad, el job se marca como fallido automáticamente. También podés cancelarlo manualmente desde el historial.

**¿El scraper agrega duplicados?**
No. Antes de insertar un lead, verifica que no exista ya una empresa con el mismo nombre y tipo de cliente.

**¿Cómo sé si un email llegó?**
Desde el detalle de una campaña podés ver las métricas de enviados, abiertos y clicks. Para el tracking de aperturas es necesario que Brevo esté configurado correctamente.

**¿Cómo le mando el catálogo a un cliente puntual?**
Desde Leads, seleccioná ese lead, hacé click en **"Catálogo"** en la barra flotante, y enviá el email con el link. También podés exportar el PDF desde el Catálogo y adjuntarlo manualmente.
