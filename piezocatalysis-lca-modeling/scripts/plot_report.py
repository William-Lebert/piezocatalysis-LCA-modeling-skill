#!/usr/bin/env python3
"""Render project plot data to editable SVG, PNG, CSV and a provenance manifest."""
import argparse,csv,hashlib,json,math,sys,textwrap
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def draw(data,dest,locale,font_path,dpi):
    if data.get('schema_version')!='piezolca.plot-data/1' or data.get('kind') not in ('cycles','stages','scenarios','sensitivity'):
        raise ValueError('unsupported plot data schema')
    if not isinstance(data.get('rows'),list) or not data['rows'] or not isinstance(data.get('warnings'),list):raise ValueError('plot rows and warnings required')
    if not isinstance(data.get('license_note'),str) or not data['license_note'].strip():raise ValueError('license note required')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.font_manager import FontProperties
    matplotlib.rcParams['svg.fonttype']='none';matplotlib.rcParams['svg.hashsalt']='piezolca-v1';matplotlib.rcParams['axes.unicode_minus']=False
    font=None
    if font_path:font=FontProperties(fname=str(font_path))
    elif locale=='zh':
        for path in ('/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/STHeiti Light.ttc','/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'):
            if Path(path).is_file():font=FontProperties(fname=path);break
        if font is None:raise ValueError('Chinese font not found; provide --font-path or use --locale en')
    if font:
        font_manager.fontManager.addfont(font.get_file())
        matplotlib.rcParams['font.family']=font.get_name()
    rows=data['rows'];kind=data['kind'];zh=locale=='zh'
    title=data['title_zh' if zh else 'title_en']
    fu=data.get('functional_unit');fu_text=(str(fu.get('value',fu.get('amount','')))+' '+str(fu.get('unit',''))+(' — '+str(fu.get('description','')) if fu.get('description') else '')) if isinstance(fu,dict) else str(fu)
    category=data.get('category',{});unit=category.get('unit','')
    db=data.get('database') or {};method=data.get('method') or {}
    context_line=('Database: '+str(db.get('name',''))+' '+str(db.get('version',''))+' | Method: '+str(method.get('name',''))) if db or method else ''
    notes=['FU: '+fu_text]+([context_line] if context_line else [])+['Source SHA-256: '+', '.join(x['sha256'][:12] for x in data['provenance']['inputs'].values()),
           'License: '+data['license_note']]+(['Data basis: '+data['data_basis']] if data.get('data_basis') else [])+data['warnings']
    wrapped=[]
    for note in notes:
        wrapped.extend(textwrap.wrap(str(note),width=95,break_long_words=True,replace_whitespace=False) or [''])
    foot_height=max(1.15,len(wrapped)*0.17+0.22);plot_height=max(3.5,len(rows)*.38+1.6) if kind in ('stages','sensitivity') else 4.2
    if kind=='sensitivity':plot_height=max(4.0,len(rows)*.55+1.6)
    fig=plt.figure(figsize=(12,plot_height+foot_height));gs=fig.add_gridspec(2 if kind=='cycles' else 1,1,left=.37 if kind=='sensitivity' else .18,right=.95,top=1-0.98/(plot_height+foot_height),bottom=foot_height/(plot_height+foot_height),hspace=.55)
    if kind=='cycles':
        axes=[fig.add_subplot(gs[i,0]) for i in range(2)];xs=list(range(len(rows)))
        for i,r in enumerate(rows):
            v=r.get('apparent_removal_mg');lo=r.get('removal_lower_mg');hi=r.get('removal_upper_mg');e=r.get('treatment_energy_kwh')
            if v is not None:axes[0].scatter(i,v,color='#007f86',s=42,zorder=3)
            elif lo is not None and hi is not None:axes[0].vlines(i,lo,hi,color='#007f86',lw=3);axes[0].scatter([i,i],[lo,hi],color='#007f86',s=20)
            else:axes[0].annotate('缺失' if zh else 'missing',(i,0),xytext=(0,5),textcoords='offset points',ha='center',fontsize=8)
            if e is not None:axes[1].bar(i,e,color='#c9863b',width=.55)
            else:axes[1].annotate('缺失' if zh else 'missing',(i,0),xytext=(0,5),textcoords='offset points',ha='center',fontsize=8)
        from matplotlib.lines import Line2D
        legend=[]
        if any(r.get('apparent_removal_mg') is not None for r in rows):legend.append(Line2D([0],[0],marker='o',color='#007f86',linestyle='None',label='精确观测' if zh else 'Exact observation'))
        if any(r.get('apparent_removal_mg') is None and r.get('removal_lower_mg') is not None and r.get('removal_upper_mg') is not None for r in rows):legend.append(Line2D([0],[0],marker='|',markersize=12,color='#007f86',linestyle='-',label='检测限区间' if zh else 'Censored interval'))
        if legend:axes[0].legend(handles=legend,loc='best',fontsize=8)
        axes[0].set_ylabel('表观去除 (mg)' if zh else 'Apparent removal (mg)');axes[1].set_ylabel('处理能耗 (kWh)' if zh else 'Treatment energy (kWh)')
        for ax in axes:
            ax.set_xlim(-.6,len(rows)-.4);ax.set_xticks(xs,[str(r['cycle']) for r in rows]);ax.set_xlabel('循环' if zh else 'Cycle');ax.grid(axis='y',alpha=.2)
    elif kind in ('stages','sensitivity'):
        ax=fig.add_subplot(gs[0,0]);ys=list(range(len(rows)))
        labels=[({'preparation':'制备','treatment':'处理'}.get(r['stage'],r['stage']) if zh else r['stage']) if kind=='stages' else textwrap.fill(r['variable']+' ('+r['setting']+')',width=34) for r in rows]
        vals=[r['contribution'] if kind=='stages' else r['delta'] for r in rows]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):raise ValueError('invalid plotted values')
        ax.barh(ys,vals,color=['#007f86' if v>=0 else '#c76352' for v in vals]);ax.axvline(0,color='#555',lw=.8)
        ax.set_yticks(ys,labels);ax.invert_yaxis();ax.set_xlabel((('贡献' if zh else 'Contribution') if kind=='stages' else ('变化量' if zh else 'Change from baseline'))+' ('+unit+')');ax.grid(axis='x',alpha=.2)
    else:
        ax=fig.add_subplot(gs[0,0]);labels=[('基准' if r['case']=='baseline' else '情景') if zh else r['case'] for r in rows];vals=[r['amount'] for r in rows]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):raise ValueError('invalid plotted values')
        ax.bar(range(len(rows)),vals,color=['#4c787a','#c9863b'][:len(rows)]);ax.set_xticks(range(len(rows)),labels);ax.set_ylabel(('影响' if zh else 'Impact')+' ('+unit+')');ax.axhline(0,color='#555',lw=.8);ax.grid(axis='y',alpha=.2)
    fig.suptitle(title,fontsize=15,fontweight='bold',y=1-.16/(plot_height+foot_height))
    if category.get('name'):fig.text(.5,1-.55/(plot_height+foot_height),textwrap.fill(category['name'],width=100),ha='center',va='center',fontsize=9,fontproperties=font)
    fig.text(.04,.03,'\n'.join(wrapped),ha='left',va='bottom',fontsize=7.5,color='#444',fontproperties=font)
    dest.mkdir(parents=True,exist_ok=False)
    (dest/'plot-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (dest/'table.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    fig.savefig(dest/'chart.svg',format='svg',metadata={'Date':None});fig.savefig(dest/'chart.png',format='png',dpi=dpi);plt.close(fig)
    manifest={'schema_version':'piezolca.plot-manifest/1','input_plot_data_sha256':hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
              'source_files':data['provenance']['inputs'],'data_generator_sha256':data['provenance']['generator_sha256'],
              'renderer_sha256':sha(Path(__file__)),'matplotlib_version':matplotlib.__version__,'python_version':sys.version.split()[0],
              'locale':locale,'font':font.get_file() if font else 'matplotlib default','font_sha256':sha(Path(font.get_file())) if font else None,'dpi':dpi,'license_note':data['license_note'],
              'outputs':{name:sha(dest/name) for name in ('plot-data.json','table.csv','chart.svg','chart.png')}}
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--locale',choices=('zh','en'),default='zh');p.add_argument('--font-path',type=Path);p.add_argument('--dpi',type=int,default=200)
    a=p.parse_args()
    if not 72<=a.dpi<=600:p.error('dpi must be 72–600')
    try:
        data=json.loads(a.input.read_text(encoding='utf-8'),parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid number '+x)))
        draw(data,a.output_dir,a.locale,a.font_path,a.dpi);print('Wrote',a.output_dir);return 0
    except (OSError,ValueError,KeyError,TypeError,ImportError) as e:print('ERROR:',e,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
