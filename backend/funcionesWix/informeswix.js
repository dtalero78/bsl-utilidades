import wixData from 'wix-data';
import { callOpenAI } from 'backend/OpenAI'; // Importa la función del backend
import moment from 'moment';
import 'moment/locale/es';

let codEmpresa;
let historiaIds = []; // Variable global para almacenar los IDs de HistoriaClinica
let empresaTitle;

$w.onReady(function () {});

$w('#buscar').onClick(async () => {
    const fechaInicio = $w('#datePicker1').value;
    const fechaFin = $w('#datePicker2').value;
    codEmpresa = $w('#codEmpresa').value;

    if (!fechaInicio || !fechaFin) {
        console.error("Por favor selecciona un rango de fechas válido.");
        return;
    }

    try {
        $w('#loading').show();

        // Consulta en HistoriaClinica
        const historiaClinicaResults = await wixData.query("HistoriaClinica")
            .eq("codEmpresa", codEmpresa)
            .between("fechaConsulta", fechaInicio, fechaFin)
            .limit(1000)
            .find();

        const totalAtenciones = historiaClinicaResults.items.length;
        console.log("Total de atenciones:", totalAtenciones);

        if (totalAtenciones === 0) {
            console.log("No hay registros en HistoriaClinica para los criterios dados.");
            return;
        }

        // Guardar los _id de HistoriaClinica en la variable global
        historiaIds = historiaClinicaResults.items.map(item => item._id);
        console.log("IDs de HistoriaClinica almacenados:", historiaIds);

        // Consulta en EMPRESAS
        console.log("CodEmpresa para el query", codEmpresa)
        const empresaQuery = wixData.query("EMPRESAS").eq("codEmpresa", codEmpresa).limit(1000).find();
        const results = await empresaQuery;
        console.log("resultados query", results)

        if (results && results.items && results.items.length > 0) {
            $w('#empresaNit').text = results.items[0].nit.toString();
            empresaTitle = results.items[0].empresa.toString();
            codEmpresa = results.items[0].codEmpresa.toString();
                        console.log("empresa encontrada", empresaTitle)
            $w('#empresaName').text = empresaTitle;
            $w('#empresa').text = empresaTitle;
            $w('#portada').show();
            $w('#search').hide();
        }

    } catch (error) {
        console.error("Error al consultar los datos:", error);
    } finally {
        $w('#loading').hide();
        $w('#tituloInicial').text = "Período: " + moment(fechaInicio, 'MMDDYYYY').format('MMMM D YYYY').toUpperCase() + " - " + moment(fechaFin, 'MMDDYYYY').format('MMMM D YYYY').toUpperCase();
        console.log("Proceso finalizado");
const today = new Date();
$w('#fechaElaboracion').text = today.toLocaleDateString();    }
});


// Botón "genero" para ejecutar la consulta en FORMULARIO y llamar a OpenAI
$w('#genero').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar géneros en FORMULARIO
        const { totalCoincidencias, totalMasculino, totalFemenino, porcentajeMasculino, porcentajeFemenino } =
        await contarGeneroEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log("Total Masculino:", totalMasculino, `(${porcentajeMasculino.toFixed(2)}%)`);
        console.log("Total Femenino:", totalFemenino, `(${porcentajeFemenino.toFixed(2)}%)`);

        // Crear el prompt para OpenAI
        const prompt = `Según los porcentajes de población de la empresa ${codEmpresa}, 
        el ${porcentajeMasculino.toFixed(2)}% son hombres y el ${porcentajeFemenino.toFixed(2)}% son mujeres. 
        Sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones`;

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un elemento de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#aiGenero').value = response.choices[0].message.content;
        } else {
            $w('#aiGenero').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar género en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
});

// Función para contar coincidencias en FORMULARIO y analizar el campo "genero"
async function contarGeneroEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)
            .find();

        const totalCoincidencias = formularioResults.items.length;

        // Contar cuántos registros tienen "MASCULINO" y cuántos "FEMENINO"
        let totalMasculino = 0;
        let totalFemenino = 0;

        formularioResults.items.forEach(item => {
            if (item.genero && item.genero.toUpperCase() === "MASCULINO") {
                totalMasculino++;
            } else if (item.genero && item.genero.toUpperCase() === "FEMENINO") {
                totalFemenino++;
            }
        });

        // Calcular porcentajes
        const porcentajeMasculino = totalCoincidencias > 0 ? (totalMasculino / totalCoincidencias) * 100 : 0;
        const porcentajeFemenino = totalCoincidencias > 0 ? (totalFemenino / totalCoincidencias) * 100 : 0;

        // Mostrar porcentajes en la interfaz de Wix
        $w('#porcentajeMasculino').text = Math.round(porcentajeMasculino).toString() + '%';
        $w('#porcentajeFemenino').text = Math.round(porcentajeFemenino).toString() + '%';

        return { totalCoincidencias, totalMasculino, totalFemenino, porcentajeMasculino, porcentajeFemenino };

    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return { totalCoincidencias: 0, totalMasculino: 0, totalFemenino: 0, porcentajeMasculino: 0, porcentajeFemenino: 0 };
    }
}

