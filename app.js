import React, { useEffect, useState } from "react";

function App() {
  const [msg, setMsg] = useState("Por favor, espera unos segundos...");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const documento = params.get("documento");
    if (!documento) {
      setMsg("❌ No se recibió el identificador del documento.");
      return;
    }

    fetch("https://bsl-utilidades-yp78a.ondigitalocean.app/descargar-pdf-empresas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ documento })
    })
    .then(res => {
      if (!res.ok) throw new Error("No se pudo generar el certificado.");
      return res.blob();
    })
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${documento}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setMsg("✅ Descarga completada. Puedes cerrar esta ventana.");
      setTimeout(() => window.close(), 3000);
    })
    .catch(err => {
      setMsg("❌ Error: No se pudo descargar el certificado. Intenta nuevamente.");
      setTimeout(() => window.close(), 4000);
    });
  }, []);

  return (
    <div style={{textAlign: "center", padding: "40px"}}>
      <h2>Generando y descargando tu certificado...</h2>
      <div style={{fontSize: "1.2em", marginTop: "30px"}}>{msg}</div>
    </div>
  );
}

export default App;
