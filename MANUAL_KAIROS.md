# Manual de Usuario — Kairos CRM
**Kairos Distribuidora · Guía completa del sistema**

---

## Índice

1. [Panel Principal (Dashboard)](#1-panel-principal)
2. [Leads](#2-leads)
3. [Pipeline (Kanban)](#3-pipeline)
4. [Campañas de Email y WhatsApp](#4-campañas)
5. [Mayoristas](#5-mayoristas)
6. [Catálogo de Productos](#6-catálogo-de-productos)
7. [Pedidos](#7-pedidos)
8. [Scraper y Enriquecimiento](#8-scraper-y-enriquecimiento)
9. [Consejos y flujo de trabajo recomendado](#9-flujo-recomendado)

---

## 1. Panel Principal

La pantalla de inicio muestra un resumen en tiempo real del negocio.

### Tarjetas de estadísticas
| Tarjeta | Qué muestra |
|---|---|
| Total Leads | Cantidad total de leads en la base |
| Clientes | Leads con estado "cliente" |
| Pedidos | Total de órdenes creadas |
| Productos | Productos en catálogo |

### Secciones del dashboard
- **Actividad del scraper** — muestra el último job: porcentaje de avance, productos encontrados y estado (corriendo / completado / error).
- **Tareas de hoy** — lista las tareas con fecha de vencimiento igual o anterior a hoy (con el nombre del lead asociado).
- **Pedidos recientes** — últimas 5 órdenes con monto y estado.
- **Stock bajo** — productos con menos de 5 unidades disponibles (configurable).

### Cómo interpretarlo
- Si el scraper muestra **error**, ir a la sección Scraper y hacer clic en **Cancelar job** para liberar el bloqueo antes de iniciar uno nuevo.
- Las tareas vencidas aparecen en rojo. Entrá al lead correspondiente para marcarlas como completadas o reprogramarlas.

---

## 2. Leads

### Acceder
Menú lateral → **Leads**

### Lista de leads
La tabla muestra empresa, ciudad, provincia, rubro, email, teléfono, score IA (0-10) y estado. Por defecto ordenada por fecha de creación (más recientes primero).

#### Filtros disponibles
| Filtro | Cómo usarlo |
|---|---|
| Empresa | Escribe parte del nombre |
| Provincia | Selecciona del desplegable |
| Ciudad | Texto libre |
| Rubro | Texto libre |
| Estado | Nuevo / Contactado / Interesado / Cliente / Descartado |
| Con email | Muestra solo los que tienen email registrado |
| Con teléfono | Muestra solo los que tienen teléfono |
| Score IA | Rango mínimo-máximo (0-10) |
| Tipo de cliente | Lead / Mayorista |

Hacé clic en **Aplicar filtros** para actualizar la tabla. Los filtros se acumulan (se aplican todos a la vez).

#### Paginación
Usa los botones de página en la parte inferior. El número de resultados por página es 50 (máximo 200).

#### Exportar CSV
Botón **Exportar CSV** en la esquina superior derecha. Descarga todos los leads que coincidan con los filtros actuales (hasta 10.000 filas).

#### Importar CSV
Botón **Importar CSV**. Sube un archivo `.csv` con columnas como `empresa`, `email`, `telefono`, `ciudad`, `provincia`, `rubro`. Los leads duplicados (mismo nombre de empresa) se omiten automáticamente.

---

### Detalle de un lead
Clic sobre cualquier fila para abrir el detalle.

#### Información de contacto (columna izquierda)
Muestra teléfono (clickeable para llamar), email (clickeable para redactar), sitio web, ubicación, rubro y fuente del lead.

#### Gestión
- **Estado**: cambia el estado del lead (Nuevo → Contactado → Interesado → Cliente → Descartado).
- **Score IA**: barra de progreso calculada automáticamente al crear el lead.
- **Observaciones**: notas internas libres. Clic en **Guardar Cambios** para confirmar.

#### Botones de acción (esquina superior derecha)
| Botón | Función |
|---|---|
| **Lista PDF** | Descarga la lista de precios personalizada para este lead en PDF |
| **Enviar por email** | Envía la lista de precios al email del lead (solo aparece si tiene email) |
| **Ver Pedidos** | Filtra la lista de pedidos por este lead |
| **Crear Pedido** | Abre el formulario de nuevo pedido pre-cargado con este lead |

#### Notas y actividad
Clic en **Nueva Nota** para agregar una anotación. Las notas aparecen en orden cronológico inverso y no se pueden eliminar (son un registro permanente de la relación).

**Casos de uso:**
- "Llamé, no atendió. Volver a llamar jueves."
- "Interesados en sahumerios, piden muestra."
- "Cliente confirmó pedido por WhatsApp."

#### Tareas / Follow-up
Clic en **Agregar tarea** para crear un recordatorio con fecha de vencimiento. Las tareas pendientes con fecha pasada aparecen en rojo.
- Tildá la casilla para marcar como completada.
- Las tareas vencidas de todos los leads también aparecen en el Dashboard.

#### Pedidos
Muestra todos los pedidos asociados al lead. Clic sobre uno para ver el detalle.

---

## 3. Pipeline

### Acceder
Menú lateral → **Pipeline**

Vista Kanban con 5 columnas: **Nuevo — Contactado — Interesado — Cliente — Descartado**.

### Cómo usar el Pipeline
- Cada tarjeta muestra el nombre de la empresa, ciudad, provincia y Score IA.
- **Arrastrar y soltar**: tomá una tarjeta y arrastrala a la columna correspondiente para cambiar el estado del lead. El cambio se guarda automáticamente.
- **Clic en la tarjeta**: no implementado — usá la vista de Lista de Leads para ver el detalle.
- Las flechas **← →** en la parte inferior de cada tarjeta permiten mover el lead de columna sin arrastrar.

### Para qué sirve
El Pipeline es ideal para revisar rápidamente qué leads están en cada etapa del proceso de venta y moverlos de forma visual.

---

## 4. Campañas

### Acceder
Menú lateral → **Campañas**

### Vista general
Muestra 4 métricas en tarjetas: total de campañas, emails enviados, tasa de apertura promedio y conversiones. Debajo, la tabla de campañas con nombre, tipo, estado, enviados, % apertura, % clicks y fecha.

---

### Crear una campaña

Clic en **Nueva Campaña**.

#### Paso 1: Configuración
1. **Nombre**: nombre interno para identificar la campaña (ej: "Promo Invierno Farmacias BA").
2. **Tipo**: Email o WhatsApp.
3. **Segmento de leads**:
   - Filtrá por provincia, rubro y estado de lead.
   - Activá "Solo leads con email" para campañas de email (recomendado).

#### Usar un template estacional
Antes de completar el paso 1, clic en el botón **Templates** (esquina superior derecha) para ver los templates predefinidos:

| Template | Ocasión |
|---|---|
| 🎄 Navidad | Diciembre — productos de regalo |
| 🎆 Año Nuevo | Enero — novedades del año |
| 💕 Día de los Enamorados | 14 de febrero — sets románticos |
| 👩 Día de la Madre | Octubre — regalos bienestar |
| 👨 Día del Padre | Junio — fragancias y relajación |
| 👫 Día del Amigo | 20 de julio — productos para compartir |
| 🌿 Promo General | Cualquier momento |

Al hacer clic en un template, el formulario se pre-carga con el asunto y texto del mensaje, saltando directo al paso 2 para que puedas editarlo.

#### Paso 2: Contenido

**Generar con IA**: clic en el botón con el ícono de chispa. La IA genera automáticamente:
- Asunto del email
- Cuerpo del mensaje (texto plano)
- Versión HTML
- **Mensaje de seguimiento a 3 días** (si el destinatario no abre el email)
- **Mensaje de seguimiento a 7 días** (cierre definitivo)

Podés editar cualquiera de estos textos antes de enviar.

**Variables personalizables en el texto:**
- `{empresa}` → se reemplaza con el nombre de la empresa del lead
- `{ciudad}` → ciudad del lead
- `{provincia}` → provincia del lead
- `{rubro}` → rubro del lead

Ejemplo: `Hola {empresa}, te contactamos desde Kairos...` → `Hola Farmacia Del Sol, te contactamos desde Kairos...`

#### Paso 3: Revisar y enviar
- Resumen del segmento y cantidad estimada de leads.
- Preview del mensaje.
- Si configuraste seguimientos, aparece una confirmación en azul.
- Clic en **Enviar Campaña**. El envío ocurre en segundo plano.

---

### Seguimiento automático (Follow-ups)

Cuando una campaña tiene textos de seguimiento configurados, el botón **"Enviar seguimientos"** en la página de Campañas procesa automáticamente:

1. Busca todos los emails enviados hace **más de 3 días** que **no fueron abiertos**.
2. Envía el mensaje de seguimiento (followup_1).
3. Busca los que recibieron el followup_1 hace **más de 7 días** y siguen sin responder.
4. Envía el mensaje de cierre (followup_2).

**Recomendación**: hacer clic en "Enviar seguimientos" una vez por semana o cada vez que se acumule una campaña enviada hace varios días.

---

### Reactivar clientes dormidos

Clic en **"Reactivar clientes"** para enviar un email de reactivación a todos los clientes (estado = "cliente") que **no hicieron un pedido en los últimos 30 días**.

El sistema:
1. Busca clientes con email que no tienen órdenes recientes.
2. Envía un email personalizado con el nombre de la empresa.
3. Muestra cuántos emails se encolaron.

---

### Seguimiento por WhatsApp

Clic en el botón verde **"Seguimiento WA"**.

En el diálogo:
1. **Selector de días**: elegí el período (1, 3, 7 o 14 días). Muestra los leads que recibieron un email pero no respondieron en ese tiempo.
2. **Lista de leads**: cada fila tiene el nombre de la empresa y el teléfono.
3. **Clic en una fila**: abre WhatsApp Web directamente con el mensaje pre-cargado.
4. **Abrir todos**: abre WhatsApp Web para todos los leads de la lista en pestañas nuevas (el navegador puede bloquear ventanas emergentes — autorizalas la primera vez).
5. **Copiar todos**: copia al portapapeles todos los nombres y links en formato texto.

---

### Duplicar una campaña
En la tabla de campañas, clic en el ícono de copiar (columna Acciones). Se crea una copia en estado "borrador" con todos los textos y configuración de la original.

---

### Ver detalle de una campaña
Clic en el nombre de la campaña o en el botón **Ver**. Muestra:
- Métricas detalladas (enviados, abiertos, clicks, tasa de apertura).
- Lista de todos los envíos individuales con estado (enviado / abierto / error).

---

## 5. Mayoristas

### Acceder
Menú lateral → **Mayoristas**

Sección independiente para gestionar clientes mayoristas. Funciona igual que Leads pero con `tipo_cliente = mayorista`.

- El scraper tiene un modo "Mayorista" que busca distribuidores y mayoristas en lugar de tiendas minoristas.
- Las listas de precios para mayoristas muestran los precios `precio_mayorista`.
- Los pedidos de mayoristas se pueden filtrar en la sección Pedidos.

---

## 6. Catálogo de Productos

### Acceder
Menú lateral → **Catálogo**

### Vista del catálogo
Tabla con nombre, categoría, precio minorista, precio mayorista, stock y estado (activo/inactivo).

#### Filtros
- Por nombre (búsqueda en tiempo real)
- Por categoría

#### Editar un producto
Clic sobre cualquier producto para abrir el formulario de edición. Campos editables:
- Nombre
- Categoría
- Precio minorista y mayorista
- Stock
- Descripción
- Estado activo/inactivo

#### Agregar un producto manualmente
Botón **+ Nuevo Producto** en la parte superior.

---

### Importar productos

#### Desde Kairosdis (scraper automático)
Clic en **Sincronizar Kairosdis**. El sistema extrae automáticamente los productos del catálogo de Kairosdis con nombres, precios y categorías. Tarda 1-2 minutos.

#### Desde Google Sheets
Clic en **Importar Google Sheets**. Ingresá el ID de la hoja (se encuentra en la URL de Google Sheets). El sistema importa los productos con sus precios.

#### Exportar CSV
Botón **Exportar CSV**. Descarga todos los productos en formato planilla.

---

### Exportar catálogo PDF

Botón **Exportar PDF** en la parte superior derecha.

**Modo "Todos los productos"** (por defecto):
- Genera un PDF con los 568 productos completos.
- Incluye imagen, nombre, código, categoría y precio.

**Modo "Selección manual"**:
- Activar el toggle "Seleccionar productos".
- Tildar los productos deseados de la página actual.
- Clic en **Exportar seleccionados**.

**Nota**: el PDF se genera en el servidor y puede tardar 10-30 segundos dependiendo de la cantidad de productos.

---

### Lista de precios personalizada

Cada lead puede recibir una lista de precios con sus precios específicos (mayoristas si es cliente mayorista o interesado, minoristas si no).

**Opciones para entregar la lista:**
1. **Descargar PDF**: en el detalle del lead, clic en **Lista PDF** — descarga inmediata en el navegador.
2. **Enviar por email**: en el detalle del lead, clic en **Enviar por email** — el sistema envía automáticamente un email vía Brevo con el link al PDF personalizado.

---

## 7. Pedidos

### Acceder
Menú lateral → **Pedidos**

### Lista de pedidos
Muestra número de orden, empresa (lead), estado, total y fecha. Filtros disponibles:
- Por empresa
- Por estado (Borrador / Confirmado / En preparación / Despachado / Entregado)
- Por fecha (rango desde-hasta)
- Por lead específico

---

### Crear un pedido

Clic en **+ Nuevo Pedido** o desde el detalle de un lead → **Crear Pedido**.

1. Seleccioná el lead (cliente) de la lista.
2. Agregá productos: clic en **Agregar producto**, elegí del desplegable (todos los 568 productos disponibles), ajustá cantidad y precio unitario.
3. Configurá fecha de entrega (opcional).
4. Ingresá un descuento si corresponde (en pesos).
5. Agrega notas de entrega en el campo "Notas de la Orden".
6. Clic en **Guardar**.

---

### Editar un pedido

Clic en cualquier pedido de la lista para abrir el detalle.

- Cambiá el estado con el desplegable (refleja el flujo de trabajo real).
- Editá productos: cambiar cantidad, precio o producto del desplegable.
- Agregá o eliminá líneas con + Agregar y el ícono de basura.
- Cambiá descuento y fecha de entrega.
- Clic en **Guardar** para confirmar.

El total se calcula automáticamente: subtotal de productos menos descuento.

---

### Generar factura PDF

En el detalle de un pedido, clic en **Factura PDF**. El sistema genera un PDF con:
- Datos del cliente (empresa, dirección)
- Número de orden
- Listado de productos con cantidades y precios
- Subtotal, descuento y total
- Fecha de emisión

---

### Clientes dormidos

En la sección Campañas → **Reactivar clientes** para enviar emails a los clientes que no hicieron pedidos en los últimos 30 días. Ver sección 4 para más detalle.

---

## 8. Scraper y Enriquecimiento

### Acceder
Menú lateral → **Scraper**

El Scraper busca automáticamente nuevos clientes potenciales en Google Maps Argentina.

---

### Iniciar un scraping

#### Modo Leads (tiendas minoristas)
Clic en **Iniciar Scraper (Leads)**. Busca tiendas holísticas, de sahumerios, dietéticas, spas, etc. en todas las provincias de Argentina.

#### Modo Mayoristas
Clic en **Iniciar Scraper (Mayoristas)**. Busca distribuidores y mayoristas de sahumerios, aromaterapia e incienso.

**El scraper:**
1. Realiza búsquedas en Google Maps con 15-20 queries predefinidas.
2. Obtiene datos de cada negocio: nombre, dirección, teléfono, website, rating, cantidad de reseñas.
3. Inserta solo los registros que no existían previamente (deduplicación por nombre).
4. Al completarse, **inicia automáticamente el proceso de enriquecimiento** si encontró leads nuevos con websites.

**Tiempo estimado**: 5-15 minutos dependiendo de la cantidad de queries.

---

### Enriquecimiento de emails

El enriquecimiento visita el sitio web de cada lead y extrae:
- Email de contacto (de formularios, footer, páginas de contacto)
- Teléfono adicional
- Instagram
- WhatsApp

**Iniciar enriquecimiento manual**: clic en **Enriquecer emails** para procesar todos los leads con website pero sin email.

**Automático**: se ejecuta automáticamente al terminar el scraper.

---

### Monitorear el progreso

La barra de progreso y el porcentaje se actualizan en tiempo real. También se muestra:
- **Encontrados**: total de negocios procesados desde Google Maps.
- **Nuevos**: negocios efectivamente agregados a la base (sin duplicados).

---

### Historial de jobs

La tabla inferior muestra todos los jobs anteriores con:
- Tipo (scraper / enriquecimiento)
- Estado (completado / error / corriendo)
- Fecha de inicio y fin
- Cantidad de nuevos leads agregados
- Error (si falló)

---

### Cancelar un job atascado

Si el scraper quedó en estado "corriendo" por más de 20 minutos sin avanzar, el sistema lo cancela automáticamente al iniciar el próximo job. También podés cancelarlo manualmente:

1. Localizá el job en la tabla de historial.
2. Clic en el ícono de stop (cuadrado rojo).
3. El estado cambia a "error" y se libera el bloqueo para iniciar uno nuevo.

---

## 9. Flujo de trabajo recomendado

### Rutina semanal

```
Lunes
  → Dashboard: revisar tareas vencidas y pedidos pendientes
  → Campañas → "Enviar seguimientos" (procesa follow-ups automáticos)

Martes / Miércoles
  → Leads: revisar leads nuevos del scraper, asignar tareas
  → Pipeline: mover leads avanzados a "Interesado" o "Cliente"

Jueves
  → Campañas → "Seguimiento WA" (contactar por WhatsApp los no respondidos)
  → Pedidos: actualizar estados de órdenes en curso

Viernes
  → Catálogo: actualizar precios si corresponde
  → Scraper → iniciar nuevo scraping si la base necesita más leads
```

---

### Flujo de conversión de un lead

```
1. NUEVO (recién creado por el scraper)
      ↓
2. CONTACTADO (enviaste una campaña o llamaste)
      ↓
3. INTERESADO (respondió o mostró interés)
   — Enviar lista de precios por email desde el detalle del lead
   — Crear una tarea de seguimiento con fecha
      ↓
4. CLIENTE (confirmó un pedido)
   — Crear pedido desde el detalle del lead
   — Generar factura PDF
      ↓
Seguimiento continuo:
   — Usa "Reactivar clientes" si no pide en 30+ días
   — Envía catálogo actualizado periódicamente
```

---

### Ciclo de campañas de email

```
1. Crear campaña (con IA o template estacional)
2. Enviar → el sistema envía emails en segundo plano
3. Esperar 3 días → clic "Enviar seguimientos" (llega followup_1 a no-abrieron)
4. Esperar 7 días → clic "Enviar seguimientos" (llega followup_2 al resto)
5. Para los que tienen teléfono: usar "Seguimiento WA" para contacto final
6. Los que convirtieron: cambiar estado a "Cliente" y crear pedido
```

---

### Consejos rápidos

- **Score IA alto (7-10)**: lead con website, teléfono, email y buenas reseñas — priorizalos para campañas.
- **El scraper solo corre 1 job a la vez**. Si da error al iniciar, esperá que el job anterior termine o cancelalo manualmente.
- **Los templates estacionales** están pensados para fechas clave. Usalos 2-3 semanas antes de la fecha.
- **Los follow-ups automáticos** solo funcionan en campañas creadas con la opción "Generar con IA" (que genera los textos de seguimiento) o si completaste manualmente los campos de seguimiento.
- **Lista de precios por email**: solo funciona si el lead tiene un email registrado (si no tiene, el botón no aparece).
- **Catálogo PDF completo**: siempre elegí "Todos los productos" para que el PDF incluya los 500+ productos, no solo la página actual.

---

*Manual actualizado: Junio 2026 — Kairos CRM v2.0*
