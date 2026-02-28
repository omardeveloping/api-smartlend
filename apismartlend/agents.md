## Smartlend Agents Guide

### Overview
- Django REST backend with three main apps: `usuarios` (auth, roles, careers, directors), `inventario` (catalog, stock, physical tools), `operaciones` (prestamos, alertas).
- Authentication uses custom `Usuario` with `correo` as username. There is password login, a bodeguero-only password login, and face login.
- The business flow separates `prestamo` creation from physical delivery. A loan can exist in `Pendiente` without any real tools assigned yet.
- `tipo_herramienta.stock` is derived data: real available tools minus the quantity currently `reservado`.
- Physical traceability happens at `herramienta_individual` level through stable `codigo_barras` values. Loan codes and barcode codes are different things.

### Business Actors
- `usuario`: requests tools and is the owner of the `prestamo`. The user should think in terms of requested `tipo_herramienta` and quantities, not individual barcodes.
- `bodeguero`: performs the physical handoff and return. The bodeguero is the actor that scans `codigo_barras` values to assign or receive real tools.
- Recommended mental model: the user creates or owns the request, and the bodeguero confirms reality in the warehouse.
- The codebase also supports a practical variant where the bodeguero can create the loan on behalf of the user, but the physical assignment and return still belong to the bodeguero flow.

### Key Models
- `usuarios.Usuario`: custom auth model keyed by `correo`; stores `rut`, names, role, career, face embedding, and ban flags (`esta_baneado`, `baneado_en`, `aviso_ban_enviado`).
- `usuarios.rol_usuarios`: role catalog. `login-bodeguero` explicitly checks that the authenticated user role name is `bodeguero`.
- `usuarios.DirectorCarrera`: one director per `carrera`; used for overdue-ban notification emails.
- `inventario.tipo_herramienta`: logical catalog entry with `nombre`, `descripcion`, `imagen`, `stock`, and `reservado`.
- `inventario.herramienta_individual`: physical unit with stable `codigo_barras`, condition (`estado_herramienta`), `disponible`, and FK to `tipo_herramienta`.
- `inventario.historial_herramienta`: audit record written on successful return with tool, condition, timestamp, loan, and user.
- `operaciones.prestamo`: core business object. Current states are `Pendiente`, `Expirado`, `Entregado`, `Finalizado`, `Vencido`, `Cancelado`.
- `operaciones.PrestamoTipoHerramienta`: requested tool types and quantities for a loan.
- `operaciones.prestamoHerramienta`: real assignment table between a loan and individual tools.
- `operaciones.alerta`: one-to-one alert per overdue loan, with `criticidad`, resolution flags, and archive flag.

### Important State Semantics
- `Pendiente`: the loan exists, requested types were validated, and virtual stock was reserved, but no real tools have been handed out yet.
- `Expirado`: 30 minutes passed and the loan was still pending; virtual reservation is released.
- `Entregado`: the bodeguero scanned and assigned the exact physical tools required by the loan.
- `Finalizado`: all assigned tools were returned and `fecha_devolucion_real` was stored.
- `Vencido`: the expected return date passed and Celery marked the loan as overdue.
- `Cancelado`: defined in the model but there is no clear current custom endpoint flow that uses it.
- Important correction: there is no `Activo` state in the current model code.

### Core Flow
1) **Crear préstamo**
   - Endpoint: `POST /operaciones/api/prestamos/`
   - Input includes `id_usuario`, dates, and `tipos` like `[{"tipo_herramienta": <id>, "cantidad": <int>}]`.
   - The serializer validates each requested type and checks free stock as `disponibles reales - reservado actual`.
   - On success it creates the loan in `Pendiente`, writes `PrestamoTipoHerramienta`, increments `reservado`, schedules expiration in 30 minutes, and sends an email with the loan code.
   - At this point no physical `herramienta_individual` has been assigned yet.

1.1) **Crear reserva docente**
   - Endpoint: `POST /operaciones/api/prestamos/reserva-docente/`
   - Intended for users whose role is `Docente`.
   - Requires `fecha_inicio_reserva` for tomorrow and the same `tipos` structure used by normal loans.
   - Internally this still creates a `prestamo` in `Pendiente`, but with future start time and delayed expiration window.

2) **Buscar préstamo para entrega**
   - Endpoint: `GET /operaciones/api/prestamos/buscar/?codigo=ABC`
   - This uses the loan `codigo`, not the tool barcode.
   - Current code only returns loans in `Pendiente` or `Entregado`.

