document.getElementById("sensorForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const sensor = {
    marca: document.getElementById("marca").value,
    modelo: document.getElementById("modelo").value,
    ubicacion: document.getElementById("ubicacion").value,
    estado: parseInt(document.getElementById("estado").value),
    id_invernadero: parseInt(document.getElementById("id_invernadero").value),
  };

  try {
    const response = await fetch("http://localhost:5000/sensores", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(sensor),
    });

    const data = await response.json();

    console.log(data);

    alert("Sensor registrado");
  } catch (error) {
    console.error(error);

    alert("Error al registrar");
  }
});
