# Herramientas: traer notas y fotos al archivo

El repositorio es **público**. Todo lo que se importe y se suba con `git push` lo puede leer cualquiera.
Antes de cada `git add`, revisa con `git status` qué entra, y borra o deja fuera lo que no quieran publicar.

## Notas de Apple Notas

1. En Notas, crea una carpeta **Ágape** y mueve ahí solo las notas que quieran en el libro. Nada fuera de esa carpeta se lee.
2. En Terminal:
   ```bash
   cd ~/Documents/mi-destino
   osascript -l JavaScript herramientas/exportar_notas.js "Ágape" | python3 herramientas/importar_notas.py --autor Greg
   python3 build.py
   ```
   La primera vez, la Mac pregunta si Terminal puede usar Notas: **Permitir**.
3. Cada nota queda en `materiales/cuaderno/` tal cual, con su fecha y hora, y aparece en **La línea del tiempo**.
   Se puede correr las veces que haga falta; lo ya importado no se duplica. Las notas con contraseña se saltan.

**Las de Nohemi:** ella crea su carpeta (por ejemplo **Ágape · Nohemi**) y te la comparte desde Notas. Aparece en tu Mac y la importas con:
```bash
osascript -l JavaScript herramientas/exportar_notas.js "Ágape · Nohemi" | python3 herramientas/importar_notas.py --autor Nohemi
```

## Fotos (con fecha y lugar)

1. En Fotos: selecciona → Archivo → Exportar → Exportar fotos → **JPEG**, tamaño **Grande**, con **Información de ubicación**.
2. Guárdalas en `materiales/fotos/greg/`, `materiales/fotos/nohemi/` o `materiales/fotos/juntos/`.
3. Una sola vez: `pip3 install pillow pillow-heif`. Después:
   ```bash
   python3 herramientas/importar_fotos.py
   python3 build.py
   ```
4. En `materiales/fotos/fotos.json` escriban `lugar`, `pie` y `capitulo` para cada foto.

Qué se sube y qué no:
- **No se suben:** las fotos originales y `ubicaciones.json` (coordenadas GPS). Guarden las originales también en Dropbox o Drive.
- **Sí se suben:** copias livianas en `_web/` **sin metadatos**, y `fotos.json` con fecha, hora, lugar escrito por ustedes y pie de foto.