// Botón para contar edades en FORMULARIO y generar recomendaciones de OpenAI
$w('#edad').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar edades en FORMULARIO
        const {
            totalCoincidencias,
            rango1,
            rango2,
            rango3,
            rango4,
            rango5,
            porcentaje1,
            porcentaje2,
            porcentaje3,
            porcentaje4,
            porcentaje5
        } = await contarEdadEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log(`15-20 años: ${rango1} (${porcentaje1.toFixed(2)}%)`);
        console.log(`21-30 años: ${rango2} (${porcentaje2.toFixed(2)}%)`);
        console.log(`31-40 años: ${rango3} (${porcentaje3.toFixed(2)}%)`);
        console.log(`41-50 años: ${rango4} (${porcentaje4.toFixed(2)}%)`);
        console.log(`Mayor a 50 años: ${rango5} (${porcentaje5.toFixed(2)}%)`);

        // Crear el prompt para OpenAI
        const prompt = `Según los porcentajes de población de la empresa ${codEmpresa}, 
        hay un ${porcentaje1.toFixed(2)}% de personas entre 15-20 años, 
        un ${porcentaje2.toFixed(2)}% entre 21-30 años, 
        un ${porcentaje3.toFixed(2)}% entre 31-40 años, 
        un ${porcentaje4.toFixed(2)}% entre 41-50 años y 
        un ${porcentaje5.toFixed(2)}% mayores a 50 años. 
        Eres médico laboral y estás elaborando el informe de condiciones de salud. 
        Sugiere exactamente dos recomendaciones breves (una frase cada una) para cada grupo de edad. 
        No incluyas introducciones. No uses markdown.;`;

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#edadAi').value = response.choices[0].message.content;
        } else {
            $w('#edadAi').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar edades en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
});

// Función para contar coincidencias en FORMULARIO y agrupar por edad
async function contarEdadEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)
            .find();

        const totalCoincidencias = formularioResults.items.length;

        // Contadores para cada rango de edad
        let rango1 = 0; // 15-20 años
        let rango2 = 0; // 21-30 años
        let rango3 = 0; // 31-40 años
        let rango4 = 0; // 41-50 años
        let rango5 = 0; // Mayor a 50 años

        formularioResults.items.forEach(item => {
            if (item.edad) {
                const edad = parseInt(item.edad, 10);
                if (edad >= 15 && edad <= 20) {
                    rango1++;
                } else if (edad >= 21 && edad <= 30) {
                    rango2++;
                } else if (edad >= 31 && edad <= 40) {
                    rango3++;
                } else if (edad >= 41 && edad <= 50) {
                    rango4++;
                } else if (edad > 50) {
                    rango5++;
                }
            }
        });

        // Calcular porcentajes
        const porcentaje1 = totalCoincidencias > 0 ? (rango1 / totalCoincidencias) * 100 : 0;
        const porcentaje2 = totalCoincidencias > 0 ? (rango2 / totalCoincidencias) * 100 : 0;
        const porcentaje3 = totalCoincidencias > 0 ? (rango3 / totalCoincidencias) * 100 : 0;
        const porcentaje4 = totalCoincidencias > 0 ? (rango4 / totalCoincidencias) * 100 : 0;
        const porcentaje5 = totalCoincidencias > 0 ? (rango5 / totalCoincidencias) * 100 : 0;

        // Mostrar porcentajes en la interfaz de Wix
        $w('#rangoEdad1').text = Math.round(porcentaje1).toString() + '%';
        $w('#rangoEdad2').text = Math.round(porcentaje2).toString() + '%';
        $w('#rangoEdad3').text = Math.round(porcentaje3).toString() + '%';
        $w('#rangoEdad4').text = Math.round(porcentaje4).toString() + '%';
        $w('#rangoEdad5').text = Math.round(porcentaje5).toString() + '%';

        return { totalCoincidencias, rango1, rango2, rango3, rango4, rango5, porcentaje1, porcentaje2, porcentaje3, porcentaje4, porcentaje5 };

    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return { totalCoincidencias: 0, rango1: 0, rango2: 0, rango3: 0, rango4: 0, rango5: 0, porcentaje1: 0, porcentaje2: 0, porcentaje3: 0, porcentaje4: 0, porcentaje5: 0 };
    }
}

