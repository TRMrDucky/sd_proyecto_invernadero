// URL base del servidor Flask local
const API_URL = "http://127.0.0.1:5000";

// Referencias a los elementos del DOM (HTML)
const loginForm = document.getElementById('loginForm');
const responseConsole = document.getElementById('responseConsole');

/**
 * Imprime logs formateados con marcas de tiempo en la consola visual del HTML.
 * @param {string} message - Mensaje a mostrar.
 * @param {boolean} isError - Determina si el texto se pinta en rojo o verde.
 */
function log(message, isError = false) {
    const timestamp = new Date().toLocaleTimeString();
    const colorClass = isError ? 'text-red-400' : 'text-green-400';
    responseConsole.innerHTML = `[${timestamp}] <span class="${colorClass}">${message}</span>\n` + responseConsole.innerHTML;
}

// Escuchador del evento de envío del formulario
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault(); // Detiene la recarga automática de la página

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    log("Enviando credenciales al clúster...");

    try {
        // Petición HTTP POST hacia el endpoint de Login en Flask
        const response = await fetch(`${API_URL}/api/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        // Control de respuestas de error del servidor (e.g., 400, 401, 500)
        if (!response.ok) {
            log(`Error ${response.status}: ${data.error || 'Credenciales inválidas'}`, true);
            return;
        }

        // Si la autenticación es exitosa (Status 200)
        log(`¡Éxito! Token recibido.`);
        log(`Bienvenido: ${data.usuario.nombre}`);
        
        // Guardamos el token de forma segura en el sessionStorage del navegador
        sessionStorage.setItem('jwt_token', data.token);
        
        log(`JWT guardado con éxito en el navegador:\n${data.token.substring(0, 45)}...`);

    } catch (error) {
        // Captura errores de red, por ejemplo, si el servidor Flask está apagado
        log(`Error de red: No se pudo establecer conexión con ${API_URL}. Verifiquen que Flask esté corriendo.`, true);
    }
});