# api-smartlend

Backend Django para gestion de herramientas y autenticacion facial (InsightFace) pensado para ejecutarse con Postgres o SQLite.

## Requisitos previos
- Python 3.13 (o 3.10+) y `pip`/`venv` para correr sin contenedores.
- Docker y Docker Compose si prefieres contenedores.
- PostgreSQL 17 si usas la base externa (por defecto puede usar SQLite).
- Dependencias del sistema para InsightFace/OpenCV (si instalas sin Docker): `build-essential cmake python3-dev libopenblas-dev liblapack-dev libjpeg-dev zlib1g-dev libgl1 libglib2.0-0`.
- La primera ejecucion de InsightFace descarga el modelo `buffalo_l`; necesitas internet o un cache previo.

## Variables de entorno
Crear un `.env` en la raiz de `apismartlend/` (el mismo nivel de `manage.py`):
```
SECRET_KEY=tu_clave_django
FACE_ENCRYPTION_KEY=clave_fernet_base64  # python - <<'PY'\nfrom cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\nPY
DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_LOGLEVEL=info
# Config DB (Postgres)
DATABASE_ENGINE=postgresql
DATABASE_NAME=smartlend
DATABASE_USERNAME=smartlend
DATABASE_PASSWORD=smartlend
DATABASE_HOST=localhost   # usa "db" si levantas docker compose
DATABASE_PORT=5432
# Opcional: duplica SECRET_KEY en DJANGO_SECRET_KEY si usas compose tal cual
DJANGO_SECRET_KEY=${SECRET_KEY}
```
Si no defines `DATABASE_*` usara SQLite en `polls`. El codigo lee `SECRET_KEY`; la variable `DJANGO_SECRET_KEY` del compose no se usa salvo que la iguale a `SECRET_KEY`.

## Instalacion local (sin Docker)
1) Crear entorno virtual: `python -m venv .venv && source .venv/bin/activate` (en Windows `.\.venv\Scripts\activate`).  
2) Instalar dependencias del sistema (solo Linux, ver lista arriba).  
3) Instalar Python deps: `pip install --upgrade pip && pip install -r requirements.txt`.  
4) Definir variables: `export $(grep -v '^#' .env | xargs)` o configurarlas en tu shell.  
5) Preparar base de datos: `python manage.py migrate`.  
6) (Opcional) Crear superusuario para admin: `python manage.py createsuperuser`.  
7) Ejecutar: `python manage.py runserver 0.0.0.0:8000`.

## Ejecucion con Docker Compose
1) Crea `.env` como arriba (usa `DATABASE_HOST=db`).  
2) Construye y levanta: `docker compose up --build`.  
   - `entrypoint.sh` aplica migraciones, colecta estaticos y lanza Gunicorn en `0.0.0.0:8000`.  
3) Accede en `http://localhost:8000`. El volumen monta el codigo para desarrollo.

## Que hace cada parte del proyecto
- `apismartlend/` (config): `settings.py` define apps (`usuarios`, `inventario`, `operaciones`), CORS, Whitenoise, base de datos y rutas en `urls.py`.
- `usuarios/`: modelo de usuario custom (`Usuario`) con identificacion por `correo`, roles (`rol_usuarios`) y carreras. Incluye gestion de embeddings faciales:
  - `face_utils.FaceProcessor` usa InsightFace para extraer embedding y lo cifra con Fernet (`FACE_ENCRYPTION_KEY`). Comparacion por norma con umbral 0.35.
  - Endpoints REST: `/usuarios/api/roles/`, `/usuarios/api/usuarios/` (CRUD).  
  - Endpoints de rostro: `POST /usuarios/auth/register-face/` recibe imagen + datos basicos y guarda embedding cifrado; `POST /usuarios/auth/login/` recibe imagen o embedding y devuelve coincidencia.  
  - Admin: `usuarios/admin.py` expone Usuario y roles en el admin de Django.
