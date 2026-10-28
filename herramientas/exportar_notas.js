// Exporta las notas de una carpeta de Apple Notas como JSON (para importar_notas.py).
// Uso (en Terminal, en la Mac):
//   osascript -l JavaScript herramientas/exportar_notas.js "Ágape" | python3 herramientas/importar_notas.py --autor Greg
function pad(n){ return (n < 10 ? '0' : '') + n; }
function local(d){ return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '+pad(d.getHours())+':'+pad(d.getMinutes()); }
function run(argv){
  var carpeta = (argv.length ? argv[0] : 'Ágape').normalize('NFC');
  var Notes = Application('Notes');
  var out = [], encontrada = false, bloqueadas = 0;
  Notes.accounts().forEach(function(acc){
    acc.folders().forEach(function(f){
      if (f.name().normalize('NFC') !== carpeta) return;
      encontrada = true;
      f.notes().forEach(function(n){
        try {
          out.push({ id: n.id(), titulo: n.name(), html: n.body(),
                     creada: local(n.creationDate()), modificada: local(n.modificationDate()),
                     cuenta: acc.name() });
        } catch (e) { bloqueadas++; }
      });
    });
  });
  if (!encontrada) throw new Error('No encontré la carpeta "' + carpeta + '" en Notas.');
  return JSON.stringify({ carpeta: carpeta, bloqueadas: bloqueadas, notas: out });
}
