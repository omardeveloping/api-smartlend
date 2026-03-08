from rest_framework.permissions import BasePermission


ROLE_ESTUDIANTE = 'ESTUDIANTE'
ROLE_DOCENTE = 'DOCENTE'
ROLE_BODEGUERO = 'BODEGUERO'

ROLE_ALIASES = {
    'ESTUDIANTE': ROLE_ESTUDIANTE,
    'ALUMNO': ROLE_ESTUDIANTE,
    'DOCENTE': ROLE_DOCENTE,
    'PROFESOR': ROLE_DOCENTE,
    'BODEGUERO': ROLE_BODEGUERO,
}


def normalize_role_code(raw_code):
    if raw_code is None:
        return None
    normalized = str(raw_code).strip().upper()
    if not normalized:
        return None
    return ROLE_ALIASES.get(normalized, normalized)


def role_code_from_role(role):
    if role is None:
        return None
    codigo = (getattr(role, 'codigo', None) or '').strip()
    if codigo:
        return normalize_role_code(codigo)
    nombre = (getattr(role, 'nombre', None) or '').strip()
    return normalize_role_code(nombre)


def user_role_code(user):
    if not getattr(user, 'is_authenticated', False):
        return None
    return role_code_from_role(getattr(user, 'id_rol', None))


def has_any_role(user, *role_codes):
    current = user_role_code(user)
    expected = {normalize_role_code(code) for code in role_codes}
    return bool(current and current in expected)


def is_bodeguero(user):
    return has_any_role(user, ROLE_BODEGUERO)


def is_docente(user):
    return has_any_role(user, ROLE_DOCENTE)


class EsActorSistema(BasePermission):
    message = 'Tu rol no está autorizado para esta acción.'

    def has_permission(self, request, view):
        return has_any_role(
            request.user,
            ROLE_ESTUDIANTE,
            ROLE_DOCENTE,
            ROLE_BODEGUERO,
        )


class EsBodeguero(BasePermission):
    message = 'Solo usuarios con rol Bodeguero pueden realizar esta acción.'

    def has_permission(self, request, view):
        return is_bodeguero(request.user)


class EsDocenteOBodeguero(BasePermission):
    message = 'Solo Docente o Bodeguero pueden realizar esta acción.'

    def has_permission(self, request, view):
        return has_any_role(request.user, ROLE_DOCENTE, ROLE_BODEGUERO)


class EsSolicitanteOBodeguero(BasePermission):
    message = 'Solo Estudiante, Docente o Bodeguero pueden realizar esta acción.'

    def has_permission(self, request, view):
        return has_any_role(
            request.user,
            ROLE_ESTUDIANTE,
            ROLE_DOCENTE,
            ROLE_BODEGUERO,
        )


class EsBodegueroOSelf(BasePermission):
    message = 'Solo puedes acceder a tus propios datos.'

    def has_permission(self, request, view):
        return bool(getattr(request.user, 'is_authenticated', False))

    def has_object_permission(self, request, view, obj):
        return is_bodeguero(request.user) or obj.pk == request.user.pk