// Botón para contar estado civil en FORMULARIO y generar recomendaciones de OpenAI
$w('#estadoCivilBtn').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar estado civil en FORMULARIO
        const {
            totalCoincidencias,
            soltero,
            casado,
            divorciado,
            viudo,
            unionLibre,
            porcentajeSoltero,
            porcentajeCasado,
            porcentajeDivorciado,
            porcentajeViudo,
            porcentajeUnionLibre
        } = await contarEstadoCivilEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log(`Soltero: ${soltero} (${porcentajeSoltero.toFixed(2)}%)`);
        console.log(`Casado: ${casado} (${porcentajeCasado.toFixed(2)}%)`);
        console.log(`Divorciado: ${divorciado} (${porcentajeDivorciado.toFixed(2)}%)`);
        console.log(`Viudo: ${viudo} (${porcentajeViudo.toFixed(2)}%)`);
        console.log(`Unión Libre: ${unionLibre} (${porcentajeUnionLibre.toFixed(2)}%)`);

        // Crear el prompt para OpenAI
        const prompt = `Según los porcentajes de población de la empresa ${codEmpresa}, 
        hay un ${porcentajeSoltero.toFixed(2)}% de personas solteras, 
        un ${porcentajeCasado.toFixed(2)}% casadas, 
        un ${porcentajeDivorciado.toFixed(2)}% divorciadas, 
        un ${porcentajeViudo.toFixed(2)}% viudas y 
        un ${porcentajeUnionLibre.toFixed(2)}% en unión libre. 
        Eres médico laboral y estás elaborando el informe de condiciones de salud. 
        Sugiere exactamente a la empresa dos recomendaciones breves (una frase cada una) para cada grupo. 
        No incluyas introducciones. No uses markdown.;`;

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#estadoCivil').value = response.choices[0].message.content;
        } else {
            $w('#estadoCivil').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar estado civil en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
})

// Función para contar coincidencias en FORMULARIO y agrupar por estado civil
async function contarEstadoCivilEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)
            .find();

        const totalCoincidencias = formularioResults.items.length;

        // Contadores para cada estado civil
        let soltero = 0;
        let casado = 0;
        let divorciado = 0;
        let viudo = 0;
        let unionLibre = 0;

        formularioResults.items.forEach(item => {
            if (item.estadoCivil) {
                const estado = item.estadoCivil.toUpperCase().trim();
                if (estado === "SOLTERO") {
                    soltero++;
                } else if (estado === "CASADO") {
                    casado++;
                } else if (estado === "DIVORCIADO") {
                    divorciado++;
                } else if (estado === "VIUDO") {
                    viudo++;
                } else if (estado === "UNIÓN LIBRE" || estado === "UNION LIBRE") {
                    unionLibre++;
                }
            }
        });

        // Calcular porcentajes
        const porcentajeSoltero = totalCoincidencias > 0 ? (soltero / totalCoincidencias) * 100 : 0;
        const porcentajeCasado = totalCoincidencias > 0 ? (casado / totalCoincidencias) * 100 : 0;
        const porcentajeDivorciado = totalCoincidencias > 0 ? (divorciado / totalCoincidencias) * 100 : 0;
        const porcentajeViudo = totalCoincidencias > 0 ? (viudo / totalCoincidencias) * 100 : 0;
        const porcentajeUnionLibre = totalCoincidencias > 0 ? (unionLibre / totalCoincidencias) * 100 : 0;

        // Mostrar porcentajes en la interfaz de Wix
        $w('#soltero').text = Math.round(porcentajeSoltero).toString() + '%';
        $w('#casado').text = Math.round(porcentajeCasado).toString() + '%';
        $w('#divorciado').text = Math.round(porcentajeDivorciado).toString() + '%';
        $w('#viudo').text = Math.round(porcentajeViudo).toString() + '%';
        $w('#unionLibre').text = Math.round(porcentajeUnionLibre).toString() + '%';

        return {
            totalCoincidencias,
            soltero,
            casado,
            divorciado,
            viudo,
            unionLibre,
            porcentajeSoltero,
            porcentajeCasado,
            porcentajeDivorciado,
            porcentajeViudo,
            porcentajeUnionLibre
        };

    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return {
            totalCoincidencias: 0,
            soltero: 0,
            casado: 0,
            divorciado: 0,
            viudo: 0,
            unionLibre: 0,
            porcentajeSoltero: 0,
            porcentajeCasado: 0,
            porcentajeDivorciado: 0,
            porcentajeViudo: 0,
            porcentajeUnionLibre: 0
        };
    }
}

$w('#nivelEducativo').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar nivel educativo en FORMULARIO
        const {
            totalCoincidencias,
            primaria,
            secundaria,
            universitario,
            postgrado,
            porcentajePrimaria,
            porcentajeSecundaria,
            porcentajeUniversitario,
            porcentajePostgrado
        } = await contarNivelEducativoEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log(`Primaria: ${primaria} (${porcentajePrimaria.toFixed(2)}%)`);
        console.log(`Secundaria: ${secundaria} (${porcentajeSecundaria.toFixed(2)}%)`);
        console.log(`Universitario: ${universitario} (${porcentajeUniversitario.toFixed(2)}%)`);
        console.log(`Postgrado: ${postgrado} (${porcentajePostgrado.toFixed(2)}%)`);

        // Crear el prompt para OpenAI
        const prompt = `Según los porcentajes de población de la empresa ${codEmpresa}, 
        hay un ${porcentajePrimaria.toFixed(2)}% de personas con nivel educativo de Primaria, 
        un ${porcentajeSecundaria.toFixed(2)}% con nivel de Secundaria, 
        un ${porcentajeUniversitario.toFixed(2)}% con nivel Universitario, 
        y un ${porcentajePostgrado.toFixed(2)}% con nivel de Postgrado. 
        Eres médico laboral y estás elaborando el informe de condiciones de salud. 
        Sugiere exactamente dos recomendaciones breves (una frase cada una) para cada grupo. 
        No incluyas introducciones. No uses markdown.;`;

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#recomendacionesNivelEducativo').value = response.choices[0].message.content;
        } else {
            $w('#recomendacionesNivelEducativo').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar nivel educativo en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
});

