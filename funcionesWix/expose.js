// backend/actualizar-resumen.jsw
import wixData from 'wix-data';

export async function actualizarResumenConversacion(_id, resumen) {
    // Primero obtenemos el ítem actual
    const existingItem = await wixData.get("CHATBOT", _id);

    // Luego solo actualizamos el campo 'resumen'
    existingItem.resumen = resumen;

    // Finalmente hacemos el update
    return wixData.update("CHATBOT", existingItem);
}

export async function obtenerHorasOcupadas(fecha) {
    try {
        const inicioDelDia = new Date(`${fecha}T00:00:00.000Z`);
        const finDelDia = new Date(`${fecha}T23:59:59.999Z`);

        const result = await wixData.query("HistoriaClinica")
            .ge("fechaAtencion", inicioDelDia)
            .le("fechaAtencion", finDelDia)
            .find();

        const horasOcupadas = result.items.map(item => {
            const fecha = new Date(item.fechaAtencion);
            const horaColombia = new Date(fecha.getTime() - (5 * 60 * 60 * 1000));
            const hora = horaColombia.toTimeString().slice(0, 5); // formato "HH:MM"

            return {
                _id: item._id,
                hora
            };
        });

        return horasOcupadas;
    } catch (error) {
        console.error("Error consultando horas ocupadas:", error);
        return [];
    }
}

export async function crearRegistroAgente(fechaTexto) {
    try {
        console.log("🕵️‍♂️ Recibido en el backend:", fechaTexto);

        const fechaUTC = new Date(fechaTexto);

        const nuevaFecha = new Date(fechaUTC.getTime() + (5 * 60 * 60 * 1000));

        const nuevoRegistro = {
            fechaAtencion: nuevaFecha,
            atendido: "PENDIENTE",
            medico: "NUBIA"
        };
        console.log("🧾 Registro a insertar:", nuevoRegistro);

        const result = await wixData.insert("HistoriaClinica", nuevoRegistro);
        return { success: true, item: result };
    } catch (error) {
        console.error("❌ Error al crear registro:", error);
        return { success: false, error: error.message };
    }
}

// PERTENECES AL BOT DE DIGITALOCEAN
export async function consultarPorDocumento(numeroId) {
    try {
        const result = await wixData.query("HistoriaClinica")
            .eq("numeroId", numeroId)
            .find();

        const informacion = result.items.map(item => ({
            _id: item._id,
            primerNombre: item.primerNombre,
            primerApellido: item.primerApellido,
            celular: item.celular,
            fechaConsulta: item.fechaConsulta ? item.fechaConsulta.toISOString() : null,
            fechaAtencion: item.fechaAtencion ? item.fechaAtencion.toISOString() : null,
            pvEstado: item.pvEstado,
            atendido: item.atendido,
            empresa: item.empresa,
            codEmpresa: item.codEmpresa
        }));

        return informacion;
    } catch (error) {
        console.error("Error consultando información por numeroId:", error);
        return [];
    }
}

// FUNCIÓN PARA ACTUALIZAR HISTORIA CLÍNICA
export async function actualizarHistoriaClinica(_id, datos) {
    try {
        const existingItem = await wixData.get("HistoriaClinica", _id);

        // Actualizar solo los campos proporcionados
        Object.keys(datos).forEach(key => {
            if (key !== '_id') {
                existingItem[key] = datos[key];
            }
        });

        const result = await wixData.update("HistoriaClinica", existingItem);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error actualizando historia clínica:", error);
        return { success: false, error: error.message };
    }
}

// FUNCIONES PARA EXPONER BASE DE DATOS FORMULARIO
export async function crearFormulario(datos) {
    try {
        const result = await wixData.insert("FORMULARIO", datos);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error creando formulario:", error);
        return { success: false, error: error.message };
    }
}

export async function obtenerFormularios(filtros = {}) {
    try {
        let query = wixData.query("FORMULARIO");

        // Aplicar filtros si existen
        if (filtros.numeroId) {
            query = query.eq("numeroId", filtros.numeroId);
        }
        if (filtros.fechaInicio && filtros.fechaFin) {
            query = query.ge("createdDate", new Date(filtros.fechaInicio))
                         .le("createdDate", new Date(filtros.fechaFin));
        }

        const result = await query.find();
        return { success: true, items: result.items, total: result.totalCount };
    } catch (error) {
        console.error("Error obteniendo formularios:", error);
        return { success: false, error: error.message };
    }
}

export async function obtenerFormularioPorIdGeneral(idGeneral) {
    try {
        const result = await wixData.query("FORMULARIO")
            .eq("idGeneral", idGeneral)
            .find();

        if (result.items.length > 0) {
            return { success: true, item: result.items[0] };
        } else {
            return { success: false, message: "No se encontró formulario con ese idGeneral" };
        }
    } catch (error) {
        console.error("Error obteniendo formulario por idGeneral:", error);
        return { success: false, error: error.message };
    }
}

