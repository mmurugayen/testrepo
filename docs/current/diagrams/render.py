#!/usr/bin/env python3
"""Render the adjacent diagrams.json to standalone accessible SVGs (stdlib only)."""
import json
from html import escape
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parent

def text(parts, x, y, value, size=16, color='#23384d', weight=400):
    parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(str(value))}</text>')

def box(parts,x,y,w,h,title,detail,fill='#ffffff',stroke='#91a7ba'):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    title_lines=textwrap.wrap(title,width=max(18,int((w-36)/10)))
    yy=y+29
    for line in title_lines:
        text(parts,x+18,yy,line,18,weight=700);yy+=23
    for line in detail:
        for row in textwrap.wrap(line,width=max(20,int((w-36)/7.3))):
            text(parts,x+18,yy+8,row,14,color='#496277');yy+=20
    if yy+8 > y+h-8:
        raise ValueError('Text exceeds box: '+title)

def render(spec):
    arch=spec['kind']=='architecture'
    rows=max(n['row'] for n in spec['nodes'])+1
    height=180+rows*(210 if arch else 160)+100
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1220" height="{height}" viewBox="0 0 1220 {height}" role="img" aria-labelledby="title desc">',f'<title id="title">{escape(spec["title"])}</title>',f'<desc id="desc">{escape(spec["description"])}</desc>',f'<rect width="1220" height="{height}" fill="#f5f8fc"/>']
    text(parts,40,47,spec['title'],27,weight=700)
    text(parts,40,79,'ARCHITECTURE / COMPONENTS AND CONNECTIONS' if arch else 'WORKFLOW / ACTIONS, DECISIONS AND OUTCOMES',13,color='#236977',weight=700)
    text(parts,40,106,'Source review: 14 September 2026 | '+spec['subtitle'],14)
    if arch:
        for col,label in enumerate(spec['zones']):
            x=30+col*400
            parts.append(f'<rect x="{x}" y="137" width="360" height="{height-195}" rx="15" fill="{["#eaf0f8","#e5f2ee","#eef0f6"][col]}" stroke="#c4d3df"/>')
            text(parts,x+16,163,label,15,weight=700)
    else:
        parts.append('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#376a80"/></marker></defs>')
    positions={}
    for n in spec['nodes']:
        x=50+n['col']*400 if arch else (70 if n['col']==0 else 870)
        y=185+n['row']*(210 if arch else 160)
        positions[n['id']]=(x,y,320 if arch else (670 if n['col']==0 else 300),140 if arch else 112)
    # Render associations under boxes. Architecture has no arrowheads or temporal sequence.
    for e in spec['edges']:
        a,b=positions[e['from']],positions[e['to']]
        ax,ay,aw,ah=a;bx,by,bw,bh=b
        if ax==bx:
            x1=x2=ax+aw/2;y1=ay+ah if by>ay else ay;y2=by if by>ay else by+bh
        elif bx>ax:
            x1=ax+aw;y1=ay+ah/2;x2=bx;y2=by+bh/2
        else:
            x1=ax;y1=ay+ah/2;x2=bx+bw;y2=by+bh/2
        points=e.get('points',[[x1,y1],[x2,y2]])
        if arch and ax==bx and abs(by-ay)>210 and 'points' not in e:
            lane=ax+aw+12
            points=[[ax+aw,ay+ah/2],[lane,ay+ah/2],[lane,by+bh/2],[bx+bw,by+bh/2]]
        arrow='' if arch else ' marker-end="url(#arrow)"'
        pts=' '.join(f'{x},{y}' for x,y in points)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#376a80" stroke-width="2"{arrow}/>')
        if e.get('label'):
            lines=textwrap.wrap(e['label'],width=10 if arch else 16)
            for index,line in enumerate(lines):
                w=len(line)*6.8+10
                lx,ly=e.get('label_at',[(x1+x2)/2-w/2+4,(y1+y2)/2-9-15*(len(lines)-1)])
                ly+=index*15
                parts.append(f'<rect x="{lx-4}" y="{ly-13}" width="{w}" height="19" rx="3" fill="#f5f8fc"/>')
                text(parts,lx,ly,line,12)
    for n in spec['nodes']:
        box(parts,*positions[n['id']],n['title'],n.get('detail',[]),fill='#fff2e9' if n.get('warning') else '#ffffff')
    text(parts,40,height-32,'Lines show structural dependencies; boxes identify components and their deployment boundary.' if arch else 'Arrows show order and explicit alternative outcomes. See the guide for command and authority details.',14)
    parts.append('</svg>')
    return '\n'.join(parts)+'\n'

if __name__=='__main__':
    specs=json.loads((ROOT/'diagrams.json').read_text())
    for spec in specs:
        (ROOT/(spec['id']+'.svg')).write_text(render(spec))
    print(f'Rendered {len(specs)} diagrams')