// Función para contar coincidencias en FORMULARIO y agrupar por nivel educativo
async function contarNivelEducativoEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)            
            .find();

        const totalCoincidencias = formularioResults.items.length;

        // Contadores para cada nivel educativo
        let primaria = 0;
        let secundaria = 0;
        let universitario = 0;
        let postgrado = 0;

        formularioResults.items.forEach(item => {
            if (item.nivelEducativo) {
                const nivel = item.nivelEducativo.toUpperCase().trim();
                if (nivel === "PRIMARIA") {
                    primaria++;
                } else if (nivel === "SECUNDARIA") {
                    secundaria++;
                } else if (nivel === "UNIVERSITARIO") {
                    universitario++;
                } else if (nivel === "POSTGRADO") {
                    postgrado++;
                }
            }
        });

        // Calcular porcentajes
        const porcentajePrimaria = totalCoincidencias > 0 ? (primaria / totalCoincidencias) * 100 : 0;
        const porcentajeSecundaria = totalCoincidencias > 0 ? (secundaria / totalCoincidencias) * 100 : 0;
        const porcentajeUniversitario = totalCoincidencias > 0 ? (universitario / totalCoincidencias) * 100 : 0;
        const porcentajePostgrado = totalCoincidencias > 0 ? (postgrado / totalCoincidencias) * 100 : 0;

        // Mostrar porcentajes en la interfaz de Wix
        $w('#porcentajePrimaria').text = Math.round(porcentajePrimaria).toString() + '%';
        $w('#porcentajeSecundaria').text = Math.round(porcentajeSecundaria).toString() + '%';
        $w('#porcentajeUniversitario').text = Math.round(porcentajeUniversitario).toString() + '%';
        $w('#porcentajePostgrado').text = Math.round(porcentajePostgrado).toString() + '%';

        return {
            totalCoincidencias,
            primaria,
            secundaria,
            universitario,
            postgrado,
            porcentajePrimaria,
            porcentajeSecundaria,
            porcentajeUniversitario,
            porcentajePostgrado
        };

    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return {
            totalCoincidencias: 0,
            primaria: 0,
            secundaria: 0,
            universitario: 0,
            postgrado: 0,
            porcentajePrimaria: 0,
            porcentajeSecundaria: 0,
            porcentajeUniversitario: 0,
            porcentajePostgrado: 0
        };
    }
}

// Botón para contar cantidad de hijos en FORMULARIO y generar recomendaciones de OpenAI
$w('#hijos').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar cantidad de hijos en FORMULARIO
        const {
            totalCoincidencias,
            sinHijos,
            unHijo,
            dosHijos,
            tresOMasHijos,
            porcentajeSinHijos,
            porcentajeUnHijo,
            porcentajeDosHijos,
            porcentajeTresOMasHijos
        } = await contarHijosEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log(`0 Hijos: ${sinHijos} (${porcentajeSinHijos.toFixed(2)}%)`);
        console.log(`1 Hijo: ${unHijo} (${porcentajeUnHijo.toFixed(2)}%)`);
        console.log(`2 Hijos: ${dosHijos} (${porcentajeDosHijos.toFixed(2)}%)`);
        console.log(`Más de 3 Hijos: ${tresOMasHijos} (${porcentajeTresOMasHijos.toFixed(2)}%)`);

        // Crear el prompt para OpenAI
        const prompt = `Según los porcentajes de población de la empresa ${codEmpresa}, 
        hay un ${porcentajeSinHijos.toFixed(2)}% de personas sin hijos, 
        un ${porcentajeUnHijo.toFixed(2)}% con 1 hijo, 
        un ${porcentajeDosHijos.toFixed(2)}% con 2 hijos, 
        y un ${porcentajeTresOMasHijos.toFixed(2)}% con 3 o más hijos. 
        Eres médico laboral y estás elaborando el informe de condiciones de salud. 
        Sugiere exactamente dos recomendaciones breves (una frase cada una) para cada grupo. 
        No incluyas introducciones. No uses markdown.;`;

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#recomendacionesHijos').value = response.choices[0].message.content;
        } else {
            $w('#recomendacionesHijos').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar cantidad de hijos en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
})

