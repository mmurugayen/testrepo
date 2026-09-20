#!/usr/bin/env python3
"""Render the adjacent diagrams.json to standalone accessible SVGs (stdlib only)."""
import json
import logging
from html import escape
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

def text(parts, x, y, value, size=16, color='#23384d', weight=400):
    logger.debug("rendering text element")
    parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(str(value))}</text>')

def box(parts,x,y,w,h,title,detail,fill='#ffffff',stroke='#91a7ba'):
    logger.debug("rendering diagram box")
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    title_lines=textwrap.wrap(title,width=max(18,int((w-36)/10)))
    yy=y+29
    for line in title_lines:
        text(parts,x+18,yy,line,18,weight=700)
        yy+=23
    for line in detail:
        for row in textwrap.wrap(line,width=max(20,int((w-36)/7.3))):
            text(parts,x+18,yy+8,row,14,color='#496277')
            yy+=20
    if yy+8 > y+h-8:
        raise ValueError('Text exceeds box: '+title)

def render(spec):
    logger.debug("rendering diagram")
    if "units" in spec:
        return render_containers(spec)
    arch=spec['kind']=='architecture'
    rows=max(n['row'] for n in spec['nodes'])+1
    height=180+rows*(210 if arch else 160)+100
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1220" height="{height}" viewBox="0 0 1220 {height}" role="img" aria-labelledby="title desc">',f'<title id="title">{escape(spec["title"])}</title>',f'<desc id="desc">{escape(spec["description"])}</desc>',f'<rect width="1220" height="{height}" fill="#f5f8fc"/>']
    text(parts,40,47,spec['title'],27,weight=700)
    text(parts,40,79,'ARCHITECTURE / COMPONENTS AND CONNECTIONS' if arch else 'WORKFLOW / ACTIONS, DECISIONS AND OUTCOMES',13,color='#236977',weight=700)
    text(parts,40,106,'Reviewed 2026-09-14 @ '+spec.get('source_commit','')[:12]+' | '+spec['subtitle'],14)
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
        ax,ay,aw,ah=a
        bx,by,bw,bh=b
        if ax==bx:
            x1=x2=ax+aw/2
            y1=ay+ah if by>ay else ay
            y2=by if by>ay else by+bh
        elif bx>ax:
            x1=ax+aw
            y1=ay+ah/2
            x2=bx
            y2=by+bh/2
        else:
            x1=ax
            y1=ay+ah/2
            x2=bx+bw
            y2=by+bh/2
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

def render_containers(spec):
    """Render structural containment and associations, without execution ordering."""
    logger.debug("rendering container diagram")
    rows=max(n['row'] for n in spec['units'])+1
    width=1400
    height=195+rows*310+65
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           f'<title id="title">{escape(spec["title"])}</title>',f'<desc id="desc">{escape(spec["description"])}</desc>',
           f'<rect width="{width}" height="{height}" fill="#f5f8fc"/>']
    text(parts,40,46,spec['title'],28,weight=700)
    text(parts,40,77,'ARCHITECTURE / DEPLOYMENT UNITS AND CONTAINED COMPONENTS',13,'#236977',700)
    text(parts,40,106,spec['subtitle'],15)
    text(parts,40,132,'Source: '+spec['repository']+' @ '+spec['source_commit'][:12]+' | Reviewed 2026-09-14',13,'#496277')
    text(parts,40,158,'Solid association: runtime interface or data access. Dashed association: source/configuration dependency.',13,'#496277')
    positions={n['id']:(45+460*n['col'],195+310*n['row'],390,240) for n in spec['units']}
    # Associations use the free lanes between deployment units. No arrowheads.
    for i,e in enumerate(spec['edges']):
        ax,ay,aw,ah=positions[e['from']]
        bx,by,bw,bh=positions[e['to']]
        if ay==by:
            if ax<bx:
                start=(ax+aw,ay+ah/2)
                end=(bx,by+bh/2)
            else:
                start=(ax,ay+ah/2)
                end=(bx+bw,by+bh/2)
            points=[start,end]
            lx=(start[0]+end[0])/2
            ly=start[1]-12
        elif ax==bx:
            if ay<by:
                start=(ax+aw/2,ay+ah)
                end=(bx+bw/2,by)
            else:
                start=(ax+aw/2,ay)
                end=(bx+bw/2,by+bh)
            points=[start,end]
            lx=start[0]+10
            ly=(start[1]+end[1])/2
        else:
            # A diagonal association exits via a side gutter and joins the target
            # from its top/bottom. This prevents drawing through contained text.
            start=(ax+aw if bx>ax else ax,ay+ah/2)
            lane=start[0]+(22 if bx>ax else -22)
            end=(bx+bw/2,by if by>ay else by+bh)
            gutter=by-28 if by>ay else by+bh+28
            points=[start,(lane,start[1]),(lane,gutter),(end[0],gutter),end]
            lx=(lane+end[0])/2
            ly=gutter-8
        dashed=' stroke-dasharray="6 4"' if e.get('dependency') else ''
        parts.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="#527085" stroke-width="2"{dashed}/>')
        label=e.get('label','')
        if label:
            for j,line in enumerate(textwrap.wrap(label,12)):
                w=len(line)*6.5+12
                yy=ly+j*16
                parts.append(f'<rect x="{lx-w/2}" y="{yy-12}" width="{w}" height="17" rx="3" fill="#f5f8fc"/>')
                text(parts,lx-w/2+6,yy,line,12)
    colors={'process':('#e5f2ee','#24766b'),'store':('#eaf0fb','#4d65a0'),'external':('#f2edf8','#8264a0'),'source':('#fff4e6','#ab7635'),'client':('#eaf2f6','#43728c'),'files':('#edf2f6','#607587')}
    for n in spec['units']:
        x,y,w,h=positions[n['id']]
        fill,stroke=colors[n['type']]
        dash=' stroke-dasharray="7 4"' if n['type']=='source' else ''
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash}/>')
        text(parts,x+18,y+24,n['boundary'].upper(),11,stroke,700)
        title=textwrap.wrap(n['title'],32)
        yy=y+52
        for line in title:
            text(parts,x+18,yy,line,19,weight=700)
            yy+=23
        yy=max(yy+4,y+85)
        for item in n['components']:
            lines=textwrap.wrap(item,45)
            hh=15+18*len(lines)
            if yy+hh>y+h-12:
                raise ValueError('Container overflow: '+n['title'])
            parts.append(f'<rect x="{x+12}" y="{yy-1}" width="{w-24}" height="{hh}" rx="5" fill="#ffffff" stroke="#cfdae2"/>')
            for line in lines:
                text(parts,x+24,yy+18,line,14)
                yy+=18
            yy+=21
    text(parts,40,height-49,'Containment describes ownership. Connections do not encode execution order. See WORKFLOWS.md for lifecycle decisions.',14)
    text(parts,40,height-25,spec.get('scope','Source-based architecture; site qualification remains separate.'),13,'#496277')
    parts.append('</svg>')
    return '\n'.join(parts)+'\n'

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if committed SVGs differ from their editable sources')
    args=parser.parse_args()
    specs=json.loads((ROOT/'diagrams.json').read_text())
    stale=[]
    for spec in specs:
        target=ROOT/(spec['id']+'.svg')
        expected=render(spec)
        if args.check:
            if not target.exists() or target.read_text()!=expected:
                stale.append(target.name)
        else:
            target.write_text(expected)
    if stale:
        raise SystemExit('Stale diagrams: '+', '.join(stale))
    print(('Checked' if args.check else 'Rendered')+f' {len(specs)} diagrams')