3) **Entregar herramientas reales**
   - Endpoint: `POST /operaciones/api/prestamos/{id}/asignar_herramientas/`
   - Input is `{"codigos": ["BAR1", "BAR2"]}` where each value is a physical tool `codigo_barras`.
   - The action validates that every barcode exists, is still available, and matches the requested types and quantities exactly.
   - On success it releases the virtual reservation, marks the scanned tools `disponible=False`, links them to the loan, and moves the loan from `Pendiente` to `Entregado`.

4) **Devolver herramientas**
   - Endpoint: `POST /operaciones/api/prestamos/{id}/devolver_herramientas/`
   - Input is `{"codigos": [...], "estados": {"BAR1": "Bueno"}}`; `estados` is optional.
   - The request must include every tool currently associated with the loan. Returns are all-or-nothing in the current implementation.
   - The endpoint updates optional tool condition, marks each tool `disponible=True`, writes `historial_herramienta`, stores `fecha_devolucion_real`, and changes the loan to `Finalizado`.

5) **Vencimiento y sanciones**
   - `expirar_prestamo_pendiente`: if 30 minutes pass and the loan is still `Pendiente`, the task changes it to `Expirado` and releases the virtual reservation.
   - `ban_overdue_prestamos`: if `fecha_devolucion_esperada` passed and the loan is still open, it marks it `Vencido`, escalates alert severity, emails the student at higher severity levels, and bans the user after 20 days.

### Stock and Barcode Rules
- `codigo` on `prestamo` is the operation code used to find the loan.
- `codigo_barras` on `herramienta_individual` is the stable physical identifier of the tool. It should remain the same for that tool across loans.
- Creating a loan does not mark physical tools unavailable. It only reserves quantity at type level through `reservado`.
- Physical availability changes only when the bodeguero assigns or receives actual tools.

### API Surface
- `usuarios/api/`
  - `roles`
  - `usuarios`
  - `usuarios/{id}/historial-prestamos/`
  - `usuarios/{id}/prestamos-activos/`
  - `usuarios/{id}/estado-bloqueo/`
  - `usuarios/{id}/dashboard-bodeguero/`
  - `carreras`
  - `directores`
- `usuarios/auth/`
  - `login-bodeguero/`: password login restricted to role `bodeguero`
  - `login-usuario/`: generic password login for any role
  - `login/`: face login
  - `register-face/`: face registration/update by `rut`
- `inventario/api/`
  - `tipos-herramienta`
  - `tipos-herramienta/resumen/`
  - `categorias-herramienta`
  - `herramientas`
  - `historial-herramientas`
- `operaciones/api/`
  - `prestamos`
  - `prestamos/reserva-docente/`
  - `prestamos/buscar/`
  - `prestamos/pendientes/`
  - `prestamos/vencidos/`
  - `prestamos/{id}/asignar_herramientas/`
  - `prestamos/{id}/devolver_herramientas/`
  - `alertas`
  - `alertas/no-archivadas/`
  - `reportes/inventario/`
  - `reportes/prestamos/`
  - `reportes/morosos/`

### Operational Notes
- `Celery` is required for business correctness, not just background convenience. Without it, pending loans do not expire automatically and overdue loans do not become `Vencido` automatically.
- `GET /operaciones/api/alertas/` has side effects: it creates or resolves alerts based on current overdue status.
- `vencidos/` is date-driven: a loan can appear overdue by date even before the Celery task has updated its explicit state to `Vencido`.
- There is no separate active `reserva` model in the current code path. Teacher reservations are implemented as future `prestamo` records through `prestamos/reserva-docente/`.
- Report endpoints return JSON by default and can export files with `?formato=pdf` or `?formato=excel`.
- There is a legacy `id_herramienta_individual` field in `prestamo`, but current multi-tool logic relies on `tipos_prestamo` plus the many-to-many assignment through `prestamoHerramienta`.
- `tipo_herramienta.stock` and inventory summary views are related but not identical concepts; some views derive availability from active-loan annotations rather than directly from `reservado`.
- If you change anything in loan behavior, review together:
  - `operaciones/models.py`
  - `operaciones/serializers.py`
  - `operaciones/views.py`
  - `operaciones/tasks.py`
  - `inventario/models.py`

### Common Misunderstandings to Avoid
- Creating a loan is not the same as delivering tools.
- The user-facing loan code is not the same as a tool barcode.
- A pending loan is still a real loan in the system, even if no physical tool has been scanned yet.
- A loan does not become `Vencido` just because time passed in the database; the Celery overdue task has to run and persist that state change.
