"""AGRO routers (CONSOL-3 fase A, regla 77)
- metodos extraidos de server.py
- cada funcion recibe handler_self como primer parametro
- comportamiento identico, codigo reubicado"""
from __future__ import annotations


def _screen_producer(
    self, s: list[str]
) -> None:
    store = type(self).store
    producer_id = (
        s[1] if len(s) > 1 else ""
    )
    row = store.get_producer(
        producer_id
    )
    if not row or not row.get("name"):
        self._html(
            404,
            _page(
                "AGRO - Productor",
                "<h1>Productor no encontrado</h1>"
                "<a href='/agro'><button>Volver</button></a>",
            ),
        )
        return
    if row.get("verified"):
        badge = "✅ VERIFICADO"
    else:
        badge = "⚠️ Sin verificar (sin bonos)"
    body = (
        "<h1>Mi Panel — " + str(row.get("name")) + "</h1>"
        "<p>" + badge + " · Rol: " + str(row.get("role")) + "</p>"
        "<div class='card'><h2>1) Registrar mi cosecha</h2>"
        "<form method='POST' action='/agro/production'>"
        "<input type='hidden' name='producer_id' value='" + producer_id + "'>"
        "<input name='product' placeholder='Producto (maiz, frijol...)'>"
        "<input name='quantity' placeholder='Cantidad'>"
        "<select name='unit'><option value='quintal'>quintal</option>"
        "<option value='libra'>libra</option></select>"
        "<button>Guardar</button>"
        "</form></div>"
        "<div class='card'><h2>2) Vender mi producto</h2>"
        "<form method='POST' action='/agro/sale'>"
        "<input type='hidden' name='producer_id' value='" + producer_id + "'>"
        "<input name='buyer' placeholder='Comprador'>"
        "<input name='product' placeholder='Producto'>"
        "<input name='quantity' placeholder='Cantidad'>"
        "<select name='unit'><option value='quintal'>quintal</option>"
        "<option value='libra'>libra</option></select>"
        "<input name='price' placeholder='Precio total'>"
        "<button>Vender</button>"
        "</form></div>"
        "<div class='card'><h2>3) Ayuda del Gobierno</h2>"
        "<a href='/agro/ayudas/" + producer_id + "'><button>Ver mis ayudas</button></a>"
        "</div>"
        "<a href='/agro'><button class='gray'>Inicio</button></a>"
    )
    self._html(
        200,
        _page("AGRO - Mi panel", body),
    )

def _screen_government(self) -> None:
    store = type(self).store
    summary = store.summary()
    from apps.agro.modules.gobierno.seguridad_alimentaria.food_security_service import (
        FoodSecurityService,
    )
    from apps.agro.modules.gobierno.apoyos.government_aid_service import (
        GovernmentAidService,
    )
    fs = FoodSecurityService(store).national_status()
    ay = GovernmentAidService(store).beneficiaries_report()
    areas = self._ZYRA_AREAS_V2()
    riesgos = ""
    for p in store.list_producers():
        for r in areas.open_risks(
            producer_id=str(p.get("producer_id"))
        ):
            riesgos = riesgos + "<li>" + str(p.get("name")) + ": " + str(r.get("risk_type")) + " (" + str(r.get("severity")) + ")</li>"
    if not riesgos:
        riesgos = "<li>Sin riesgos abiertos</li>"
    prod_rows = ""
    for x in fs["products"]:
        prod_rows = prod_rows + "<li>" + x["product"] + ": " + str(x["quantity"]) + "</li>"
    if not prod_rows:
        prod_rows = "<li>Sin cosechas registradas</li>"
    roles_html = ""
    for k, v in (summary.get("producers_by_role") or {}).items():
        roles_html = roles_html + "<li>" + str(k) + ": " + str(v) + "</li>"
    ben = ""
    for r in ay["beneficiados"]:
        ben = ben + "<li>" + r["name"] + " (" + str(r["aid_count"]) + ")</li>"
    if not ben:
        ben = "<li>Ninguno aun</li>"
    noben = ""
    for r in ay["no_beneficiados"]:
        noben = noben + "<li>" + r["name"] + "</li>"
    if not noben:
        noben = "<li>Todos beneficiados</li>"
    modulos = ""
    for m in self._ZYRA_MENUS_V2():
        modulos = modulos + "<li><b>" + str(m.get("title")) + "</b>:"
        for it in m.get("items", []):
            modulos = modulos + " <a href='" + str(it.get("path")) + "'>" + str(it.get("label")) + "</a>"
        modulos = modulos + "</li>"
    body = (
        "<h1>🏛️ AGRO — Vista Gobierno</h1>"
        "<h2>Soberania alimentaria nacional</h2>"
        "<div class='card'>"
        "<span class='big'>" + str(summary.get("producers_total")) + "</span> productores<br>"
        "<span class='big'>" + str(summary.get("producers_verified")) + "</span> verificados"
        "</div>"
        "<div class='card'><h2>Seguridad alimentaria</h2><ul>" + prod_rows + "</ul>"
        "<a href='/agro/gobierno/seguridad'><button>Ver detalle</button></a></div>"
        "<div class='card'><h2>Ayudas (" + str(ay["aid_total"]) + " total)</h2>"
        "<h3>Beneficiados</h3><ul>" + ben + "</ul>"
        "<h3>No beneficiados (a quienes ayudar)</h3><ul>" + noben + "</ul>"
        "<a href='/agro/gobierno/beneficiados'><button>Ver detalle</button></a></div>"
        "<div class='card'><h2>Riesgos abiertos</h2><ul>" + riesgos + "</ul>"
        "<a href='/agro/gobierno/riesgos'><button>Ver detalle</button></a></div>"
        "<div class='card'><h2>Por rol</h2><ul>" + roles_html + "</ul></div>"
        "<div class='card'><h2>Modulos de la Red AGRO</h2><ul>" + modulos + "</ul></div>"
        "<a href='/agro'><button class='gray'>Inicio</button></a>"
    )
    self._html(
        200,
        _page("AGRO - Gobierno", body),
    )

