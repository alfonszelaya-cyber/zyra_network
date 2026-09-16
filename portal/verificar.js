async function verify() {
  const blob = document.getElementById("blob").value.trim();
  const box = document.getElementById("result");
  if (!blob) { box.className="bad"; box.style.display="block";
    box.textContent="Pega un certificado primero."; return; }
  box.style.display="block";
  box.textContent="Verificando...";
  try {
    const res = await fetch("/verify", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({attestation: blob})
    });
    const payload = await res.json();
    const d = payload.data || payload.error || {};
    if (payload.ok && d.valid) {
      box.className = "ok";
      box.innerHTML = "<b>✓ AUTÉNTICO</b><br>" +
        "Motivo: " + d.reason + "<br>" +
        "ID: " + (d.attestation_id || "-") + "<br>" +
        "Sujeto: " + (d.subject_zid || "-") + "<br>" +
        "Declaración: " + (d.claim || "-") + "<br>" +
        "Huella de clave: " + (d.key_fingerprint || "-");
    } else {
      box.className = "bad";
      box.innerHTML = "<b>✗ NO VÁLIDO</b><br>" +
        "Motivo: " + (d.reason || d.message || "desconocido");
    }
  } catch (e) {
    box.className = "bad";
    box.textContent = "Error contactando la Red: " + e;
  }
}
