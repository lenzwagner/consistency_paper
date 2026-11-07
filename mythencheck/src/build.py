import sys, re, pathlib
src = pathlib.Path(__file__).parent
shell = (src/'shell.html').read_text(encoding='utf-8')
css = (src/'app.css').read_text(encoding='utf-8')
data = '\n'.join((src/f).read_text(encoding='utf-8') for f in ['data1.js','data2.js','data3.js','deep1.js','deep2.js','deep3.js'])
app = (src/'app.js').read_text(encoding='utf-8')
page = shell.replace('/*__CSS__*/', css).replace('/*__DATA__*/', data).replace('/*__APP__*/', app)
head, body = page.split('<!--__BODY__-->')
fragment = head + body
out_frag = pathlib.Path(sys.argv[1]); out_full = pathlib.Path(sys.argv[2])
out_frag.write_text(fragment, encoding='utf-8')
full = ('<!doctype html>\n<html lang="de">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}</style>\n'
        + head.strip() + '\n</head>\n<body>\n' + body.strip() + '\n</body>\n</html>\n')
out_full.parent.mkdir(parents=True, exist_ok=True)
out_full.write_text(full, encoding='utf-8')
print(len(fragment.encode()), len(full.encode()))