- `inventario/`: modelos de categorias, tipos de herramienta y herramientas individuales con codigos de barra. Endpoints REST en `/inventario/api/` (CRUD via viewsets).
- `operaciones/`: reservas y prestamos vinculados a usuarios y herramientas. Endpoints REST en `/operaciones/api/` (CRUD via viewsets).
- `tools/convert_image.py`: script CLI para convertir imagenes a RGB (JPEG/PNG), util si InsightFace rechaza formatos.  
- `check_image.py`: script de prueba con `face_recognition` para inspeccionar una imagen local.  
- Infra: `Dockerfile` multi-stage instala deps nativos y Python; `compose.yml` levanta Postgres 17 + web; `entrypoint.sh` migra/colecta estaticos y ejecuta Gunicorn.

## Operaciones tipicas
- Cargar datos base (roles, carreras, categorias) via admin (`/admin/`) o los endpoints REST.  
- Registrar un usuario con rostro: enviar `rut`, `nombres`, `apellidos`, `correo`, `rol`, `carrera` (opcional) y archivo `image` a `/usuarios/auth/register-face/`.  
- Validar acceso por rostro: enviar `image` o `embedding` a `/usuarios/auth/login/` y usar el `usuario_id` devuelto.  
- Gestionar inventario (tipos, categorias, herramientas) y luego crear reservas/prestamos via los endpoints de `inventario` y `operaciones`.

## Guia de explicacion para un tercero
1) Tecnologia y funciones  
   - Backend: Django 5 + Django REST Framework, servidor Gunicorn, Whitenoise para estaticos. BD: PostgreSQL (o SQLite en local).  
   - Reconocimiento facial: InsightFace (modelo buffalo_l) + cifrado Fernet.  
   - Apps: `usuarios` (auth/roles/carreras + rostros), `inventario` (catalogo), `operaciones` (reservas/prestamos).

2) Endpoints actuales (prefijo base `http://localhost:8000/`)  
   - Admin: `/admin/`.  
   - Usuarios: `/usuarios/api/roles/`, `/usuarios/api/usuarios/` (CRUD), `/usuarios/auth/register-face/`, `/usuarios/auth/login/`.  
   - Inventario: `/inventario/api/tipos-herramienta/`, `/inventario/api/categorias-herramienta/`, `/inventario/api/herramientas/`.  
   - Operaciones: `/operaciones/api/reservas/`, `/operaciones/api/prestamos/`.

3) Como funciona la base de datos  
   - `usuarios_usuario`: credencial por `correo`, relaciona `rol_usuarios` y `carrera`; guarda `embedding` cifrado.  
   - `inventario`: categorias -> tipos de herramienta -> herramientas individuales (con codigo de barras y estado).  
   - `operaciones`: `reserva` y `prestamo` referencian usuario y herramientas/tipos, con fechas y estado.

4) Como funciona el reconocimiento facial  
   - Registro (`/usuarios/auth/register-face/`): recibe imagen, extrae embedding con InsightFace, lo cifra con `FACE_ENCRYPTION_KEY` y lo almacena ligado al usuario.  
   - Login (`/usuarios/auth/login/`): recibe imagen o embedding; se descifra el embedding guardado y se compara por distancia (umbral 0.35). Devuelve coincidencia y `usuario_id`.  
   - Si la imagen no es valida o no hay rostro, responde con error claro.

5) Guialo para trabajar en VS Code y enviar commits  
   - Prerequisitos: Python 3.13, Git, VS Code con extensiones Python y Docker (opcional). Acceso al repo remoto.  
   - Clonar: `git clone <url-del-repo> && cd api-smartlend/apismartlend`.  
   - Abrir en VS Code: `code .`. Crear rama: `git checkout -b feature/<tema>`.  
   - Configurar `.env` (ver seccion Variables de entorno).  
   - Instalar deps: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` (o usar Docker con `docker compose up --build`).  
   - Probar local: `python manage.py migrate` y `python manage.py runserver`.  
   - Confirmar estilo/funcionalidad, hacer commits: `git status`, `git add ...`, `git commit -m "feat: ..."` y `git push origin feature/<tema>`.  
   - Abrir PR en el repo remoto y asignar reviewer.