async function contarHijosEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)
            .find();

        const totalCoincidencias = formularioResults.items.length;

        // Contadores para cada grupo de cantidad de hijos
        let sinHijos = 0;
        let unHijo = 0;
        let dosHijos = 0;
        let tresOMasHijos = 0;

        formularioResults.items.forEach(item => {
            if (item.hijos !== undefined && item.hijos !== null) {
                const cantidadHijos = parseInt(item.hijos, 10);
                if (cantidadHijos === 0) {
                    sinHijos++;
                } else if (cantidadHijos === 1) {
                    unHijo++;
                } else if (cantidadHijos === 2) {
                    dosHijos++;
                } else if (cantidadHijos >= 3) {
                    tresOMasHijos++;
                }
            }
        });

        // Calcular porcentajes
        const porcentajeSinHijos = totalCoincidencias > 0 ? (sinHijos / totalCoincidencias) * 100 : 0;
        const porcentajeUnHijo = totalCoincidencias > 0 ? (unHijo / totalCoincidencias) * 100 : 0;
        const porcentajeDosHijos = totalCoincidencias > 0 ? (dosHijos / totalCoincidencias) * 100 : 0;
        const porcentajeTresOMasHijos = totalCoincidencias > 0 ? (tresOMasHijos / totalCoincidencias) * 100 : 0;

        // Mostrar porcentajes en la interfaz de Wix
        $w('#porcentajeSinHijos').text = Math.round(porcentajeSinHijos).toString() + '%';
        $w('#porcentajeUnHijo').text = Math.round(porcentajeUnHijo).toString() + '%';
        $w('#porcentajeDosHijos').text = Math.round(porcentajeDosHijos).toString() + '%';
        $w('#porcentajeTresOMasHijos').text = Math.round(porcentajeTresOMasHijos).toString() + '%';

        return {
            totalCoincidencias,
            sinHijos,
            unHijo,
            dosHijos,
            tresOMasHijos,
            porcentajeSinHijos,
            porcentajeUnHijo,
            porcentajeDosHijos,
            porcentajeTresOMasHijos
        };

    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return {
            totalCoincidencias: 0,
            sinHijos: 0,
            unHijo: 0,
            dosHijos: 0,
            tresOMasHijos: 0,
            porcentajeSinHijos: 0,
            porcentajeUnHijo: 0,
            porcentajeDosHijos: 0,
            porcentajeTresOMasHijos: 0
        };
    }
}

// Botón para contar ciudad de residencia en FORMULARIO y generar recomendaciones de OpenAI
$w('#ciudadResidencia').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar ciudad de residencia en FORMULARIO
        const { totalCoincidencias, ciudades } = await contarCiudadDeResidenciaEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log("Ciudades encontradas:", ciudades);

        // Formatear los datos para la tabla
        const tablaData = ciudades.map(ciudad => ({
            ciudad: ciudad.nombre,
            cantidad: ciudad.cantidad,
            porcentaje: `${ciudad.porcentaje.toFixed(2)}%`
        }));

        // Configurar las columnas de la tabla
        $w("#tablaCiudad").columns = [
            { id: "ciudad", label: "Ciudad", dataPath: "ciudad", type: "string" },
            { id: "porcentaje", label: "Porcentaje", dataPath: "porcentaje", type: "string" }
        ];

        // Asignar los datos a la tabla
        $w("#tablaCiudad").rows = tablaData;

        // Crear el prompt para OpenAI
        let prompt = `Según los porcentajes de población de la empresa ${codEmpresa}, la distribución por ciudad de residencia es:\n`;
        ciudades.forEach(ciudad => {
            prompt += `- ${ciudad.nombre}: ${ciudad.porcentaje.toFixed(2)}%\n`;
        });
        prompt += "Sugiere una recomendación médico-laboral para cada grupo dirigidas a LA EMPRESA. No hagas introducciones. No uses markdowns";

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#recomendacionesCiudad').value = response.choices[0].message.content;
        } else {
            $w('#recomendacionesCiudad').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar ciudad de residencia en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
});

async function contarCiudadDeResidenciaEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)
            .find();

        const totalCoincidencias = formularioResults.items.length;
        const ciudadesMap = {};

        // Agrupar las ciudades y contar su frecuencia
        formularioResults.items.forEach(item => {
            if (item.ciudadDeResidencia) {
                const ciudad = item.ciudadDeResidencia.trim().toUpperCase();
                if (!ciudadesMap[ciudad]) {
                    ciudadesMap[ciudad] = 1;
                } else {
                    ciudadesMap[ciudad]++;
                }
            }
        });

        // Convertir el mapa en un array ordenado por cantidad
        const ciudades = Object.keys(ciudadesMap).map(ciudad => ({
            nombre: ciudad,
            cantidad: ciudadesMap[ciudad],
            porcentaje: (ciudadesMap[ciudad] / totalCoincidencias) * 100
        })).sort((a, b) => b.cantidad - a.cantidad); // Ordenar de mayor a menor

        return { totalCoincidencias, ciudades };

    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return { totalCoincidencias: 0, ciudades: [] };
    }
}

