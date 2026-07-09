import sys
with open(sys.argv[1],encoding='utf-8') as f: c=f.read()
checks=['dot-grid','wave-icon','character-img','top-bar','RANDOM','waveform','main-content','assets/']
for ch in checks:
 print(f'  {ch}:', 'OK' if ch in c else 'MISSING')
