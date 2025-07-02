// App.js (React)
import { useEffect } from "react";

function App() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const documento = params.get("documento");
    if (!documento) return;

    fetch("https://bsl-utilidades-yp78a.ondigitalocean.app/descargar-pdf-empresas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ documento })
    })
      .then(res => res.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${documento}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        window.close(); // Cierra la ventana/pestaña si quieres, tras descargar.
      })
      .catch(err => {
        alert("Error descargando el certificado");
        window.close();
      });
  }, []);

  return (
    <div>
      <p>Generando y descargando tu certificado...</p>
    </div>
  );
}

export default App;
