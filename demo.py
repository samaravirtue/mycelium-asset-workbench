"""Layered synthetic world kit. Diagrams, not 3D models or book canon."""
from pathlib import Path
import html
from workbench import Catalog, atomic_json

DOMAINS={'seelie':('Sun Court','#c9a84c'),'unseelie':('Frost Court','#86c5dd'),'wilds':('Wild Network','#80bd95'),'underwave':('Underwave','#7ea6cb')}
LAYERS=['underground','terrain','water','flora','structures','sky']
DETAILS={
'underground':('Root chamber','Below-ground chamber connects to surface access shaft; clearance and collision untested.'),
 'terrain':('Terrace tile','32 x 32 metre proposed tile; east/west seam positions declared, not engine-tested.'),
 'water':('Water boundary','Flow boundary and depth zone; water shader and swimming behaviour not implemented.'),
 'flora':('Canopy cluster','Irregular planting cluster with three size classes; spacing is a layout proposal.'),
 'structures':('Palace entrance module','Facade, doorway and interior attachment slots; no claim of complete palace geometry.'),
 'sky':('Atmosphere study','Palette reference for sky and fog; no physical sky simulation.')}

def run():
    root=Path('layered_demo');root.mkdir(exist_ok=True)
    cat=Catalog(root/'catalog');existing={r['id'] for r in cat.rows()};slots=[];cards=[]
    for di,(domain,(label,color)) in enumerate(DOMAINS.items()):
        pieces=[]
        for li,layer in enumerate(LAYERS):
            title,note=DETAILS[layer];key=domain+'-'+layer
            # Every source is a new procedural SVG layer diagram, not private artwork.
            svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="180" viewBox="0 0 400 180"><rect width="400" height="180" fill="#152b2a"/><path d="M40 120 L200 70 L360 120 L200 165 Z" fill="{color}" opacity=".65"/><path d="M40 120 L200 70 L360 120 M200 70 V165" fill="none" stroke="white"/><text x="20" y="30" fill="white" font-family="sans-serif">{html.escape(label+" / "+layer)}</text><text x="20" y="52" fill="white" font-family="sans-serif">SYNTHETIC LAYOUT - NOT A 3D MESH</text></svg>'
            path=root/(key+'.svg');path.write_text(svg,encoding='utf8')
            status='proposal' if layer in ('structures','terrain','underground') else 'reference'
            tags=[domain,layer,'synthetic','layered', 'winter' if domain=='unseelie' else 'summer' if domain=='seelie' else 'network' if domain=='wilds' else 'ocean']
            if key not in existing:cat.ingest(path,key,label+' / '+title,domain,layer,tags,'synthetic:demo.py procedural diagram',note,status)
            slots.append({'asset_id':key,'cell':[di,0],'layer':layer,'elevation_band_m':[-20,-1] if layer=='underground' else [0,5] if layer in ('terrain','water') else [5,60], 'revision':'demo-v1','source_asset_id':key,'engine_ready':False,'requires':['scale review','collision test','material conversion']})
            pieces.append(f'<div class="layer" style="border-color:{color}"><b>{layer}</b> &middot; {html.escape(title)}<small>{html.escape(note)}</small></div>')
        cards.append(f'<section><h2 style="color:{color}">{label}</h2>{"".join(pieces)}</section>')
    links=[{'from':'wilds-underground','to':d+'-underground','type':'proposed passage','tested':False} for d in ('seelie','unseelie','underwave')]
    links += [{'from':d+'-'+a,'to':d+'-'+b,'type':kind,'tested':False} for d in DOMAINS for a,b,kind in [('underground','terrain','surface access'),('water','terrain','shore boundary')]]
    atomic_json(root/'scene_plan.json',{'schema_version':1,'synthetic':True,'canonical_geography':False,'assets':slots,'connections':links,'note':'Planning records only; not loaded or tested in a 3D engine.'})
    atomic_json(root/'project_index.json',{'schema_version':1,'synthetic':True,'exhaustive_inventory':False,'projects':[{'id':'demo-os','name':'Synthetic Workspace','kind':'os','status':'prototype','asset_ids':['wilds-flora','wilds-sky']},{'id':'demo-game','name':'Synthetic Exploration','kind':'game','status':'planning','asset_ids':['wilds-terrain','wilds-underground','underwave-water']},{'id':'demo-world','name':'Synthetic Realm Atlas','kind':'world','status':'planning','asset_ids':[s['asset_id'] for s in slots]}],'relationships':[{'from':'demo-os','to':'demo-game','type':'proposed shared assets','tested':False},{'from':'demo-game','to':'demo-world','type':'proposed scene dependency','tested':False}],'provenance':{'source':'demo.py fictional fixtures','revision':'demo-v1'},'note':'Identifiers connect projects without copying private project content. Not a real project inventory.'})
    atomic_json(root/'manifest.json',cat.manifest());cat.report(root/'gallery.html');cat.close()
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Layered world organization demo</title><style>body{font:16px system-ui;background:#102323;color:#edf7ef;max-width:1200px;margin:30px auto;padding:20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}.layer{padding:12px;margin:8px 0;background:#213c39;border-left:4px solid}small{display:block;margin-top:6px;color:#bdd5cf}h1{color:#b6e5ad}a{color:#b6e5ad}</style><h1>Layered world kit</h1><p>24 synthetic references across four illustrative domains. Domain â†’ layer â†’ module. This demonstrates organization, not a finished world or private story canon.</p><p><a href="gallery.html">Search catalog</a> Â· <a href="scene_plan.json">Inspect connection plan</a> Â· <a href="manifest.json">Inspect provenance manifest</a></p><div class="grid">'+''.join(cards)+'</div><h2>Connection network</h2><p>Wild Network underground â†’ Sun Court, Frost Court and Underwave. All are proposed connections, not working portals. Six vertical layers per domain preserve the underground-to-sky organization. No creature assets included.</p></html>'
    (root/'layers.html').write_text(page,encoding='utf8')
    print('Open layered_demo/layers.html or layered_demo/gallery.html. 24 synthetic diagrams; zero production-ready meshes.')
if __name__=='__main__':run()
