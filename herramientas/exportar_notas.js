// Exporta notas de Apple Notas como JSON.
// Una carpeta (para importar al libro):
//   osascript -l JavaScript herramientas/exportar_notas.js "Ágape" | python3 herramientas/importar_notas.py --autor Greg
// Todas las carpetas (para el análisis privado; NO va al repositorio):
//   osascript -l JavaScript exportar_notas.js --todas > notas-todas.json
function pad(n){ return (n < 10 ? '0' : '') + n; }
function local(d){ return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '+pad(d.getHours())+':'+pad(d.getMinutes()); }
var BORRADAS = ['Recently Deleted', 'Eliminados recientemente', 'Eliminadas recientemente'];
function run(argv){
  var todas = argv.length && argv[0] === '--todas';
  var carpeta = todas ? null : (argv.length ? argv[0] : 'Ágape').normalize('NFC');
  var Notes = Application('Notes');
  var out = [], encontrada = false, bloqueadas = 0;
  Notes.accounts().forEach(function(acc){
    acc.folders().forEach(function(f){
      var nombre = f.name().normalize('NFC');
      if (todas ? BORRADAS.indexOf(nombre) >= 0 : nombre !== carpeta) return;
      encontrada = true;
      f.notes().forEach(function(n){
        try {
          var html = n.body();
          if (todas) html = html.replace(/<img[^>]*>/gi, '[imagen]');
          out.push({ id: n.id(), titulo: n.name(), html: html, carpeta: nombre,
                     creada: local(n.creationDate()), modificada: local(n.modificationDate()),
                     cuenta: acc.name() });
        } catch (e) { bloqueadas++; }
      });
    });
  });
  if (!encontrada) throw new Error(todas ? 'No encontré carpetas en Notas.' : 'No encontré la carpeta "' + carpeta + '" en Notas.');
  return JSON.stringify({ carpeta: todas ? '(todas)' : carpeta, bloqueadas: bloqueadas, notas: out });
}
