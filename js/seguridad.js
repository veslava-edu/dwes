// docs/js/custom.js

/**
 * Muestra un prompt para pedir una contraseña y, si es correcta, revela el bloque de la solución correspondiente.
 * @param {string} exerciseId - Un identificador único para el ejercicio (ej: 'arq-01', 'glosario-innovatech').
 */
function showSolutionPrompt(exerciseId) {
  let correctPassword;

  // 1. Asigna la contraseña correcta según el ID del ejercicio.
  // ¡Añade aquí tantos casos como ejercicios tengas!
  switch (exerciseId) {
    case 'UD1-1':
      correctPassword = 'cliente-servidor';
      break;
    case 'UD1-2':
      correctPassword = 'http';
      break;
    case 'db-05':
      correctPassword = 'persistencia_nexus';
      break;
    default:
      // Si el ID del ejercicio no se encuentra, muestra un error y detiene la ejecución.
      console.error("Error: ID de ejercicio no reconocido:", exerciseId);
      alert("Error de configuración: No se ha encontrado el ejercicio.");
      return;
  }

  // 2. Pide al usuario la contraseña.
  const enteredPassword = prompt(`Introduce la contraseña para ver la solución del ejercicio "${exerciseId}":`);

  // Si el usuario presiona "Cancelar", no hagas nada.
  if (enteredPassword === null) {
    return;
  }

  // 3. Compara la contraseña introducida con la correcta.
  if (enteredPassword === correctPassword) {
    // Si es correcta, construye el ID del bloque de solución (ej: 'solution-arq-01')
    const solutionBlock = document.getElementById('solution-' + exerciseId);
    
    if (solutionBlock) {
      // Muestra el bloque
      solutionBlock.style.display = 'block';
    } else {
      console.error("Error: No se encontró el bloque de solución con el ID: solution-" + exerciseId);
      alert("Error de configuración: No se encuentra el contenido de la solución.");
    }
  } else {
    // Si es incorrecta, avisa al usuario.
    alert("Contraseña incorrecta.");
  }
}