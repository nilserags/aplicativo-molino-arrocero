from functools import wraps
from flask import abort
from flask_login import current_user


def requiere_rol(rol_requerido: str):
    """
    Restringe una ruta a un solo rol.
    Ejemplo: @requiere_rol(ROL_ENCARGADO) -> solo el encargado puede entrar.
    Esto es lo que garantiza que 'solo esa persona puede modificar' los datos.
    """

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated or current_user.rol != rol_requerido:
                abort(403)  # Prohibido: no tienes el rol necesario
            return vista(*args, **kwargs)

        return envoltura

    return decorador
