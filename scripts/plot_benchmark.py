"""Plot measured benchmark results; matplotlib is an optional docs dependency."""
import json,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent
rows=json.loads((ROOT/'docs/assets/benchmark.json').read_text())['rows']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
colors=['#6750a4','#16877b']
fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
for condition,color in zip(('Voz limpia','Voz + tonos'),colors):
    subset=[r for r in rows if r['condition']==condition]
    shift=-.12 if condition=='Voz limpia' else .12
    x=[r['case']+shift for r in subset]
    axes[0].scatter(x,[100*r['wer'] for r in subset],s=65,label=condition,color=color)
    axes[1].scatter(x,[r['rtf'] for r in subset],s=65,label=condition,color=color)
for ax in axes:
    ax.set_xticks(range(1,6));ax.set_xlabel('Frase sintética (5 casos emparejados)');ax.grid(axis='y',alpha=.2);ax.set_ylim(bottom=0)
axes[0].set_ylim(0,max(r['wer']*100 for r in rows)*1.2 or 1)
axes[1].set_ylim(0,max(r['rtf'] for r in rows)*1.2)
axes[0].set_title('Error de palabras (WER) · menor es mejor');axes[0].set_ylabel('Errores / palabras de referencia (%)');axes[0].legend()
axes[1].set_title('Tiempo de proceso / duración del clip');axes[1].set_ylabel('RTF · menor es más rápido')
fig.suptitle('Ensayo local pequeño · voz Piper + Moonshine ES',fontsize=16)
fig.text(.5,-.04,'Tonos añadidos a 10 dB SNR; no música real. Clips de 12,2 s con silencio. RTF incluye carga del modelo; no mide latencia en vivo.',ha='center',fontsize=9)
fig.savefig(ROOT/'docs/assets/precision-efficiency.png',dpi=170,bbox_inches='tight')
summary={}
for condition in ('Voz limpia','Voz + tonos'):
    subset=[r for r in rows if r['condition']==condition];errs=sum(r['word_errors'] for r in subset);n=sum(r['words'] for r in subset)
    summary[condition]={'n':len(subset),'words':n,'errors':errs,'wer_percent':100*errs/n,'median_rtf':statistics.median(r['rtf'] for r in subset),'rtf_min':min(r['rtf'] for r in subset),'rtf_max':max(r['rtf'] for r in subset),'median_seconds':statistics.median(r['asr_process_seconds'] for r in subset)}
(ROOT/'docs/assets/summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
