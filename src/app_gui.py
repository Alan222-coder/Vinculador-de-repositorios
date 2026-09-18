"""Interfaz gráfica de usuario moderna para Git Manager construida con CustomTkinter.

Cumple con todos los requisitos fundamentales:
- Separación de comprobación de Git local vs cuenta de GitHub
- Vinculación completa de carpetas normales de Windows (sin .git)
- Detección y análisis previo de archivos locales
- Opción de clonar repositorios o vincular existentes
- Flujo guiado de identidad Git (user.name / user.email)
- Vinculación manual guiada por usuario/email con verificación
- Manejo de carpetas movidas y adaptabilidad en pendrive
"""

import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, List, Dict, Any

import customtkinter as ctk

from src.logger_service import logger
from src.config_manager import config
from src.git_service import git_service
from src.github_auth import github_auth
from src.security_checker import SecurityChecker
from src.error_translator import ErrorTranslator


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class GitManagerApp(ctk.CTk):
    """Ventana principal de Git Manager."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Git Manager - Proyecto Escolar")
        self.geometry("820x760")
        self.minsize(720, 680)

        self._set_app_icon()

        self.is_busy = False
        self.last_technical_details: Dict[str, Any] = {}
        self.cached_git_info = {"available": False, "version": ""}
        self.cached_auth_info = {"is_authenticated": False, "username": ""}
        self.cached_repo_info = {"is_repo": False}
        self.last_collab_status: Dict[str, Any] = {}

        self._build_ui()
        self.after(200, self._initial_check)
        self.after(4000, self._start_live_sync_loop)

    def _set_app_icon(self) -> None:
        try:
            from src.logger_service import get_base_dir
            base = getattr(sys, "_MEIPASS", get_base_dir())
            icon_path = os.path.join(base, "assets", "icon.ico")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(get_base_dir(), "assets", "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.main_container = ctk.CTkScrollableFrame(self, corner_radius=12)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. ENCABEZADO
        self.header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 10))

        self.lbl_title = ctk.CTkLabel(
            self.header_frame,
            text="GIT MANAGER",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        self.lbl_title.pack()

        self.lbl_subtitle = ctk.CTkLabel(
            self.header_frame,
            text="Herramienta de Respaldo y Vinculación para Proyectos Escolares",
            font=ctk.CTkFont(size=13),
            text_color="gray70",
        )
        self.lbl_subtitle.pack()

        # 2. BLOQUE 1: GIT DE LA COMPUTADORA (Independiente)
        self.git_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.git_card.pack(fill="x", pady=6, padx=5)

        self.git_header_row = ctk.CTkFrame(self.git_card, fg_color="transparent")
        self.git_header_row.pack(fill="x", padx=15, pady=(10, 4))

        self.lbl_git_title = ctk.CTkLabel(
            self.git_header_row,
            text="Git de la computadora",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray60",
        )
        self.lbl_git_title.pack(side="left")

        self.btn_install_git = ctk.CTkButton(
            self.git_header_row,
            text="[ ¿Cómo instalar Git? ]",
            width=160,
            height=26,
            fg_color="#334155",
            hover_color="#1e293b",
            command=lambda: webbrowser.open("https://git-scm.com/download/win"),
        )
        self.btn_install_git.pack(side="right")
        self.btn_install_git.pack_forget()

        self.lbl_git_status = ctk.CTkLabel(
            self.git_card,
            text="🔵 Comprobando Git...",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self.lbl_git_status.pack(fill="x", padx=15, pady=(0, 10))

        # 3. BLOQUE 2: GITHUB (Independiente)
        self.gh_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.gh_card.pack(fill="x", pady=6, padx=5)

        self.gh_header_row = ctk.CTkFrame(self.gh_card, fg_color="transparent")
        self.gh_header_row.pack(fill="x", padx=15, pady=(10, 4))

        ctk.CTkLabel(
            self.gh_header_row,
            text="GitHub",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray60",
        ).pack(side="left")

        self.lbl_gh_badge = ctk.CTkLabel(
            self.gh_card,
            text="🔵 Verificando GitHub...",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self.lbl_gh_badge.pack(fill="x", padx=15, pady=(0, 4))

        self.lbl_gh_user = ctk.CTkLabel(
            self.gh_card,
            text="👤 Usuario: Comprobando...",
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        self.lbl_gh_user.pack(fill="x", padx=15, pady=(0, 8))

        # Sección de login y vinculación manual si no hay sesión
        self.gh_login_section = ctk.CTkFrame(self.gh_card, fg_color="transparent")
        self.gh_login_section.pack(fill="x", padx=15, pady=(0, 12))

        self.btn_login = ctk.CTkButton(
            self.gh_login_section,
            text="[ INICIAR SESIÓN ]",
            height=34,
            width=160,
            fg_color="#2b7de9",
            hover_color="#1d5ec2",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_login,
        )
        self.btn_login.pack(anchor="w", pady=(2, 6))

        # Opción 2.1: Vinculación manual por usuario/email
        self.lbl_manual_hint = ctk.CTkLabel(
            self.gh_login_section,
            text="¿Ya tenés una cuenta de GitHub? Ingresá tu usuario o email para vincularla:",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            anchor="w",
        )
        self.lbl_manual_hint.pack(anchor="w", pady=(6, 2))

        self.manual_entry_row = ctk.CTkFrame(self.gh_login_section, fg_color="transparent")
        self.manual_entry_row.pack(fill="x", pady=(2, 4))

        self.txt_user_hint = ctk.CTkEntry(
            self.manual_entry_row,
            placeholder_text="Ejemplo: Alan222-coder o correo@colegio.edu",
            height=34,
            width=360,
        )
        self.txt_user_hint.pack(side="left", padx=(0, 8))

        self.btn_manual_link = ctk.CTkButton(
            self.manual_entry_row,
            text="[ VINCULAR CUENTA ]",
            height=34,
            width=180,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._handle_manual_account_link,
        )
        self.btn_manual_link.pack(side="left")

        # 4. BLOQUE 3: PROYECTO LOCAL
        self.proj_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.proj_card.pack(fill="x", pady=6, padx=5)

        self.proj_header_row = ctk.CTkFrame(self.proj_card, fg_color="transparent")
        self.proj_header_row.pack(fill="x", padx=15, pady=(10, 4))

        ctk.CTkLabel(
            self.proj_header_row,
            text="Proyecto",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray60",
        ).pack(side="left")

        self.btn_choose_folder = ctk.CTkButton(
            self.proj_header_row,
            text="📁 SELECCIONAR PROYECTO",
            height=28,
            width=180,
            fg_color="#334155",
            hover_color="#1e293b",
            command=self._choose_project_folder,
        )
        self.btn_choose_folder.pack(side="right")

        self.lbl_proj_status = ctk.CTkLabel(
            self.proj_card,
            text="🟡 No hay proyecto seleccionado",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self.lbl_proj_status.pack(fill="x", padx=15, pady=(0, 4))

        self.lbl_proj_path = ctk.CTkLabel(
            self.proj_card,
            text="📁 Carpeta: (Ninguna)",
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color="#60a5fa",
        )
        self.lbl_proj_path.pack(fill="x", padx=15, pady=2)

        # Detalles si es repo
        self.repo_details_frame = ctk.CTkFrame(self.proj_card, fg_color="transparent")
        self.repo_details_frame.pack(fill="x", padx=15, pady=(2, 8))

        self.lbl_proj_repo = ctk.CTkLabel(self.repo_details_frame, text="Repositorio: -", anchor="w", font=ctk.CTkFont(size=12))
        self.lbl_proj_repo.pack(fill="x", pady=1)

        self.lbl_proj_branch = ctk.CTkLabel(self.repo_details_frame, text="Rama: -", anchor="w", font=ctk.CTkFont(size=12))
        self.lbl_proj_branch.pack(fill="x", pady=1)

        self.lbl_proj_sync = ctk.CTkLabel(self.repo_details_frame, text="Estado: -", anchor="w", font=ctk.CTkFont(size=12))
        self.lbl_proj_sync.pack(fill="x", pady=1)

        # Opciones si la carpeta no tiene .git
        self.not_linked_actions_frame = ctk.CTkFrame(self.proj_card, fg_color="transparent")
        self.not_linked_actions_frame.pack(fill="x", padx=15, pady=(6, 12))
        self.not_linked_actions_frame.columnconfigure(0, weight=1)
        self.not_linked_actions_frame.columnconfigure(1, weight=1)

        self.btn_link_existing = ctk.CTkButton(
            self.not_linked_actions_frame,
            text="🔗  VINCULAR CON GITHUB",
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#16a34a",
            hover_color="#15803d",
            command=self._open_link_wizard,
        )
        self.btn_link_existing.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_clone_repo = ctk.CTkButton(
            self.not_linked_actions_frame,
            text="📥  CLONAR UN REPOSITORIO",
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._open_clone_wizard,
        )
        self.btn_clone_repo.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.not_linked_actions_frame.pack_forget()

        # 5. BLOQUE DE COLABORACIÓN Y SINCRONIZACIÓN EN VIVO (EQUIPO)
        self.collab_card = ctk.CTkFrame(self.main_container, corner_radius=10, fg_color="#1e293b")
        self.collab_card.pack(fill="x", pady=6, padx=5)

        self.collab_top_row = ctk.CTkFrame(self.collab_card, fg_color="transparent")
        self.collab_top_row.pack(fill="x", padx=15, pady=(8, 4))

        ctk.CTkLabel(
            self.collab_top_row,
            text="👥 Sincronización de Equipo en Vivo",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#94a3b8",
        ).pack(side="left")

        self.btn_check_collab = ctk.CTkButton(
            self.collab_top_row,
            text="🔄 Buscar cambios de otros",
            height=26,
            width=180,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._manual_check_live_sync,
        )
        self.btn_check_collab.pack(side="right")

        # Banner de alerta cuando hay commits entrantes
        self.collab_alert_box = ctk.CTkFrame(self.collab_card, corner_radius=8, fg_color="#0f172a")
        self.collab_alert_box.pack(fill="x", padx=12, pady=(4, 10))

        self.lbl_collab_notice = ctk.CTkLabel(
            self.collab_alert_box,
            text="✓ Tu copia está al día con el repositorio remoto.",
            font=ctk.CTkFont(size=12),
            text_color="#4ade80",
            anchor="w",
            wraplength=640,
            justify="left",
        )
        self.lbl_collab_notice.pack(fill="x", padx=12, pady=(6, 6))

        self.collab_actions_row = ctk.CTkFrame(self.collab_alert_box, fg_color="transparent")
        self.collab_actions_row.pack(fill="x", padx=12, pady=(0, 8))

        self.btn_pull_incoming = ctk.CTkButton(
            self.collab_actions_row,
            text="📥 Traer cambios del equipo",
            height=30,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._pull_incoming_changes,
        )
        self.btn_pull_incoming.pack(side="left", padx=(0, 8))

        self.btn_view_incoming = ctk.CTkButton(
            self.collab_actions_row,
            text="Ver detalles de los cambios",
            height=30,
            fg_color="#475569",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            command=self._show_incoming_details,
        )
        self.btn_view_incoming.pack(side="left")
        self.collab_actions_row.pack_forget()

        # 6. BARRA DE PROGRESO GLOBAL
        self.progress_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.progress_frame.pack(fill="x", pady=4, padx=5)

        self.lbl_progress_status = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#60a5fa",
        )
        self.lbl_progress_status.pack()

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=8)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=4)
        self.progress_frame.pack_forget()

        # 7. BOTONES DE ACCIÓN PRINCIPAL (Operaciones diarias)
        self.actions_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.actions_frame.pack(fill="x", pady=10, padx=5)

        self.btn_pull = ctk.CTkButton(
            self.actions_frame,
            text="📥  TRAER CAMBIOS",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=50,
            corner_radius=10,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._handle_pull,
        )
        self.btn_pull.pack(fill="x", pady=5)

        self.btn_backup = ctk.CTkButton(
            self.actions_frame,
            text="📤  CREAR BACKUP",
            font=ctk.CTkFont(size=17, weight="bold"),
            height=60,
            corner_radius=10,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=self._open_backup_dialog,
        )
        self.btn_backup.pack(fill="x", pady=5)

        # Fila de gestión de ramas
        self.branches_row = ctk.CTkFrame(self.actions_frame, fg_color="transparent")
        self.branches_row.pack(fill="x", pady=5)
        self.branches_row.columnconfigure(0, weight=1)
        self.branches_row.columnconfigure(1, weight=1)

        self.btn_branch = ctk.CTkButton(
            self.branches_row,
            text="🌿  CAMBIAR RAMA",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            corner_radius=10,
            fg_color="#475569",
            hover_color="#334155",
            command=self._open_branch_dialog,
        )
        self.btn_branch.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.btn_create_branch = ctk.CTkButton(
            self.branches_row,
            text="➕  CREAR RAMA NUEVA",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            corner_radius=10,
            fg_color="#0369a1",
            hover_color="#0284c7",
            command=self._open_create_branch_dialog,
        )
        self.btn_create_branch.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # 7. FILA SECUNDARIA
        self.secondary_row = ctk.CTkFrame(self.actions_frame, fg_color="transparent")
        self.secondary_row.pack(fill="x", pady=(6, 2))
        self.secondary_row.columnconfigure(0, weight=1)
        self.secondary_row.columnconfigure(1, weight=1)

        self.btn_history = ctk.CTkButton(
            self.secondary_row,
            text="📜 Historial de Backups",
            height=34,
            fg_color="#334155",
            hover_color="#1e293b",
            command=self._open_history_dialog,
        )
        self.btn_history.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_identity = ctk.CTkButton(
            self.secondary_row,
            text="⚙️ Identidad Git y Ajustes",
            height=34,
            fg_color="#334155",
            hover_color="#1e293b",
            command=self._open_identity_dialog,
        )
        self.btn_identity.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # 8. BANNER DE ÚLTIMA OPERACIÓN
        self.last_op_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.last_op_card.pack(fill="x", pady=10, padx=5)

        self.lbl_last_op_title = ctk.CTkLabel(
            self.last_op_card,
            text="Última operación:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray60",
        )
        self.lbl_last_op_title.pack(anchor="w", padx=15, pady=(8, 2))

        self.lbl_last_op_msg = ctk.CTkLabel(
            self.last_op_card,
            text="Aplicación iniciada.",
            font=ctk.CTkFont(size=13),
            wraplength=660,
            justify="left",
        )
        self.lbl_last_op_msg.pack(anchor="w", padx=15, pady=(2, 6))

        self.btn_details = ctk.CTkButton(
            self.last_op_card,
            text="Ver detalles técnicos",
            height=26,
            width=150,
            fg_color="transparent",
            text_color="#60a5fa",
            hover_color="#1e293b",
            command=self._show_technical_details,
        )
        self.btn_details.pack(anchor="w", padx=15, pady=(0, 8))
        self.btn_details.pack_forget()

    # ==================== VERIFICACIONES INDEPENDIENTES ====================

    def _initial_check(self) -> None:
        """Comprueba de forma independiente Git, GitHub y el Proyecto."""
        self.refresh_all_status()

    def refresh_all_status(self) -> None:
        """Actualiza el estado de los 3 bloques principales en hilos de fondo."""
        def task():
            # 1. Comprobar Git en la computadora
            git_ok = git_service.is_git_available()
            git_version = git_service.get_git_version() if git_ok else ""
            self.cached_git_info = {"available": git_ok, "version": git_version}

            # 2. Comprobar GitHub (independiente de Git local)
            auth_info = github_auth.get_auth_status()
            self.cached_auth_info = auth_info

            # 3. Comprobar Proyecto local
            current_path = config.get_project_path()
            path_exists = os.path.isdir(current_path) if current_path else False
            is_repo = git_service.is_git_repository(current_path) if path_exists else False
            repo_info = git_service.get_repo_info(current_path) if is_repo else {}

            def update_ui():
                # Actualizar Tarjeta 1: Git Local
                if git_ok:
                    self.lbl_git_status.configure(
                        text=f"🟢 Git disponible ({git_version})",
                        text_color="#4ade80",
                    )
                    self.btn_install_git.pack_forget()
                else:
                    self.lbl_git_status.configure(
                        text="🔴 Git no está disponible en esta computadora",
                        text_color="#f87171",
                    )
                    self.btn_install_git.pack(side="right")

                # Actualizar Tarjeta 2: GitHub
                if auth_info["is_authenticated"]:
                    user_label = auth_info["username"]
                    if auth_info.get("public_name") and auth_info["public_name"] != user_label:
                        user_label += f" ({auth_info['public_name']})"
                    self.lbl_gh_badge.configure(
                        text="🟢 GitHub conectado",
                        text_color="#4ade80",
                    )
                    self.lbl_gh_user.configure(text=f"👤 Usuario: {user_label}")
                    self.gh_login_section.pack_forget()
                else:
                    self.lbl_gh_badge.configure(
                        text="🔴 GitHub no conectado en esta computadora",
                        text_color="#f87171",
                    )
                    self.lbl_gh_user.configure(text="👤 Usuario: No disponible")
                    self.gh_login_section.pack(fill="x", padx=15, pady=(0, 12))

                # Actualizar Tarjeta 3: Proyecto Local
                if not current_path:
                    self.lbl_proj_status.configure(text="🟡 Ningún proyecto seleccionado", text_color="#fbbf24")
                    self.lbl_proj_path.configure(text="📁 Carpeta: Haz clic en 'SELECCIONAR PROYECTO'")
                    self.repo_details_frame.pack_forget()
                    self.not_linked_actions_frame.pack_forget()
                    self._enable_repo_actions(False)
                elif not path_exists:
                    self.lbl_proj_status.configure(text="⚠️ No se encuentra la carpeta configurada", text_color="#f87171")
                    self.lbl_proj_path.configure(text=f"📁 Carpeta movida o borrada: {current_path}")
                    self.repo_details_frame.pack_forget()
                    self.not_linked_actions_frame.pack_forget()
                    self._enable_repo_actions(False)
                elif is_repo:
                    self.lbl_proj_status.configure(text="🟢 Repositorio Git detectado y vinculado", text_color="#4ade80")
                    self.lbl_proj_path.configure(text=f"📁 Carpeta: {current_path}")
                    current_b = repo_info.get("branch") or "main"
                    self.lbl_proj_branch.configure(
                        text=f"🌿 Rama activa: {current_b}  (Parado aquí)",
                        text_color="#38bdf8",
                        font=ctk.CTkFont(size=13, weight="bold"),
                    )
                    if repo_info.get("is_clean"):
                        self.lbl_proj_sync.configure(text="✓ Estado: Todo actualizado", text_color="#4ade80")
                    else:
                        self.lbl_proj_sync.configure(text="● Estado: Hay cambios locales sin guardar", text_color="#fbbf24")
                    self.repo_details_frame.pack(fill="x", padx=15, pady=(2, 8))
                    self.not_linked_actions_frame.pack_forget()
                    self._enable_repo_actions(True)
                else:
                    # La carpeta existe pero NO contiene .git
                    files, dirs = git_service.count_folder_contents(current_path)
                    self.lbl_proj_status.configure(
                        text=f"🟡 Esta carpeta todavía no está vinculada a Git ({files} archivos)",
                        text_color="#fbbf24",
                    )
                    self.lbl_proj_path.configure(text=f"📁 Carpeta: {current_path}")
                    self.repo_details_frame.pack_forget()
                    self.not_linked_actions_frame.pack(fill="x", padx=15, pady=(6, 12))
                    self._enable_repo_actions(False)

            self.after(0, update_ui)

        threading.Thread(target=task, daemon=True).start()

    def _enable_repo_actions(self, enable: bool) -> None:
        state = "normal" if enable and not self.is_busy else "disabled"
        self.btn_pull.configure(state=state)
        self.btn_backup.configure(state=state)
        self.btn_branch.configure(state=state)
        if hasattr(self, "btn_create_branch"):
            self.btn_create_branch.configure(state=state)
        self.btn_history.configure(state=state)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.is_busy = busy
        self._enable_repo_actions(not busy)
        if busy:
            self.progress_frame.pack(fill="x", pady=4, padx=5)
            self.lbl_progress_status.configure(text=message)
            self.progress_bar.set(0.2)
        else:
            self.progress_frame.pack_forget()

    def _set_operation_result(
        self,
        message: str,
        is_error: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        color = "#f87171" if is_error else "#4ade80"
        self.lbl_last_op_msg.configure(text=message, text_color=color)

        if details and (details.get("raw") or details.get("command")):
            self.last_technical_details = details
            self.btn_details.pack(anchor="w", padx=15, pady=(0, 8))
        else:
            self.btn_details.pack_forget()

    def _show_technical_details(self) -> None:
        if not self.last_technical_details:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Detalles Técnicos de Git")
        dialog.geometry("620x440")
        dialog.transient(self)
        dialog.grab_set()

        lbl_top = ctk.CTkLabel(
            dialog,
            text=self.last_technical_details.get("title", "Salida de comando"),
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        lbl_top.pack(anchor="w", padx=20, pady=(15, 5))

        cmd = self.last_technical_details.get("command", "")
        if cmd:
            ctk.CTkLabel(
                dialog,
                text=f"Comando: {cmd}",
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color="gray70",
            ).pack(anchor="w", padx=20, pady=2)

        txt_box = ctk.CTkTextbox(dialog, font=ctk.CTkFont(family="Consolas", size=11))
        txt_box.pack(fill="both", expand=True, padx=20, pady=10)
        raw_content = self.last_technical_details.get("raw", "Sin información disponible.")
        txt_box.insert("1.0", raw_content)
        txt_box.configure(state="disabled")

        ctk.CTkButton(dialog, text="Cerrar", width=100, command=dialog.destroy).pack(pady=(0, 15))

    # ==================== SELECCIÓN Y GESTIÓN DE CARPETA ====================

    def _choose_project_folder(self) -> None:
        """Permite al usuario seleccionar cualquier carpeta normal de Windows."""
        folder = filedialog.askdirectory(title="Selecciona la carpeta de tu proyecto")
        if not folder:
            return

        folder = os.path.normpath(folder)
        config.set_project_path(folder)
        self.refresh_all_status()
        self._set_operation_result(f"Carpeta seleccionada: {os.path.basename(folder)}")

    # ==================== LOGIN Y VINCULACIÓN MANUAL DE GITHUB ====================

    def _handle_login(self) -> None:
        """Inicia el inicio de sesión oficial en GitHub."""
        self._set_busy(True, "Abriendo inicio de sesión oficial de GitHub en el navegador...")

        def task():
            res = github_auth.launch_official_login()

            def finish():
                self._set_busy(False)
                if res["success"]:
                    messagebox.showinfo("GitHub", res["message"])
                    self._set_operation_result(f"Sesión iniciada como {res.get('username')}")
                else:
                    messagebox.showwarning("GitHub", res["message"])
                self.refresh_all_status()

            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    def _handle_manual_account_link(self) -> None:
        """Flujo de la Sección 2.1: usuario ingresa usuario/email y luego se autentica."""
        hint = self.txt_user_hint.get().strip()
        if not hint:
            messagebox.showinfo("Vinculación", "Por favor escribe tu usuario o email de GitHub.")
            return

        self._set_busy(True, f"Preparando autenticación para la cuenta '{hint}'...")

        def task():
            res = github_auth.launch_official_login()

            def finish():
                self._set_busy(False)
                if res["success"]:
                    actual_user = res.get("username", "")
                    actual_email = res.get("email", "")
                    matches, msg = github_auth.verify_manual_hint_against_login(hint, actual_user, actual_email)
                    if not matches:
                        # Preguntar confirmación clara
                        confirm = messagebox.askyesno("Confirmar Cuenta de GitHub", msg)
                        if not confirm:
                            self._set_operation_result("Vinculación cancelada por el usuario.", is_error=True)
                            self.refresh_all_status()
                            return

                    messagebox.showinfo("Cuenta Vinculada", f"🟢 ¡Cuenta '{actual_user}' conectada correctamente!")
                    self._set_operation_result(f"Cuenta vinculada: {actual_user}")
                else:
                    messagebox.showwarning("GitHub", res["message"])
                self.refresh_all_status()

            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    # ==================== VINCULAR CARPETA EXISTENTE SIN .GIT ====================

    def _open_link_wizard(self) -> None:
        """Asistente para vincular una carpeta existente normal a un repositorio de GitHub."""
        project_path = config.get_project_path()
        if not project_path or not os.path.isdir(project_path):
            messagebox.showwarning("Carpeta no encontrada", "Por favor selecciona una carpeta primero.")
            return

        files_count, dirs_count = git_service.count_folder_contents(project_path)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Vincular Proyecto con GitHub")
        dialog.geometry("640x540")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="🔗 VINCULAR CARPETA CON GITHUB",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(15, 5))

        # Alerta informativa de archivos existentes (Requisito Sección 9)
        alert_text = (
            f"⚠️ Esta carpeta ya contiene archivos:\n"
            f"  • {files_count} archivos\n"
            f"  • {dirs_count} carpetas\n\n"
            f"Tus archivos NO serán eliminados ni sobrescritos."
        )
        ctk.CTkLabel(
            dialog,
            text=alert_text,
            font=ctk.CTkFont(size=12),
            text_color="#fbbf24",
            justify="left",
        ).pack(fill="x", padx=30, pady=8)

        # Selección de repositorio (Requisito Sección 7)
        ctk.CTkLabel(
            dialog,
            text="URL del repositorio de GitHub (HTTPS):",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=30, pady=(6, 2))

        txt_remote = ctk.CTkEntry(
            dialog,
            placeholder_text="Ejemplo: https://github.com/usuario/mi-proyecto.git",
            height=36,
        )
        txt_remote.pack(fill="x", padx=30, pady=4)

        # Si el usuario ya está autenticado, sugerir repos si los hay
        auth = github_auth.get_auth_status()
        suggested_url = ""
        if auth.get("username"):
            folder_name = os.path.basename(project_path)
            suggested_url = f"https://github.com/{auth['username']}/{folder_name}.git"
            txt_remote.insert(0, suggested_url)

        # Configuración de Identidad Git (Requisito Sección 13)
        ctk.CTkLabel(
            dialog,
            text="Identidad para los backups (Git user.name y user.email):",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=30, pady=(12, 2))

        current_name, current_email = git_service.get_git_identity(project_path)
        if not current_name and auth.get("username"):
            current_name = auth.get("public_name") or auth.get("username")
        if not current_email and auth.get("email"):
            current_email = auth.get("email")

        name_row = ctk.CTkFrame(dialog, fg_color="transparent")
        name_row.pack(fill="x", padx=30, pady=2)
        ctk.CTkLabel(name_row, text="Tu Nombre:", width=80, anchor="w").pack(side="left")
        txt_name = ctk.CTkEntry(name_row, height=32)
        txt_name.pack(side="left", fill="x", expand=True)
        if current_name:
            txt_name.insert(0, current_name)

        email_row = ctk.CTkFrame(dialog, fg_color="transparent")
        email_row.pack(fill="x", padx=30, pady=2)
        ctk.CTkLabel(email_row, text="Tu Correo:", width=80, anchor="w").pack(side="left")
        txt_email = ctk.CTkEntry(email_row, height=32)
        txt_email.pack(side="left", fill="x", expand=True)
        if current_email:
            txt_email.insert(0, current_email)

        lbl_status = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=12), text_color="#f87171")
        lbl_status.pack(pady=4)

        def execute_linking():
            url = txt_remote.get().strip()
            name = txt_name.get().strip()
            email = txt_email.get().strip()

            if not url or not url.startswith("http"):
                lbl_status.configure(text="Ingresa una URL válida de GitHub (https://...).")
                return
            if not name or not email:
                lbl_status.configure(text="Nombre y correo son requeridos para la identidad de Git.")
                return

            dialog.destroy()
            self._set_busy(True, "Vinculando proyecto y configurando repositorio...")

            def task():
                # Guardar identidad en Git
                git_service.set_git_identity(name, email, project_path, is_global=False)

                # Ejecutar vinculación completa
                def progress(stage: str, fraction: float):
                    self.after(0, lambda: self.lbl_progress_status.configure(text=stage))
                    self.after(0, lambda: self.progress_bar.set(fraction))

                succ, msg, diag = git_service.link_folder_to_github(
                    folder_path=project_path,
                    remote_url=url,
                    commit_message="Primer backup del proyecto escolar",
                    progress_callback=progress,
                )

                def finish():
                    self._set_busy(False)
                    if succ:
                        # Pantalla final requerida en Sección 22
                        final_msg = (
                            "✅ PROYECTO CONFIGURADO\n\n"
                            f"• Git: 🟢 Disponible ({git_service.get_git_version()})\n"
                            f"• GitHub: 🟢 {auth.get('username') or name}\n"
                            f"• Repositorio: 🟢 {url}\n"
                            f"• Rama: 🟢 main\n"
                            f"• Carpeta: 🟢 {project_path}\n\n"
                            "¡Ya puedes trabajar normalmente y crear backups!"
                        )
                        messagebox.showinfo("✅ Proyecto Vinculado", final_msg)
                        self._set_operation_result("Proyecto correctamente vinculado a GitHub.")
                    else:
                        messagebox.showwarning("Error al Vincular", f"{diag.get('title', 'Error')}\n\n{msg}")
                        self._set_operation_result(f"Error al vincular: {msg}", is_error=True, details=diag)
                    self.refresh_all_status()

                self.after(0, finish)

            threading.Thread(target=task, daemon=True).start()

        btn_confirm = ctk.CTkButton(
            dialog,
            text="[ CONTINUAR Y VINCULAR ]",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#16a34a",
            hover_color="#15803d",
            command=execute_linking,
        )
        btn_confirm.pack(pady=15)

    # ==================== CLONAR REPOSITORIO (Opción B) ====================

    def _open_clone_wizard(self) -> None:
        """Asistente para descargar/clonar un repositorio existente de GitHub."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Clonar Repositorio de GitHub")
        dialog.geometry("600x380")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="📥 CLONAR REPOSITORIO DESDE GITHUB",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(pady=(15, 10))

        ctk.CTkLabel(dialog, text="URL del repositorio de GitHub:", anchor="w").pack(fill="x", padx=30, pady=(4, 2))
        txt_url = ctk.CTkEntry(dialog, placeholder_text="https://github.com/usuario/proyecto.git", height=36)
        txt_url.pack(fill="x", padx=30, pady=4)

        ctk.CTkLabel(dialog, text="Carpeta de destino en tu computadora:", anchor="w").pack(fill="x", padx=30, pady=(8, 2))
        dest_row = ctk.CTkFrame(dialog, fg_color="transparent")
        dest_row.pack(fill="x", padx=30, pady=4)

        txt_dest = ctk.CTkEntry(dest_row, placeholder_text="Selecciona una carpeta vacía", height=36)
        txt_dest.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def browse_dest():
            f = filedialog.askdirectory(title="Selecciona la carpeta donde clonar el proyecto")
            if f:
                txt_dest.delete(0, "end")
                txt_dest.insert(0, os.path.normpath(f))

        ctk.CTkButton(dest_row, text="Examinar...", width=100, height=36, command=browse_dest).pack(side="right")

        def start_clone():
            url = txt_url.get().strip()
            dest = txt_dest.get().strip()

            if not url.startswith("http"):
                messagebox.showwarning("Datos incompletos", "Por favor ingresa una URL válida de GitHub.")
                return
            if not dest or not os.path.isdir(dest):
                messagebox.showwarning("Datos incompletos", "Selecciona una carpeta de destino válida.")
                return

            dialog.destroy()
            self._set_busy(True, "Clonando repositorio de GitHub...")

            def task():
                succ, msg, diag = git_service.clone_repository(url, dest)

                def finish():
                    self._set_busy(False)
                    if succ:
                        config.set_project_path(dest)
                        messagebox.showinfo("Clonación Exitosa", f"El proyecto fue descargado exitosamente en:\n{dest}")
                        self._set_operation_result("Proyecto clonado y configurado correctamente.")
                    else:
                        messagebox.showwarning("Error al Clonar", f"{diag.get('title', 'Error')}\n\n{msg}")
                        self._set_operation_result(f"Error al clonar: {msg}", is_error=True, details=diag)
                    self.refresh_all_status()

                self.after(0, finish)

            threading.Thread(target=task, daemon=True).start()

        ctk.CTkButton(
            dialog,
            text="[ CLONAR PROYECTO ]",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=start_clone,
        ).pack(pady=25)

    # ==================== OPERACIONES: PULL ====================

    def _handle_pull(self) -> None:
        project_path = config.get_project_path()
        if not git_service.is_git_repository(project_path):
            messagebox.showwarning("Proyecto no válido", "Por favor selecciona una carpeta de proyecto válida.")
            return

        has_changes, files = git_service.has_local_changes(project_path)
        if has_changes:
            confirm = messagebox.askyesno(
                "Cambios locales pendientes",
                "⚠️ Tienes cambios locales sin guardar en tu proyecto.\n\n"
                "Traer cambios ahora podría provocar un conflicto con el trabajo de tus compañeros.\n\n"
                "¿Deseas continuar de todos modos?",
            )
            if not confirm:
                return

        self._set_busy(True, "Traer cambios: Descargando de GitHub...")

        def task():
            success, message, diag = git_service.pull(project_path)

            def finish_ui():
                self._set_busy(False)
                if success:
                    self._set_operation_result(f"✅ {message}", is_error=False, details=diag)
                    messagebox.showinfo("Traer cambios", f"✅ {message}")
                else:
                    self._set_operation_result(
                        f"⚠️ No se pudo traer cambios: {diag.get('title', 'Error')}",
                        is_error=True,
                        details=diag,
                    )
                    messagebox.showwarning(diag.get("title", "Error al traer cambios"), diag.get("message", message))
                self.refresh_all_status()

            self.after(0, finish_ui)

        threading.Thread(target=task, daemon=True).start()

    # ==================== OPERACIONES: BACKUP ====================

    def _open_backup_dialog(self) -> None:
        project_path = config.get_project_path()
        if not git_service.is_git_repository(project_path):
            messagebox.showwarning("Proyecto no válido", "Por favor selecciona una carpeta de proyecto válida.")
            return

        has_changes, files = git_service.has_local_changes(project_path)
        if not has_changes:
            messagebox.showinfo("Sin cambios", "ℹ️ No hay cambios nuevos para guardar en este momento.")
            return

        is_safe, dangerous_files = SecurityChecker.inspect_changed_files(files)
        if not is_safe:
            alert = SecurityChecker.format_security_alert(dangerous_files)
            messagebox.showerror(alert["title"], alert["message"])
            self._set_operation_result(
                f"⚠️ Backup bloqueado: Se detectó archivo privado ({dangerous_files[0]})",
                is_error=True,
                details={"title": "Alerta de seguridad", "raw": alert["message"], "command": "security_check"},
            )
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Crear Backup")
        dialog.geometry("520x340")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="CREAR BACKUP", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))
        ctk.CTkLabel(
            dialog,
            text="Describe los cambios que realizaste en el proyecto:",
            font=ctk.CTkFont(size=13),
            text_color="gray70",
        ).pack(pady=(0, 10))

        txt_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="Ejemplo: Agregué el sistema de login y estilos",
            width=440,
            height=45,
            font=ctk.CTkFont(size=13),
        )
        txt_entry.pack(pady=10)
        txt_entry.focus_set()

        lbl_error = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=12), text_color="#f87171")
        lbl_error.pack(pady=2)

        buttons_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=40, pady=20)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        ctk.CTkButton(
            buttons_frame,
            text="[ CANCELAR ]",
            height=42,
            fg_color="#475569",
            hover_color="#334155",
            command=dialog.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def execute_backup():
            description = txt_entry.get().strip()
            if not description:
                lbl_error.configure(text="Debes escribir una descripción de los cambios.")
                return

            dialog.destroy()
            self._run_backup_process(description)

        ctk.CTkButton(
            buttons_frame,
            text="[ CREAR BACKUP ]",
            height=42,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=execute_backup,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        txt_entry.bind("<Return>", lambda event: execute_backup())

    def _run_backup_process(self, message_text: str) -> None:
        project_path = config.get_project_path()
        self._set_busy(True, "Iniciando creación de backup...")

        def update_progress(stage: str, fraction: float):
            self.after(0, lambda: self.lbl_progress_status.configure(text=stage))
            self.after(0, lambda: self.progress_bar.set(fraction))

        def task():
            success, msg, diag = git_service.create_backup(
                repo_path=project_path,
                message=message_text,
                progress_callback=update_progress,
            )

            def finish_ui():
                self._set_busy(False)
                # Refrescar de inmediato TODAS las pantallas antes de desplegar cualquier alerta modal
                self.refresh_all_status()

                if success:
                    auth_info = github_auth.get_auth_status(project_path)
                    user_name = auth_info.get("username", "Usuario")
                    branch_name = diag.get("branch", "main")

                    success_display = (
                        f"✅ BACKUP CREADO\n\n"
                        f"Los cambios fueron enviados correctamente a GitHub.\n\n"
                        f"• Usuario: {user_name}\n"
                        f"• Rama: {branch_name}\n"
                        f"• Mensaje: {message_text}"
                    )
                    self._set_operation_result(
                        f"Backup creado correctamente: \"{message_text}\"",
                        is_error=False,
                        details=diag,
                    )
                    messagebox.showinfo("✅ Backup Creado", success_display)
                else:
                    self._set_operation_result(
                        f"⚠️ Error al crear backup: {diag.get('title', 'Error')}",
                        is_error=True,
                        details=diag,
                    )
                    self._show_backup_error_dialog(diag, msg)

            self.after(0, finish_ui)

        threading.Thread(target=task, daemon=True).start()

    def _show_backup_error_dialog(self, diag: Dict[str, Any], default_msg: str) -> None:
        """Muestra una ventana detallada con el error REAL de Git, código de salida y acción sugerida."""
        project_path = config.get_project_path()
        dialog = ctk.CTkToplevel(self)
        dialog.title("Detalle del Error de Guardado")
        dialog.geometry("640x520")
        dialog.transient(self)
        dialog.grab_set()

        title_text = diag.get("title", "⚠️ Error al crear backup")
        lbl_title = ctk.CTkLabel(
            dialog,
            text=title_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#f87171",
            wraplength=600,
            justify="left",
        )
        lbl_title.pack(anchor="w", padx=25, pady=(20, 8))

        msg_text = diag.get("message", default_msg)
        lbl_msg = ctk.CTkLabel(
            dialog,
            text=msg_text,
            font=ctk.CTkFont(size=13),
            wraplength=590,
            justify="left",
        )
        lbl_msg.pack(anchor="w", padx=25, pady=(0, 10))

        # Acción sugerida destacada
        action_text = diag.get("suggested_action")
        if action_text:
            action_card = ctk.CTkFrame(dialog, corner_radius=8, fg_color="#1e293b")
            action_card.pack(fill="x", padx=25, pady=(0, 10))
            ctk.CTkLabel(
                action_card,
                text=f"💡 Acción sugerida:\n{action_text}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#38bdf8",
                wraplength=570,
                justify="left",
            ).pack(anchor="w", padx=12, pady=10)

        # Caja técnica visible: Código de salida y mensaje de Git (stderr)
        tech_frame = ctk.CTkFrame(dialog, corner_radius=8, fg_color="#0f172a")
        tech_frame.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        exit_code = diag.get("exit_code")
        cmd_run = diag.get("command", "")
        top_meta = f"Código de salida: {exit_code if exit_code is not None else 'N/A'}"
        if cmd_run:
            top_meta += f"  |  Comando: {cmd_run}"

        ctk.CTkLabel(
            tech_frame,
            text=top_meta,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color="#fbbf24",
        ).pack(anchor="w", padx=12, pady=(8, 2))

        txt_err = ctk.CTkTextbox(tech_frame, font=ctk.CTkFont(family="Consolas", size=11), height=110)
        txt_err.pack(fill="both", expand=True, padx=12, pady=(4, 10))
        raw_err = diag.get("stderr") or diag.get("raw") or "Sin mensaje de error reportado por Git."
        txt_err.insert("1.0", raw_err)
        txt_err.configure(state="disabled")

        # Fila de botones según la causa del problema
        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=25, pady=(0, 18))

        cause = diag.get("cause")
        if cause == "missing_identity":
            ctk.CTkButton(
                btn_box,
                text="⚙️ Configurar Identidad de Git",
                fg_color="#0284c7",
                hover_color="#0369a1",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=36,
                command=lambda: [dialog.destroy(), self._open_identity_dialog()],
            ).pack(side="left", padx=(0, 8))

        elif cause == "locked_file":
            def do_clean_lock():
                succ, lock_msg = git_service.cleanup_index_lock(project_path)
                dialog.destroy()
                if succ:
                    messagebox.showinfo("Bloqueo Limpiado", lock_msg)
                else:
                    messagebox.showwarning("Error de Bloqueo", lock_msg)
                self.refresh_all_status()

            ctk.CTkButton(
                btn_box,
                text="🔓 Limpiar Bloqueo index.lock",
                fg_color="#d97706",
                hover_color="#b45309",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=36,
                command=do_clean_lock,
            ).pack(side="left", padx=(0, 8))

        elif cause == "merge_in_progress":
            def do_abort_merge():
                succ, m_msg = git_service.abort_merge(project_path)
                dialog.destroy()
                if succ:
                    messagebox.showinfo("Fusión Cancelada", m_msg)
                else:
                    messagebox.showwarning("Error", m_msg)
                self.refresh_all_status()

            ctk.CTkButton(
                btn_box,
                text="↩️ Cancelar Fusión Inconclusa",
                fg_color="#dc2626",
                hover_color="#b91c1c",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=36,
                command=do_abort_merge,
            ).pack(side="left", padx=(0, 8))

        # Botón para crear rama de emergencia
        ctk.CTkButton(
            btn_box,
            text="🌿 Crear Rama de Respaldo",
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=36,
            command=lambda: [dialog.destroy(), self._open_create_branch_dialog()],
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_box,
            text="Cerrar",
            width=90,
            height=36,
            fg_color="#475569",
            hover_color="#334155",
            command=dialog.destroy,
        ).pack(side="right")

    # ==================== SINCRONIZACIÓN EN VIVO (BLOQUE 2) ====================

    def _start_live_sync_loop(self) -> None:
        """Ciclo periódico de comprobación en vivo de cambios remotos en GitHub."""
        try:
            self._run_live_sync_check(show_clean_notice=False)
        finally:
            # Repetir automáticamente cada 90 segundos
            self.after(90000, self._start_live_sync_loop)

    def _manual_check_live_sync(self) -> None:
        """Comprobación manual de cambios al pulsar el botón 'Buscar cambios de otros'."""
        self._set_operation_result("Consultando cambios recientes en GitHub...")
        self._run_live_sync_check(show_clean_notice=True)

    def _run_live_sync_check(self, show_clean_notice: bool = False) -> None:
        """Ejecuta en segundo plano la consulta de cambios del equipo."""
        project_path = config.get_project_path()
        if not git_service.is_git_repository(project_path):
            return

        def task():
            status = git_service.check_collaboration_status(project_path)
            self.last_collab_status = status

            def update_collab_ui():
                if status.get("has_incoming"):
                    author = status.get("latest_author", "Un compañero")
                    time_ago = status.get("latest_time", "hace poco")
                    msg = status.get("latest_message", "")
                    count = status.get("count", 1)

                    notice_text = (
                        f"🔔 ¡Hay {count} cambio(s) nuevo(s) de {author} ({time_ago}) en GitHub!\n"
                        f"Mensaje: \"{msg}\""
                    )
                    self.lbl_collab_notice.configure(
                        text=notice_text,
                        text_color="#fbbf24" if not status.get("has_conflict_risk") else "#f87171",
                    )
                    self.btn_pull_incoming.configure(
                        text=f"📥 Traer cambios de {author} ({count})"
                    )
                    self.collab_actions_row.pack(fill="x", padx=12, pady=(0, 8))
                    self._set_operation_result(f"Hay {count} cambio(s) nuevo(s) en GitHub de {author}.")
                else:
                    self.lbl_collab_notice.configure(
                        text="✓ Tu copia está al día con el repositorio remoto.",
                        text_color="#4ade80",
                    )
                    self.collab_actions_row.pack_forget()
                    if show_clean_notice:
                        self._set_operation_result("Todo actualizado: ningún compañero ha subido cambios nuevos.")

            self.after(0, update_collab_ui)

        threading.Thread(target=task, daemon=True).start()

    def _show_incoming_details(self) -> None:
        """Abre un modal mostrando quién hizo cada commit remoto y cuándo."""
        commits = self.last_collab_status.get("commits", [])
        if not commits:
            messagebox.showinfo("Sin cambios", "No hay cambios pendientes por descargar.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Cambios Nuevos en GitHub")
        dialog.geometry("620x460")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="👥 CAMBIOS REALIZADOS POR TU EQUIPO",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(15, 6))

        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        for c in commits:
            item = ctk.CTkFrame(scroll, corner_radius=8)
            item.pack(fill="x", pady=4, padx=5)

            ctk.CTkLabel(
                item,
                text=c["message"],
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                wraplength=520,
            ).pack(anchor="w", padx=12, pady=(6, 2))

            ctk.CTkLabel(
                item,
                text=f"👤 Autor: {c['author']}  •  🕒 {c['time_ago']}  •  ID: {c['hash']}",
                font=ctk.CTkFont(size=11),
                text_color="gray60",
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(0, 6))

        ctk.CTkButton(dialog, text="Cerrar", width=100, command=dialog.destroy).pack(pady=10)

    def _pull_incoming_changes(self) -> None:
        """Descarga de forma segura los cambios del equipo con detección estricta de conflictos."""
        project_path = config.get_project_path()
        status = self.last_collab_status

        # REGLA DE SEGURIDAD CRÍTICA (Bloque 2):
        # Si hay archivos en conflicto potencial (modificados localmente Y en el remoto)
        if status.get("has_conflict_risk"):
            conflicting = status.get("conflicting_files", [])
            file_list_str = "\n".join([f"  • {f}" for f in conflicting[:8]])

            warn_msg = (
                "⚠️ ¡ATENCIÓN: POSIBLE CONFLICTO DE ARCHIVOS!\n\n"
                "Tú y tu compañero modificaron los mismos archivos sin guardar:\n\n"
                f"{file_list_str}\n\n"
                "Para no sobrescribir ni perder tus cambios locales:\n"
                "1. Primero haz clic en 'Guardar mi versión' para crear un backup local.\n"
                "2. Luego podrás fusionar los cambios de forma segura.\n\n"
                "¿Deseas crear un backup de tu versión ahora?"
            )
            confirm_backup = messagebox.askyesno("Conflicto Detectado", warn_msg)
            if confirm_backup:
                self._open_backup_dialog()
            return

        # Si el usuario tiene cambios locales propios que no chocan, advertir amigablemente
        has_local, local_files = git_service.has_local_changes(project_path)
        if has_local:
            confirm = messagebox.askyesno(
                "Cambios locales",
                "Tienes archivos modificados en tu proyecto.\n\n"
                "¿Deseas descargar los cambios del equipo e integrarlos con tus archivos?",
            )
            if not confirm:
                return

        self._set_busy(True, "Descargando e integrando cambios del equipo...")

        def task():
            success, msg, diag = git_service.pull(project_path)

            def finish():
                self._set_busy(False)
                self.refresh_all_status()
                if success:
                    author = status.get("latest_author", "el equipo")
                    messagebox.showinfo(
                        "✅ Sincronización Exitosa",
                        f"¡Tu proyecto se actualizó correctamente!\n\n"
                        f"Se integraron los cambios de {author} sin perder tu trabajo.",
                    )
                    self._set_operation_result(f"Cambios de {author} integrados con éxito.")
                else:
                    messagebox.showwarning(diag.get("title", "Error"), diag.get("message", msg))
                    self._set_operation_result(f"Error al integrar cambios: {msg}", is_error=True, details=diag)

                # Re-evaluar estado colaborativo
                self._run_live_sync_check(show_clean_notice=False)

            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    # ==================== OPERACIONES: CAMBIAR RAMA ====================

    def _open_branch_dialog(self) -> None:
        project_path = config.get_project_path()
        if not git_service.is_git_repository(project_path):
            messagebox.showwarning("Proyecto no válido", "Por favor selecciona una carpeta de proyecto válida.")
            return

        has_changes, changes = git_service.has_local_changes(project_path)
        if has_changes:
            files_preview = "\n".join([f"  • {c[2:].strip()}" for c in changes[:6]])
            if len(changes) > 6:
                files_preview += f"\n  ... y {len(changes) - 6} archivo(s) más"

            messagebox.showwarning(
                "Cambios sin guardar",
                f"⚠️ Tienes archivos modificados en tu proyecto sin guardar:\n\n"
                f"{files_preview}\n\n"
                "Para no perder tu trabajo ni provocar conflictos, crea un backup antes de cambiar de rama.",
            )
            return

        branches, current_branch = git_service.get_branches(project_path)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Cambiar Rama")
        dialog.geometry("440x360")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="CAMBIAR RAMA", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))
        ctk.CTkLabel(dialog, text=f"Rama actual: {current_branch}", font=ctk.CTkFont(size=13), text_color="#60a5fa").pack(pady=(0, 10))

        frame_branches = ctk.CTkScrollableFrame(dialog, height=150)
        frame_branches.pack(fill="x", padx=30, pady=5)

        selected_branch = tk.StringVar(value=current_branch)

        for b in branches:
            ctk.CTkRadioButton(
                frame_branches,
                text=b,
                variable=selected_branch,
                value=b,
                font=ctk.CTkFont(size=13),
            ).pack(anchor="w", pady=5, padx=10)

        def switch():
            target = selected_branch.get()
            if target == current_branch:
                dialog.destroy()
                return

            dialog.destroy()
            self._set_busy(True, f"Cambiando a la rama '{target}'...")

            def task():
                success, msg, diag = git_service.checkout_branch(project_path, target)

                def finish_ui():
                    self._set_busy(False)
                    if success:
                        self._set_operation_result(f"✅ {msg}")
                        messagebox.showinfo("Rama Cambiada", f"Ahora estás trabajando en la rama '{target}'.")
                    else:
                        self._set_operation_result(f"⚠️ Error: {diag.get('title')}", is_error=True, details=diag)
                        messagebox.showwarning(diag.get("title", "Error"), diag.get("message", msg))
                    self.refresh_all_status()

                self.after(0, finish_ui)

            threading.Thread(target=task, daemon=True).start()

        ctk.CTkButton(
            dialog,
            text="[ CAMBIAR ]",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=switch,
        ).pack(pady=15)

    # ==================== CREAR RAMA NUEVA (BLOQUE 2) ====================

    def _open_create_branch_dialog(self) -> None:
        """Abre el diálogo para crear una rama nueva y opcionalmente publicarla a GitHub."""
        project_path = config.get_project_path()
        if not git_service.is_git_repository(project_path):
            messagebox.showwarning("Proyecto no válido", "Por favor selecciona una carpeta de proyecto válida.")
            return

        branches, current_branch = git_service.get_branches(project_path)
        has_changes, changes = git_service.has_local_changes(project_path)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Crear Rama Nueva")
        dialog.geometry("540x480")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="➕ CREAR RAMA NUEVA", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(16, 4))
        ctk.CTkLabel(
            dialog,
            text=f"Se creará a partir de la rama actual: {current_branch}",
            font=ctk.CTkFont(size=13),
            text_color="#38bdf8",
        ).pack(pady=(0, 12))

        # Campo nombre de rama
        ctk.CTkLabel(dialog, text="Nombre de la nueva rama:", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(fill="x", padx=35, pady=(4, 2))
        txt_branch = ctk.CTkEntry(
            dialog,
            placeholder_text="ej: mi-rama-trabajo, feature-login, respaldo-emergencia",
            height=40,
            font=ctk.CTkFont(size=13),
        )
        txt_branch.pack(fill="x", padx=35, pady=(0, 8))
        txt_branch.focus_set()

        # Opciones avanzadas
        chk_push_var = tk.BooleanVar(value=True)
        chk_push = ctk.CTkCheckBox(
            dialog,
            text="Subir rama a GitHub inmediatamente (git push -u origin <rama>)",
            variable=chk_push_var,
            font=ctk.CTkFont(size=12),
        )
        chk_push.pack(anchor="w", padx=35, pady=6)

        chk_backup_var = tk.BooleanVar(value=has_changes)
        chk_backup = ctk.CTkCheckBox(
            dialog,
            text=f"Guardar también los cambios pendientes en esta nueva rama ({len(changes)} archivo(s))",
            variable=chk_backup_var,
            font=ctk.CTkFont(size=12),
        )
        if has_changes:
            chk_backup.pack(anchor="w", padx=35, pady=6)

        txt_commit_msg = ctk.CTkEntry(
            dialog,
            placeholder_text="Descripción del guardado (ej: Respaldo de emergencia en rama nueva)",
            height=36,
            font=ctk.CTkFont(size=12),
        )
        txt_commit_msg.insert(0, f"Respaldo de trabajo en rama nueva desde {current_branch}")

        def toggle_backup_entry():
            if chk_backup_var.get():
                txt_commit_msg.pack(fill="x", padx=35, pady=(2, 6))
            else:
                txt_commit_msg.pack_forget()

        chk_backup.configure(command=toggle_backup_entry)
        if has_changes:
            toggle_backup_entry()

        lbl_error = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=12), text_color="#f87171")
        lbl_error.pack(pady=4)

        buttons_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=35, pady=12)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        ctk.CTkButton(
            buttons_frame,
            text="[ CANCELAR ]",
            height=42,
            fg_color="#475569",
            hover_color="#334155",
            command=dialog.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def execute_create():
            name = txt_branch.get().strip()
            if not name:
                lbl_error.configure(text="Debes ingresar un nombre para la rama.")
                return
            if " " in name:
                lbl_error.configure(text="El nombre no puede tener espacios. Usa guiones medios '-' o bajos '_'.")
                return

            do_backup = chk_backup_var.get() and has_changes
            commit_text = txt_commit_msg.get().strip() if do_backup else ""
            if do_backup and not commit_text:
                lbl_error.configure(text="Escribe una breve descripción para el backup de la rama.")
                return

            push_remote = chk_push_var.get()

            dialog.destroy()
            self._set_busy(True, f"Creando y cambiando a la rama '{name}'...")

            def task():
                succ, msg, diag = git_service.create_branch(
                    repo_path=project_path,
                    branch_name=name,
                    checkout=True,
                    push_upstream=push_remote,
                )

                if succ and do_backup:
                    self.after(0, lambda: self.lbl_progress_status.configure(text=f"Guardando cambios en '{name}'..."))
                    succ_b, msg_b, diag_b = git_service.create_backup(
                        repo_path=project_path,
                        message=commit_text,
                    )
                    if not succ_b:
                        msg += f"\n\n⚠️ La rama fue creada pero el backup falló: {msg_b}"

                def finish_ui():
                    self._set_busy(False)
                    self.refresh_all_status()
                    if succ:
                        self._set_operation_result(f"✅ Rama '{name}' creada y seleccionada.", details=diag)
                        messagebox.showinfo(
                            "✅ Rama Creada con Éxito",
                            f"¡Ahora estás trabajando en la nueva rama '{name}'!\n\n"
                            f"• Rama base anterior: {current_branch}\n"
                            f"• Rama activa actual: {name}\n"
                            + ("• Subida a GitHub: Sí\n" if push_remote else "• Subida a GitHub: No (solo local)\n")
                            + (f"• Backup guardado: \"{commit_text}\"" if do_backup else "")
                        )
                    else:
                        self._set_operation_result(f"⚠️ Error al crear rama: {msg}", is_error=True, details=diag)
                        messagebox.showwarning(diag.get("title", "Error al crear rama"), diag.get("message", msg))

                self.after(0, finish_ui)

            threading.Thread(target=task, daemon=True).start()

        ctk.CTkButton(
            buttons_frame,
            text="[ CREAR RAMA ]",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=execute_create,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        txt_branch.bind("<Return>", lambda event: execute_create())

    # ==================== OPERACIONES: HISTORIAL ====================

    def _open_history_dialog(self) -> None:
        project_path = config.get_project_path()
        if not git_service.is_git_repository(project_path):
            messagebox.showwarning("Proyecto no válido", "Por favor selecciona una carpeta de proyecto válida.")
            return

        commits = git_service.get_commit_history(project_path, limit=20)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Historial de Backups")
        dialog.geometry("640x520")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="📜 HISTORIAL DE BACKUPS", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))

        if not commits:
            ctk.CTkLabel(
                dialog,
                text="No se encontraron backups o commits previos en este proyecto.",
                font=ctk.CTkFont(size=13),
                text_color="gray70",
            ).pack(pady=30)
            return

        list_frame = ctk.CTkScrollableFrame(dialog)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        for c in commits:
            item = ctk.CTkFrame(list_frame, corner_radius=8)
            item.pack(fill="x", pady=5, padx=5)

            ctk.CTkLabel(
                item,
                text=c["message"],
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                wraplength=540,
            ).pack(anchor="w", padx=12, pady=(8, 2))

            meta_text = f"👤 {c['author']}  •  🕒 {c['time_ago']}  •  ID: {c['hash']}"
            ctk.CTkLabel(
                item,
                text=meta_text,
                font=ctk.CTkFont(size=11),
                text_color="gray60",
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(0, 8))

        ctk.CTkButton(dialog, text="Cerrar", width=100, command=dialog.destroy).pack(pady=10)

    # ==================== IDENTIDAD GIT Y CONFIGURACIÓN ====================

    def _open_identity_dialog(self) -> None:
        """Permite configurar user.name y user.email de Git."""
        project_path = config.get_project_path()
        cur_name, cur_email = git_service.get_git_identity(project_path)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Identidad Git y Ajustes")
        dialog.geometry("540x420")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="⚙️ IDENTIDAD DE GIT", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 10))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=30, pady=10)

        ctk.CTkLabel(form, text="Nombre del autor (user.name):", anchor="w").pack(fill="x", pady=(5, 2))
        txt_name = ctk.CTkEntry(form, height=36)
        txt_name.pack(fill="x", pady=2)
        if cur_name:
            txt_name.insert(0, cur_name)

        ctk.CTkLabel(form, text="Correo electrónico (user.email):", anchor="w").pack(fill="x", pady=(8, 2))
        txt_email = ctk.CTkEntry(form, height=36)
        txt_email.pack(fill="x", pady=2)
        if cur_email:
            txt_email.insert(0, cur_email)

        chk_global_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(form, text="Guardar para toda la computadora (Global)", variable=chk_global_var).pack(anchor="w", pady=12)

        def save_id():
            n = txt_name.get().strip()
            e = txt_email.get().strip()
            if not n or not e:
                messagebox.showwarning("Campos requeridos", "Nombre y correo son necesarios.")
                return

            succ, msg = git_service.set_git_identity(n, e, project_path, is_global=chk_global_var.get())
            if succ:
                messagebox.showinfo("Identidad Git", "✓ Identidad configurada correctamente.")
                dialog.destroy()
                self.refresh_all_status()
            else:
                messagebox.showerror("Error", msg)

        ctk.CTkButton(
            dialog,
            text="[ GUARDAR CONFIGURACIÓN ]",
            height=40,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=save_id,
        ).pack(pady=15)


def start_app() -> None:
    app = GitManagerApp()
    app.mainloop()