// Botón para contar profesión u oficio en FORMULARIO y generar recomendaciones de OpenAI
$w('#profesionUOficio').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar profesión u oficio en FORMULARIO
        const { totalCoincidencias, profesiones } = await contarProfesionUOficioEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log("Profesiones encontradas:", profesiones);

        // Formatear los datos para la tabla
        const tablaData = profesiones.map(profesion => ({
            profesion: profesion.nombre,
            cantidad: profesion.cantidad,
            porcentaje: `${profesion.porcentaje.toFixed(2)}%`
        }));

        // Configurar las columnas de la tabla
        $w("#tablaProfesionUOficio").columns = [
            { id: "profesion", label: "Profesión u Oficio", dataPath: "profesion", type: "string" },
            { id: "porcentaje", label: "Porcentaje", dataPath: "porcentaje", type: "string" }
        ];

        // Asignar los datos a la tabla
        $w("#tablaProfesionUOficio").rows = tablaData;

        // Crear el prompt para OpenAI
        let prompt = `Según los porcentajes de población de la empresa ${codEmpresa}, la distribución por profesión u oficio es:\n`;
        profesiones.forEach(profesion => {
            prompt += `- ${profesion.nombre}: ${profesion.porcentaje.toFixed(2)}%\n`;
        });
        prompt += "Sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones ni uses markdown";

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#recomendacionesProfesionUOficio').value = response.choices[0].message.content;
        } else {
            $w('#recomendacionesProfesionUOficio').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar profesión u oficio en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
});

// Función para contar coincidencias en FORMULARIO y agrupar por profesión u oficio
async function contarProfesionUOficioEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)
            .find();

        const totalCoincidencias = formularioResults.items.length;
        const profesionesMap = {};

        // Agrupar las profesiones y contar su frecuencia
        formularioResults.items.forEach(item => {
            if (item.profesionUOficio) {
                const profesion = item.profesionUOficio.trim().toUpperCase();
                if (!profesionesMap[profesion]) {
                    profesionesMap[profesion] = 1;
                } else {
                    profesionesMap[profesion]++;
                }
            }
        });

        // Convertir el mapa en un array ordenado por cantidad
        const profesiones = Object.keys(profesionesMap).map(profesion => ({
            nombre: profesion,
            cantidad: profesionesMap[profesion],
            porcentaje: (profesionesMap[profesion] / totalCoincidencias) * 100
        })).sort((a, b) => b.cantidad - a.cantidad); // Ordenar de mayor a menor

        return { totalCoincidencias, profesiones };

    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return { totalCoincidencias: 0, profesiones: [] };
    }
}

