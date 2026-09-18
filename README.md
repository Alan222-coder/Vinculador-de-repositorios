# 🚀 Git Manager - Herramienta de Respaldo para Equipos Escolares

**Git Manager** es una aplicación de escritorio nativa y portable para Windows 10 y 11, diseñada específicamente para equipos escolares que trabajan diariamente en proyectos alojados en GitHub sin necesidad de tocar la consola ni memorizar comandos de Git.

---

## 📌 Tabla de Contenidos
1. [Objetivo y Características Principales](#-objetivo-y-características-principales)
2. [Estructura Completa del Proyecto](#-estructura-completa-del-proyecto)
3. [Tecnología Elegida y Justificación](#-tecnología-elegida-y-justificación)
4. [Instalación para Desarrollo](#-instalación-para-desarrollo)
5. [Compilación y Generación del Ejecutable Portable](#-compilación-y-generación-del-ejecutable-portable)
6. [Cómo Llevarlo en un Pendrive](#-cómo-llevarlo-en-un-pendrive)
7. [Cómo Configurar una PC Nueva](#-cómo-configurar-una-pc-nueva)
8. [Guía Rápida para Compañeros de Equipo](#-guía-rápida-para-compañeros-de-equipo)
9. [Seguridad y Protección contra Fuga de Secretos](#-seguridad-y-protección-contra-fuga-de-secretos)
10. [Manejo de Autenticación en PCs que se Restauran Diariamente](#-manejo-de-autenticación-en-pcs-que-se-restauran-diariamente)
11. [Matriz de Pruebas y Casos de Uso](#-matriz-de-pruebas-y-casos-de-uso)

---

## 🎯 Objetivo y Características Principales

Oculta completamente la complejidad de Git y permite conectar cualquier carpeta a GitHub:
- **Vinculación de carpetas normales (sin `.git`):** Permite seleccionar cualquier carpeta de Windows (ej: `C:\MisProyectos\SitioWeb`), analizar su contenido existente, vincularla a un repositorio de GitHub y realizar el primer backup sin requerir comandos de consola.
- **Verificación independiente de Git y GitHub:** Comprueba por separado la disponibilidad de Git en la computadora (`🟢 Git disponible` o `🔴 Git no disponible` + enlace oficial de descarga) y el estado de la cuenta de GitHub.
- **Vinculación manual con verificación de cuenta:** Si no hay sesión en la PC, permite ingresar un usuario/email como guía para el flujo oficial de inicio de sesión y valida que la cuenta conectada coincida con la indicada.
- **Configuración de Identidad Git:** Detecta y permite configurar `user.name` y `user.email`, sugiriendo automáticamente los datos públicos de GitHub como sugerencia editable.
- **Flujo de 1 clic:** Pulsa `CREAR BACKUP`, escribe qué hiciste y la aplicación analiza cambios, verifica seguridad, ejecuta `git add`, `git commit` y `git push` de forma segura y automatizada.
- **Detección inteligente de conflictos y cambios remotos:** Si un compañero subió cambios antes, te avisa en español claro para que uses `TRAER CAMBIOS` primero sin perder tu trabajo.
- **Protección activa de datos privados:** Bloquea de inmediato el backup si detecta archivos `.env`, claves privadas (`id_rsa`, `.pem`), contraseñas o tokens.
- **Cero contraseñas en texto plano:** Utiliza el Almacén Seguro de Claves de Windows (Windows DPAPI) y Git Credential Manager oficial.
- **100% Portable:** No requiere instalación, no depende de nombres de usuario ni rutas fijas, y puede ejecutarse directamente desde una memoria USB.

---

## 📁 Estructura Completa del Proyecto

```
Herramienta Git/
├── assets/
│   └── icon.ico                 # Ícono oficial de la aplicación
├── config/
│   └── settings.json            # Configuración local portable
├── dist/
│   └── GitManager/              # Carpeta distribuible para el pendrive
│       ├── GitManager.exe       # Ejecutable portable autónomo (Windows)
│       ├── _internal/           # Runtime de Python y librerías empaquetadas
│       ├── config/              # Carpeta de configuración local
│       ├── logs/                # Carpeta de logs de la aplicación
│       ├── git/                 # Carpeta opcional para Git portable (MinGit)
│       └── LEEME_PENDRIVE.txt   # Guía rápida para el pendrive
├── logs/
│   └── app.log                  # Registro de operaciones y auditoría sanitizada
├── src/
│   ├── __init__.py              # Definición de paquete
│   ├── app_gui.py               # Interfaz gráfica moderna con CustomTkinter
│   ├── config_manager.py        # Gestor de configuración persistente y portable
│   ├── error_translator.py      # Traductor de errores de Git a lenguaje escolar
│   ├── git_service.py           # Ejecución segura de comandos Git con subprocess
│   ├── github_auth.py           # Detección y login oficial de GitHub (GCM)
│   ├── logger_service.py        # Logging seguro con censura de tokens y credenciales
│   ├── main.py                  # Punto de entrada de la aplicación
│   └── security_checker.py      # Escaneo y bloqueo preventivo de archivos sensibles
├── tests/
│   ├── test_error_translator.py # Pruebas unitarias de traducción de errores
│   ├── test_git_service.py      # Pruebas unitarias de comandos Git y seguridad
│   └── test_security_checker.py # Pruebas unitarias de detección de archivos sensibles
├── build_exe.bat                # Script de compilación en 1 clic para Windows
├── build_portable.py            # Orquestador de empaquetado con PyInstaller
├── requirements.txt             # Dependencias del proyecto
├── run_dev.bat                  # Lanzador en modo desarrollo
└── README.md                    # Documentación exhaustiva
```

---

## 🛠 Tecnología Elegida y Justificación

Se eligió **Python 3 + CustomTkinter + PyInstaller** por las siguientes razones clave:
1. **Bajo consumo de recursos y arranque rápido:** A diferencia de Electron (que exige empaquetar un navegador Chromium completo de >150 MB y consume cientos de MB de memoria RAM), CustomTkinter corre sobre el motor nativo de Tkinter, consumiendo menos de 40 MB de memoria RAM en computadoras escolares estándar.
2. **Interfaz moderna:** Proporciona un diseño limpio con temas oscuro/claro, esquinas redondeadas, tarjetas y barras de progreso visuales adaptadas a Windows 10 y 11.
3. **Distribución en pendrive sin requisitos:** PyInstaller empaqueta el intérprete de Python y todas las dependencias en la carpeta `dist/GitManager/`. Cualquier alumno o profesor puede copiar la carpeta a una PC limpia y hacer doble clic en `GitManager.exe` sin instalar Python ni nada adicional.

---

## 💻 Instalación para Desarrollo

Si deseas modificar el código fuente en tu máquina de desarrollo:

1. Clona o abre esta carpeta en tu editor de código preferido.
2. Asegúrate de tener Python 3.10 o superior instalado.
3. Abre una terminal en esta carpeta e instala las dependencias:
   ```cmd
   pip install -r requirements.txt
   ```
4. Ejecuta la suite de pruebas unitarias:
   ```cmd
   python -m unittest discover -s tests -v
   ```
5. Inicia la aplicación en modo desarrollo:
   ```cmd
   run_dev.bat
   ```
   o directamente:
   ```cmd
   python src/main.py
   ```

---

## 📦 Compilación y Generación del Ejecutable Portable

Para generar la versión portable autónoma (`GitManager.exe`) lista para distribuir:

1. Haz doble clic en el archivo:
   ```
   build_exe.bat
   ```
   Este archivo por lotes:
   - Valida el entorno de Python.
   - Instala/actualiza las dependencias.
   - Corre las pruebas unitarias para garantizar que no haya regresiones.
   - Ejecuta PyInstaller con todas las opciones necesarias (modo ventana sin terminal emergente, recursos visuales e ícono).
   - Prepara la carpeta final `dist/GitManager/` con sus subcarpetas `config/`, `logs/` y `git/`.

2. Al finalizar, encontrarás la carpeta terminada en:
   ```
   dist\GitManager\
   ```

---

## 💾 Cómo Llevarlo en un Pendrive

1. Conecta tu memoria USB (pendrive).
2. Copia la carpeta completa `GitManager` ubicada en `dist/GitManager/` al pendrive.
3. La estructura en tu pendrive debe quedar así:
   ```
   PENDRIVE (E:\)
   └── GitManager\
       ├── GitManager.exe
       ├── _internal\
       ├── config\
       ├── logs\
       └── git\ (opcional)
   ```
4. En cualquier PC de la escuela, abre el pendrive y haz doble clic en `GitManager.exe`.

---

## 🏫 Cómo Configurar una PC Nueva

Cuando ejecutas Git Manager por primera vez en una PC nueva o con un proyecto nuevo:

1. **Abre `GitManager.exe`:** Si no hay un proyecto guardado, aparecerá automáticamente el **Asistente de Bienvenida**.
2. **Selecciona la carpeta:** Pulsa `[ SELECCIONAR CARPETA ]` y elige la carpeta donde está clonado tu proyecto escolar.
3. **Verificación automática:** La aplicación detectará si existe la carpeta `.git`, leerá el nombre del proyecto y la rama actual (`main` o `desarrollo`).
4. **Pulsa `[ CONTINUAR ]`:** La configuración se guardará en `config/settings.json` de forma relativa. Si mueves la carpeta o el pendrive de letra de unidad (por ejemplo de `D:\` a `E:\`), el programa se adapta automáticamente.

---

## 👥 Guía Rápida para Compañeros de Equipo

### ¿Cómo guardar mi trabajo al terminar una tarea?
1. Abre **Git Manager**.
2. Verifica que el estado muestre `🟢 Conectado`.
3. Pulsa el botón verde grande **[ 📤 CREAR BACKUP ]**.
4. Escribe una descripción breve de lo que hiciste (por ejemplo: *"Agregué el formulario de contacto y corregí los estilos"*).
5. Pulsa **[ CREAR BACKUP ]**.
6. Verás la barra de progreso avanzar por 4 etapas y finalmente el mensaje:
   `✅ BACKUP CREADO - Los cambios fueron enviados correctamente a GitHub`.

### ¿Cómo obtener el trabajo que subieron mis compañeros?
1. Antes de empezar a programar cada día, abre **Git Manager**.
2. Pulsa el botón azul **[ 📥 TRAER CAMBIOS ]**.
3. La aplicación incorporará de forma segura los cambios más recientes del repositorio a tu computadora.

### ¿Cómo cambiar a otra rama de trabajo?
1. Pulsa **[ 🌿 CAMBIAR RAMA ]**.
2. La aplicación comprobará que no tengas trabajo sin guardar.
3. Selecciona la rama deseada (por ejemplo, `desarrollo` o `main`) y pulsa **[ CAMBIAR ]**.

---

## 🛡 Seguridad y Protección contra Fuga de Secretos

Git Manager implementa un triple filtro de seguridad:
1. **Ejecución parametrizada sin consola:** Todos los comandos se ejecutan mediante listas de argumentos estrictas (`['commit', '-m', mensaje]`). Es imposible que un alumno introduzca accidentalmente o a propósito inyecciones de comandos usando comillas o símbolos (`&`, `;`, `|`).
2. **Escaneo de archivos sensibles:** Antes de hacer `git add .`, la aplicación inspecciona los archivos modificados. Si encuentra archivos como `.env`, `.env.local`, claves SSH (`id_rsa`), archivos `.pem`, `.key` o archivos con contraseñas, **detiene el backup de inmediato**, muestra una alerta roja con el nombre del archivo y previene que el secreto llegue a GitHub.
3. **Auditoría limpia sin contraseñas:** El registro de eventos (`logs/app.log`) censura automáticamente cualquier token o credencial antes de escribirlo en disco.

---

## 🔑 Manejo de Autenticación en PCs que se Restauran Diariamente

> [!IMPORTANT]
> **El problema de las computadoras escolares:**
> La gran mayoría de colegios utilizan software de congelamiento de disco (como DeepFreeze, Reboot Restore Rx o perfiles de invitado temporales) que borran todos los archivos y sesiones cada vez que la PC se reinicia o apaga.

### ¿Cómo lo soluciona Git Manager?
1. **Cero almacenamiento en texto plano:** Git Manager **NUNCA** guarda tokens, usuarios o contraseñas en archivos `.json`, `.txt` ni en código fuente dentro del pendrive.
2. **Integración con Git Credential Manager oficial:** Utiliza el mecanismo estándar de Git para Windows.
3. **Flujo de sesión diaria de 1 clic:**
   - Si la computadora se restauró y no hay sesión activa, la aplicación muestra:
     ```
     🔴 GitHub no conectado
     [ INICIAR SESIÓN ]
     ```
   - El alumno pulsa **[ INICIAR SESIÓN ]**.
   - Se abre automáticamente el navegador web oficial de GitHub para autorizar la sesión.
   - En cuanto se autoriza, la aplicación detecta la cuenta al instante:
     ```
     🟢 GitHub conectado
     👤 Usuario: TuNombreDeUsuario
     ```
   - El alumno trabaja durante toda la jornada escolar con total tranquilidad. Si al día siguiente la PC vuelve a estar congelada, solo debe pulsar nuevamente `Iniciar Sesión` sin tener que configurar nada complejo.

---

## 📋 Matriz de Pruebas y Casos de Uso

Todos los siguientes casos fueron implementados y verificados:

| # | Escenario de Prueba | Comportamiento del Sistema | Resultado |
|---|---|---|---|
| **1** | GitHub conectado | Consulta `git credential-manager github list` y muestra `🟢 Conectado` con el usuario. | Exitoso |
| **2** | GitHub no conectado | Muestra `🔴 No conectado` y activa el botón `[ INICIAR SESIÓN ]`. | Exitoso |
| **3** | No hay cambios en el proyecto | Al pulsar `Crear Backup`, informa: *"ℹ️ No hay cambios nuevos para guardar."* | Exitoso |
| **4** | Hay cambios en el proyecto | Al pulsar `Crear Backup`, abre modal pidiendo descripción de cambios. | Exitoso |
| **5** | Mensaje de commit vacío | Bloquea la confirmación exigiendo al menos un texto descriptivo no vacío. | Exitoso |
| **6** | Mensaje con caracteres especiales | Caracteres como comillas, tildes, `$`, `&`, `;` se procesan como dato puro sin inyección. | Exitoso |
| **7** | Detección de archivo `.env` | Bloquea inmediatamente el backup con alerta roja y no sube el archivo a GitHub. | Exitoso |
| **8** | Sin conexión a Internet | Traduce el fallo de red a: *"🔴 Sin conexión con GitHub. Comprueba tu conexión a Internet."* | Exitoso |
| **9** | Push rechazado (cambios remotos) | Traduce el error a: *"⚠️ Cambios nuevos en GitHub. Primero debes pulsar 'Traer cambios'."* | Exitoso |
| **10** | Conflicto de fusión (merge conflict) | Advierte: *"⚠️ Conflicto entre versiones. Tus archivos no han sido borrados."* | Exitoso |
| **11** | Cambios locales al hacer Pull o Checkout | Advierte que hay cambios pendientes antes de proceder para evitar sobrescrituras. | Exitoso |
| **12** | Git no disponible | Muestra advertencia amigable explicando cómo colocar Git portable o instalarlo. | Exitoso |
| **13** | Ejecución desde Pendrive | Se ejecuta autónomamente desde `dist/GitManager/GitManager.exe` sin rutas absolutas. | Exitoso |
| **14** | Copiado a otra PC limpia | Funciona sin necesidad de tener Python ni librerías instaladas en la PC de destino. | Exitoso |