export async function actualizarFormulario(_id, datos) {
    try {
        const existingItem = await wixData.get("FORMULARIO", _id);
        
        // Actualizar solo los campos proporcionados
        Object.keys(datos).forEach(key => {
            if (key !== '_id') {
                existingItem[key] = datos[key];
            }
        });
        
        const result = await wixData.update("FORMULARIO", existingItem);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error actualizando formulario:", error);
        return { success: false, error: error.message };
    }
}

// FUNCIONES PARA EXPONER BASE DE DATOS AUDIOMETRIA
export async function obtenerAudiometrias(filtros = {}) {
    try {
        let query = wixData.query("AUDIOMETRIA");
        
        // Aplicar filtros si existen
        if (filtros.numeroId) {
            query = query.eq("numeroId", filtros.numeroId);
        }
        if (filtros.fechaInicio && filtros.fechaFin) {
            query = query.ge("createdDate", new Date(filtros.fechaInicio))
                         .le("createdDate", new Date(filtros.fechaFin));
        }
        
        const result = await query.find();
        return { success: true, items: result.items, total: result.totalCount };
    } catch (error) {
        console.error("Error obteniendo audiometrías:", error);
        return { success: false, error: error.message };
    }
}

export async function crearAudiometria(datos) {
    try {
        const result = await wixData.insert("AUDIOMETRIA", datos);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error creando audiometría:", error);
        return { success: false, error: error.message };
    }
}

export async function actualizarAudiometria(_id, datos) {
    try {
        const existingItem = await wixData.get("AUDIOMETRIA", _id);

        // Actualizar solo los campos proporcionados
        Object.keys(datos).forEach(key => {
            if (key !== '_id') {
                existingItem[key] = datos[key];
            }
        });

        const result = await wixData.update("AUDIOMETRIA", existingItem);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error actualizando audiometría:", error);
        return { success: false, error: error.message };
    }
}

// FUNCIONES PARA EXPONER BASE DE DATOS VISUAL
export async function obtenerVisuales(filtros = {}) {
    try {
        let query = wixData.query("VISUAL");
        
        // Aplicar filtros si existen
        if (filtros.numeroId) {
            query = query.eq("numeroId", filtros.numeroId);
        }
        if (filtros.fechaInicio && filtros.fechaFin) {
            query = query.ge("createdDate", new Date(filtros.fechaInicio))
                         .le("createdDate", new Date(filtros.fechaFin));
        }
        
        const result = await query.find();
        return { success: true, items: result.items, total: result.totalCount };
    } catch (error) {
        console.error("Error obteniendo visuales:", error);
        return { success: false, error: error.message };
    }
}

export async function crearVisual(datos) {
    try {
        const result = await wixData.insert("VISUAL", datos);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error creando visual:", error);
        return { success: false, error: error.message };
    }
}

export async function actualizarVisual(_id, datos) {
    try {
        const existingItem = await wixData.get("VISUAL", _id);

        // Actualizar solo los campos proporcionados
        Object.keys(datos).forEach(key => {
            if (key !== '_id') {
                existingItem[key] = datos[key];
            }
        });

        const result = await wixData.update("VISUAL", existingItem);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error actualizando visual:", error);
        return { success: false, error: error.message };
    }
}

// FUNCIONES PARA EXPONER BASE DE DATOS ADCTEST
export async function obtenerAdcTests(filtros = {}) {
    try {
        let query = wixData.query("ADCTEST");
        
        // Aplicar filtros si existen
        if (filtros.numeroId) {
            query = query.eq("numeroId", filtros.numeroId);
        }
        if (filtros.fechaInicio && filtros.fechaFin) {
            query = query.ge("createdDate", new Date(filtros.fechaInicio))
                         .le("createdDate", new Date(filtros.fechaFin));
        }
        
        const result = await query.find();
        return { success: true, items: result.items, total: result.totalCount };
    } catch (error) {
        console.error("Error obteniendo ADC tests:", error);
        return { success: false, error: error.message };
    }
}

export async function crearAdcTest(datos) {
    try {
        const result = await wixData.insert("ADCTEST", datos);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error creando ADC test:", error);
        return { success: false, error: error.message };
    }
}

export async function actualizarAdcTest(_id, datos) {
    try {
        const existingItem = await wixData.get("ADCTEST", _id);

        // Actualizar solo los campos proporcionados
        Object.keys(datos).forEach(key => {
            if (key !== '_id') {
                existingItem[key] = datos[key];
            }
        });

        const result = await wixData.update("ADCTEST", existingItem);
        return { success: true, item: result };
    } catch (error) {
        console.error("Error actualizando ADC test:", error);
        return { success: false, error: error.message };
    }
}