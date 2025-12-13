## Smartlend Agents Guide

### Overview
- Django REST backend with three apps: `usuarios` (auth/roles), `inventario` (tool catalog + stock), `operaciones` (prestamos/reservas/alertas).
- Authentication: custom `Usuario` uses `correo` as username; face login endpoints also available.
- Stock model: `tipo_herramienta.stock` auto-updates from `herramienta_individual` marked `disponible=True`.
- Loans (`prestamo`) support multiple `tipo_herramienta` with quantities and real tool assignment/return flows for bodeguero.

### Key Models
- `inventario.tipo_herramienta`: nombre/descripcion/imagen; `stock` recalculated from available individuales.
- `inventario.herramienta_individual`: `codigo_barras`, `estado_herramienta`, `disponible`, FK to tipo.
- `inventario.historial_herramienta`: tracks estado/disponibilidad changes on return (herramienta, estado, timestamp, prestamo, usuario).
- `operaciones.prestamo`: estados (`Pendiente`, `Activo`, `Entregado`, `Finalizado`, `Expirado`, `Vencido`, `Cancelado`), fechas, código autogenerado + email, tipos solicitados (`tipos_prestamo` through), herramientas asignadas (through `prestamoHerramienta`).
- `usuarios`: `rol_usuarios`, `carrera`, `Usuario`, `DirectorCarrera`.

### Core Flows
1) **Crear préstamo (frontend)**  
   - POST `/operaciones/api/prestamos/` with `tipos` list `[{"tipo_herramienta": <id>, "cantidad": <int>}, ...]` plus fechas, usuario.  
   - Validates stock per tipo, reserves real herramientas (marks `disponible=False`), saves `tipos_prestamo`.  
   - Schedules Celery `expirar_prestamo_pendiente` (30 min) to mark `Expirado` if still `Pendiente`.  
   - Sends email with código + requested tipos/cantidades and 30-minute pickup warning.

2) **Asignar herramientas (bodeguero entrega)**  
   - POST `/operaciones/api/prestamos/{id}/asignar_herramientas` with `{"codigos": ["BAR1", ...]}`.  
   - Checks all barcodes exist, are disponibles, and match requested tipos/cantidades exactly; assigns them, marks `disponible=False`, sets estado to `Activo`.

3) **Buscar préstamo por código**  
   - GET `/operaciones/api/prestamos/buscar/?codigo=ABC` (matches `Pendiente/Activo/Entregado`).
   - GET `/operaciones/api/prestamos/pendientes/` to list pending; `/vencidos/` for overdue.

4) **Devolver herramientas (bodeguero recepción)**  
   - POST `/operaciones/api/prestamos/{id}/devolver_herramientas` with `{"codigos": ["BAR1", ...], "estados": {"BAR1": "Bueno"}}` (estados optional).  
   - Requires all loan herramientas; updates optional estado_herramienta, marks `disponible=True`, writes `historial_herramienta`, sets estado to `Finalizado` and `fecha_devolucion_real` to now.

5) **Alertas y bans automáticos (Celery)**  
   - `expirar_prestamo_pendiente`: expires pending loan after 30 minutes, releasing tools.  
   - `ban_overdue_prestamos`: marks loans Vencido after due date, escalates alerts, emails students/directors, and bans users after 20 days.

### API Surface (routers)
- `usuarios/api/`: `roles`, `usuarios`, `carreras`, `directores`; auth: `/usuarios/auth/login-bodeguero/`, `/usuarios/auth/login/` (face), `/usuarios/auth/register-face/`.
- `inventario/api/`: `tipos-herramienta`, `categorias-herramienta`, `herramientas`.
- `operaciones/api/`: `prestamos` (with custom actions above), `reservas`, `alertas`.

### Operational Notes
- Migrations needed for `historial_herramienta` and other recent model changes.  
- Celery worker must be running to enforce expirations and overdue bans.  
- Stock is enforced at creation/update; assignment/return endpoints are atomic to avoid partial writes.
