// URL base de su servidor Flask
const API_URL = "http://127.0.0.1:5000";

const registerForm = document.getElementById('registerForm');
const responseConsole = document.getElementById('responseConsole');

/**
 * Imprime logs formateados con marcas de tiempo en la consola integrada.
 */
function log(message, isError = false) {
    const timestamp = new Date().toLocaleTimeString();
    const colorClass = isError ? 'text-red-400' : 'text-green-400';
    responseConsole.innerHTML = `[${timestamp}] <span class="${colorClass}">${message}</span>\n` + responseConsole.innerHTML;
}

// Escuchar el evento de envío del formulario de registro
registerForm.addEventListener('submit', async (e) => {
    e.preventDefault(); // Evita que la página se refresque

    // Captura de datos del DOM
    const nombre = document.getElementById('nombre').value;
    const email = document.getElementById('email').value;
    const telefono = document.getElementById('telefono').value;
    const password = document.getElementById('password').value;

    log("Enviando paquete de registro a la API REST...");

    try {
        // Petición HTTP POST al endpoint de registro
        const response = await fetch(`${API_URL}/api/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nombre, email, telefono, password })
        });

        const data = await response.json();

        // Control de errores enviados por Flask (ej. 400 Bad Request, 500 DB Error)
        if (!response.ok) {
            log(`Error ${response.status}: ${data.error || 'No se pudo completar el registro'}`, true);
            return;
        }

        // Si el registro es exitoso (Status 201 Created)
        log(`¡Usuario registrado con éxito! ID asignado: ${data.id}`);
        log("Redireccionando al inicio de sesión en 2 segundos...");

        // Desactivar el botón para evitar doble envío accidental
        registerForm.querySelector('button').disabled = true;

        // Redirección automática al index de Login para que prueben sus credenciales
        setTimeout(() => {
            window.location.href = "../HTML/login.html";
        }, 2000);

    } catch (error) {
        // Error de red
        log(`Error de red: Imposible conectar con el clúster en ${API_URL}. ¿Está encendido Flask?`, true);
    }
});