// Botón para contar respuestas de encuesta de salud en FORMULARIO y generar recomendaciones de OpenAI
$w('#encuestaSaludBtn').onClick(async () => {
    if (historiaIds.length === 0) {
        console.warn("No hay IDs de HistoriaClinica almacenados. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar respuestas de encuesta de salud en FORMULARIO
        const { totalCoincidencias, respuestas } = await contarEncuestaSaludEnFormulario(historiaIds);

        console.log("Total de coincidencias en FORMULARIO:", totalCoincidencias);
        console.log("Respuestas encontradas en la encuesta de salud:", respuestas);

        // Formatear los datos para la tabla
        const tablaData = respuestas.map(respuesta => ({
            respuesta: respuesta.nombre,
            cantidad: respuesta.cantidad,
            porcentaje: `${respuesta.porcentaje.toFixed(2)}%`
        }));

        // Configurar las columnas de la tabla
        $w("#encuestaTable").columns = [
            { id: "respuesta", label: "Respuesta", dataPath: "respuesta", type: "string" },
            { id: "porcentaje", label: "Porcentaje", dataPath: "porcentaje", type: "string" }
        ];

        // Asignar los datos a la tabla
        $w("#encuestaTable").rows = tablaData;

        // Crear el prompt para OpenAI
        let prompt = `Según los resultados de la encuesta de salud en la empresa ${codEmpresa}, las respuestas más frecuentes fueron:\n`;
        respuestas.forEach(respuesta => {
            prompt += `- ${respuesta.nombre}: ${respuesta.porcentaje.toFixed(2)}%\n`;
        });
        prompt += "Sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones ni uses markdown. Al finalizar las recomendaciones provee un análisis de salud de la población basado en la información de la encuesta teniendo en cuenta que es una empresa con cargos administrativos";

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#recomendacionesEncuestaSalud').value = response.choices[0].message.content;
        } else {
            $w('#recomendacionesEncuestaSalud').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar respuestas de encuesta de salud en FORMULARIO o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
});

// Función para contar respuestas de encuesta de salud en FORMULARIO
async function contarEncuestaSaludEnFormulario(historiaIds) {
    try {
        const formularioResults = await wixData.query("FORMULARIO")
            .hasSome("idGeneral", historiaIds)
            .limit(1000)
            .find();

        const totalCoincidencias = formularioResults.items.length;
        const respuestasMap = {};

        // Iterar sobre cada registro y extraer los valores del array "encuestaSalud"
        formularioResults.items.forEach(item => {
            if (Array.isArray(item.encuestaSalud)) {
                item.encuestaSalud.forEach(respuesta => {
                    const respuestaLimpia = respuesta.trim().toUpperCase();
                    if (!respuestasMap[respuestaLimpia]) {
                        respuestasMap[respuestaLimpia] = 1;
                    } else {
                        respuestasMap[respuestaLimpia]++;
                    }
                });
            }
        });

        // Convertir el mapa en un array ordenado por cantidad
        const respuestas = Object.keys(respuestasMap).map(respuesta => ({
            nombre: respuesta,
            cantidad: respuestasMap[respuesta],
            porcentaje: (respuestasMap[respuesta] / totalCoincidencias) * 100
        })).sort((a, b) => b.cantidad - a.cantidad); // Ordenar de mayor a menor
        console.log(totalCoincidencias, respuestas)

        return { totalCoincidencias, respuestas };
    } catch (error) {
        console.error("Error en la consulta de FORMULARIO:", error);
        return { totalCoincidencias: 0, respuestas: [] };
    }
}

$w.onReady(function () {});

// Botón para contar diagnósticos en HistoriaClinica y generar recomendaciones de OpenAI
$w('#dxButton').onClick(async () => {
    if (!codEmpresa) {
        console.warn("No se ha seleccionado una empresa. Primero realiza una búsqueda.");
        return;
    }

    try {
        $w('#loading').show();

        // Contar diagnósticos en HistoriaClinica
        const { totalCoincidencias, diagnosticos } = await contarMdDx1EnHistoriaClinica(codEmpresa);

        console.log("Total de diagnósticos en HistoriaClinica:", totalCoincidencias);
        console.log("Diagnósticos encontrados:", diagnosticos);

        // Formatear los datos para la tabla
        const tablaData = diagnosticos.map(dx => ({
            diagnostico: dx.nombre,
            cantidad: dx.cantidad,
            porcentaje: `${dx.porcentaje.toFixed(2)}%`
        }));

        // Configurar las columnas de la tabla
        $w("#dxTabla").columns = [
            { id: "diagnostico", label: "Diagnóstico", dataPath: "diagnostico", type: "string" },
            { id: "porcentaje", label: "Porcentaje", dataPath: "porcentaje", type: "string" }
        ];

        // Asignar los datos a la tabla
        $w("#dxTabla").rows = tablaData;

        // Crear el prompt para OpenAI
        let prompt = `Según los diagnósticos más comunes en la empresa ${codEmpresa}, la distribución es:\n`;
        diagnosticos.forEach(dx => {
            prompt += `- ${dx.nombre}: ${dx.porcentaje.toFixed(2)}%\n`;
        });
        prompt += "Explica y sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones ni uses markdown. No hagas introducciones ni uses markdown. Al finalizar las recomendaciones provee un análisis detallado de salud de la población basado en la información de la encuesta teniendo en cuenta que es una empresa con cargos administrativos";

        // Llamar a OpenAI con el prompt generado
        const response = await callOpenAI(prompt);
        console.log("Respuesta de OpenAI:", response);

        // Mostrar la respuesta en un campo de texto en Wix (ajusta el ID según sea necesario)
        if (response && response.choices && response.choices.length > 0) {
            $w('#recomendacionesDx').value = response.choices[0].message.content;
        } else {
            $w('#recomendacionesDx').value = "No se recibieron recomendaciones.";
        }

    } catch (error) {
        console.error("Error al contar diagnósticos en HistoriaClinica o llamar a OpenAI:", error);
    } finally {
        $w('#loading').hide();
        console.log("Proceso finalizado.");
    }
});

// Función para contar diagnósticos en HistoriaClinica
async function contarMdDx1EnHistoriaClinica(codEmpresa) {
    try {
        const historiaResults = await wixData.query("HistoriaClinica")
            .eq("codEmpresa", codEmpresa)
            .limit(1000)
            .find();

        const totalCoincidencias = historiaResults.items.length;
        const diagnosticosMap = {};

        console.log("Total registros en HistoriaClinica:", totalCoincidencias);

        historiaResults.items.forEach((item, index) => {
            console.log(`Registro ${index + 1}:`, item.mdDx1); // Ver qué datos trae mdDx1

            if (typeof item.mdDx1 === "string" && item.mdDx1.trim() !== "") {
                // Separar diagnósticos por coma o punto y coma (ajustar si es necesario)
                const diagnosticos = item.mdDx1.split(/[,;]/).map(dx => dx.trim().toUpperCase());

                diagnosticos.forEach(diagnostico => {
                    if (diagnostico) {
                        if (!diagnosticosMap[diagnostico]) {
                            diagnosticosMap[diagnostico] = 1;
                        } else {
                            diagnosticosMap[diagnostico]++;
                        }
                    }
                });
            }
        });

        console.log("Diagnósticos agrupados:", diagnosticosMap);

        // Convertir el mapa en un array ordenado por cantidad
        const diagnosticos = Object.keys(diagnosticosMap).map(dx => ({
            nombre: dx,
            cantidad: diagnosticosMap[dx],
            porcentaje: (diagnosticosMap[dx] / totalCoincidencias) * 100
        })).sort((a, b) => b.cantidad - a.cantidad); // Ordenar de mayor a menor

        return { totalCoincidencias, diagnosticos };

    } catch (error) {
        console.error("Error en la consulta de HistoriaClinica:", error);
        return { totalCoincidencias: 0, diagnosticos: [] };
    }
}

$w("#sveButton").onClick(async () => {
    console.log("Botón #sveButton2 presionado, ejecutando sve()...");
    await sve();
});
async function sve() {
    try {
        console.log("Consultando datos en HistoriaClinica para SVE...");

        // Consultar datos en HistoriaClinica
        const historiaResults = await wixData.query("HistoriaClinica")
            .eq("codEmpresa", codEmpresa)
            .limit(1000)
            .find();

        console.log("Registros obtenidos en HistoriaClinica:", historiaResults.items.length);

        if (historiaResults.items.length === 0) {
            console.warn("No se encontraron registros en HistoriaClinica.");
            return;
        }

        // Definir categorías de condiciones médicas
        const visualConditions = [
            'ASTIGMATISMO H522',
            "ALTERACION VISUAL  NO ESPECIFICADA H539",
            'ALTERACIONES VISUALES SUBJETIVAS H531',
            'CONJUNTIVITIS  NO ESPECIFICADA H109',
            'DISMINUCION DE LA AGUDEZA VISUAL SIN ESPECIFICACION H547',
            'DISMINUCION INDETERMINADA DE LA AGUDEZA VISUAL EN AMBOS OJOS (AMETROPÍA) H543',
            'MIOPIA H521',
            'PRESBICIA H524',
            'VISION SUBNORMAL DE AMBOS OJOS H542',
            'DEFECTOS DEL CAMPO VISUAL H534'
        ];

        const auditoryConditions = [
            'EFECTOS DEL RUIDO SOBRE EL OIDO INTERNO H833',
            'PRESBIACUSIA H911',
            'HIPOACUSIA  NO ESPECIFICADA H919',
            'OTITIS MEDIA  NO ESPECIFICADA H669',
            'OTRAS ENFERMEDADES DE LAS CUERDAS VOCALES J383',
            'OTROS TRASTORNOS DE LA VISION BINOCULAR H533'
        ];

        const weightControlConditions = [
            'AUMENTO ANORMAL DE PESO',
            'OBESIDAD ALIMENTARIA, E66.0',
            'OBESIDAD CONSTITUCIONAL, E66.8',
            'HIPOTIROIDISMO  NO ESPECIFICADO E039'
        ];

        // Extraer y normalizar los valores de mdDx1 y mdDx2
        const diagnosesMap = {};
        const sveTableData = [];

        historiaResults.items.forEach((item, index) => {
            console.log(`Registro ${index + 1}: mdDx1 = ${item.mdDx1}, mdDx2 = ${item.mdDx2}`);

            const nombres = `${item.primerNombre} ${item.primerApellido}`;
            const documento = item.numeroId;

            let allDiagnoses = [];

            if (typeof item.mdDx1 === "string" && item.mdDx1.trim() !== "") {
                allDiagnoses.push(...item.mdDx1.split(/[,;]/).map(dx => dx.trim().toUpperCase()));
            }
            if (typeof item.mdDx2 === "string" && item.mdDx2.trim() !== "") {
                allDiagnoses.push(...item.mdDx2.split(/[,;]/).map(dx => dx.trim().toUpperCase()));
            }

            allDiagnoses.forEach(diagnosis => {
                if (!diagnosesMap[diagnosis]) {
                    diagnosesMap[diagnosis] = 1;
                } else {
                    diagnosesMap[diagnosis]++;
                }

                let sistema = "";
                if (visualConditions.includes(diagnosis)) {
                    sistema = 'Visual';
                } else if (auditoryConditions.includes(diagnosis)) {
                    sistema = 'Auditivo';
                } else if (weightControlConditions.includes(diagnosis)) {
                    sistema = 'Control de Peso';
                }

                if (sistema) {
                    sveTableData.push({ nombres, documento, sistema });
                }
            });
        });

        console.log("Diagnósticos agrupados:", JSON.stringify(diagnosesMap, null, 2));
        console.log("Datos formateados para la tabla:", sveTableData);

        // Configurar las columnas y filas para la tabla en Wix
        $w("#sveTable").columns = [
            { id: "nombres", label: "Nombres", dataPath: "nombres", type: "string" },
            { id: "documento", label: "Documento", dataPath: "documento", type: "string" },
            { id: "sistema", label: "Sistema", dataPath: "sistema", type: "string" }
        ];

        $w("#sveTable").rows = sveTableData;

    } catch (error) {
        console.error("Error al procesar los diagnósticos en HistoriaClinica:", error);
    }

    console.log("SVE DONE!");
}