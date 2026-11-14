from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import Usuario, ROL_TECNICO, ROL_ENCARGADO

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and usuario.check_password(password):
            login_user(usuario)
            # Forzar cambio de contraseña si es su primer ingreso con la clave por defecto
            if usuario.debe_cambiar_password:
                flash("Por seguridad institucional, debe cambiar su contraseña inicial antes de operar el sistema.", "warning")
                return redirect(url_for("auth.cambiar_password"))

            if usuario.rol == ROL_ENCARGADO:
                return redirect(url_for("encargado.dashboard"))
            return redirect(url_for("tecnico.registrar"))

        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@auth_bp.route("/cambiar-password", methods=["GET", "POST"])
@login_required
def cambiar_password():
    """
    Ruta obligatoria en el primer ingreso cuando el usuario tiene la contraseña por defecto (1234),
    o accesible desde el perfil para actualizar credenciales de acceso institucional.
    """
    if request.method == "POST":
        password_actual = request.form.get("password_actual", "")
        password_nueva = request.form.get("password_nueva", "").strip()
        password_confirmar = request.form.get("password_confirmar", "").strip()

        if not current_user.check_password(password_actual):
            flash("La contraseña actual ingresada es incorrecta.", "danger")
            return render_template("cambiar_password.html")

        if password_nueva == "1234":
            flash("La nueva contraseña no puede ser la clave por defecto '1234'. Ingrese una contraseña segura.", "danger")
            return render_template("cambiar_password.html")

        if len(password_nueva) < 6:
            flash("La nueva contraseña debe tener al menos 6 caracteres.", "danger")
            return render_template("cambiar_password.html")

        if password_nueva != password_confirmar:
            flash("La nueva contraseña y su confirmación no coinciden. Inténtelo de nuevo.", "danger")
            return render_template("cambiar_password.html")

        current_user.set_password(password_nueva)
        current_user.debe_cambiar_password = False
        db.session.commit()

        flash("¡Contraseña actualizada con éxito! Ya puede operar el sistema de manera segura.", "success")
        if current_user.rol == ROL_ENCARGADO:
            return redirect(url_for("encargado.dashboard"))
        return redirect(url_for("tecnico.registrar"))

    return render_template("cambiar_password.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