def _screen_bank(self) -> None:
    store = type(self).store
    producers = store.list_producers()
    total = len(producers)
    verified = 0
    for p in producers:
        if p.get("verified"):
            verified = verified + 1
    prods = store.list_productions()
    rows = ""
    for p in prods:
        rows = rows + "<li>" + str(p.get("product")) + " - " + str(p.get("quantity")) + " " + str(p.get("unit")) + "</li>"
    if not rows:
        rows = "<li>Sin produccion disponible</li>"
    body = (
        "<h1>Banco AGRO</h1>"
        "<p>Productores: " + str(total) + " - verificados: " + str(verified) + "</p>"
        "<div class='card'><h2>Credito agricola</h2>"
        "<p>credito para productores verificados con ZID en la Red.</p>"
        "<a href='/agro/gobierno/beneficiados'><button>Beneficiarios de apoyo</button></a>"
        "</div>"
        "<div class='card'><h2>Produccion para compra / exportacion</h2>"
        "<ul>" + rows + "</ul>"
        "<a href='/agro/mercado'><button>Ir al mercado</button></a>"
        "</div>"
        "<a href='/agro'><button class='gray'>Inicio</button></a>"
    )
    self._html(
        200,
        _page("AGRO - Banco", body),
    )

def _home(self) -> None:
    body = (
        "<h1>🛡️ AGRO</h1>"
        "<p>La Red de confianza"
        " para agricultores y"
        " ganaderos.</p>"
        "<h2>Soy productor</h2>"
        "<div class='card'>"
        "<form method='POST'"
        " action='/agro/register'>"
        "<input name='name'"
        " placeholder='Mi nombre'>"
        "<select name='role'>"
        "<option value='agricultor'>"
        "Agricultor</option>"
        "<option value='ganadero'>"
        "Ganadero</option>"
        "</select>"
        "<input name='producer_type'"
        " placeholder='Que produzco"
        " (maiz, ganado...)'>"
        "<input name='location'"
        " placeholder='Mi zona'>"
        "<fieldset><legend>1) Foto del documento (por ley)</legend><input type='file' id='agroDoc' accept='image/*' capture='environment'></fieldset>"
        "<fieldset><legend>2) Selfie en vivo</legend>"
        "<video id='agroCam' width='240' height='180' autoplay playsinline muted></video><br>"
        "<button type='button' id='agroSnap'>Capturar selfie</button><br>"
        "o desde archivo: <input type='file' id='agroSelfie' accept='image/*' capture='user'>"
        "</fieldset>"
        "<input type='hidden' name='doc_image_b64' id='agroDocB64'>"
        "<input type='hidden' name='selfie_image_b64' id='agroSelfieB64'>"
        "<canvas id='agroCv' style='display:none'></canvas>"
        "<p id='agroSt'>Estado: pendiente</p>"
        "<script>"
        "(function(){"
        "var doc=document.getElementById('agroDoc');"
        "var slf=document.getElementById('agroSelfie');"
        "var vid=document.getElementById('agroCam');"
        "var cvv=document.getElementById('agroCv');"
        "var cx=cvv.getContext('2d');"
        "var st=document.getElementById('agroSt');"
        "function upd(){st.textContent='Estado: doc='+(document.getElementById('agroDocB64').value?'OK':'falta')+' | selfie='+(document.getElementById('agroSelfieB64').value?'OK':'falta');}"
        "function process(file,target){if(!file){return;}var r=new FileReader();r.onload=function(){var im=new Image();im.onload=function(){var max=800;var k=Math.min(1,max/Math.max(im.width,im.height));cvv.width=Math.round(im.width*k);cvv.height=Math.round(im.height*k);cx.drawImage(im,0,0,cvv.width,cvv.height);var d=cvv.toDataURL('image/jpeg',0.72);document.getElementById(target).value=d.split(',')[1];upd();};im.src=r.result;};r.readAsDataURL(file);}"
        "doc.addEventListener('change',function(){process(doc.files[0],'agroDocB64');});"
        "slf.addEventListener('change',function(){process(slf.files[0],'agroSelfieB64');});"
        "if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia){navigator.mediaDevices.getUserMedia({video:{facingMode:'user'}}).then(function(s){vid.srcObject=s;}).catch(function(){st.textContent='Camara no disponible: use el archivo.';});}"
        "document.getElementById('agroSnap').addEventListener('click',function(){if(!vid.videoWidth){st.textContent='Camara aun no lista.';return;}var w=480;var k=w/vid.videoWidth;cvv.width=w;cvv.height=Math.round(vid.videoHeight*k);cx.drawImage(vid,0,0,cvv.width,cvv.height);var d=cvv.toDataURL('image/jpeg',0.72);document.getElementById('agroSelfieB64').value=d.split(',')[1];upd();});"
        "})();"
        "</script>"
        "<button>Registrarme en la"
        " Red</button>"
        "</form></div>"
        "<h2>Soy Gobierno / Banco"
        "</h2>"
        "<div class='card'>"
        "<a href='/agro/gobierno'>"
        "<button>Vista Gobierno"
        "</button></a>"
        "<a href='/agro/banco'>"
        "<button class='gray'>Vista"
        " Banco</button></a>"
        "</div>"
    )
    self._html(200, _page("AGRO", body))