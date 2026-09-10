"""Local entry discovery and content checks; no application imports."""

import hashlib
import json
import posixpath
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def local_path(root, parent, reference):
    url = urlsplit(reference)
    if url.scheme or url.netloc or url.path.startswith("/"):
        raise ValueError("External/absolute asset reference: " + reference)
    target = (parent / unquote(url.path)).resolve()
    target.relative_to(root.resolve())
    if not target.is_file():
        raise ValueError("Missing local asset: " + str(target))
    return target


class EntryParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.styles = []
        self.icons = []
        self.inline_styles = []
        self.inline_scripts = []
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.scripts.append({"url": attrs["src"], "type": attrs.get("type", "text/javascript")})
        elif tag == "script" or tag == "style":
            self.capture = {"tag": tag, "line": self.getpos()[0], "text": ""}
        elif tag == "link":
            rel = attrs.get("rel", "").split()
            if "stylesheet" in rel:
                self.styles.append(attrs["href"])
            elif "icon" in rel:
                self.icons.append(attrs["href"])

    def handle_data(self, data):
        if self.capture is not None:
            self.capture["text"] += data

    def handle_endtag(self, tag):
        if self.capture is not None and self.capture["tag"] == tag:
            target = self.inline_styles if tag == "style" else self.inline_scripts
            target.append(self.capture)
            self.capture = None


def parse_entry(path, root):
    parser = EntryParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    def relative(ref):
        return local_path(root, path.parent, ref).relative_to(root).as_posix()

    return {
        "path": path.relative_to(root).as_posix(),
        "scripts": [{"path": relative(item["url"]), "type": item["type"]} for item in parser.scripts],
        "styles": [relative(url) for url in parser.styles],
        "icons": [relative(url) for url in parser.icons],
        "inline_styles": parser.inline_styles,
        "inline_scripts": parser.inline_scripts,
    }


def css_references(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    urls = re.findall(r"url\(\s*['\"]?([^'\")]+?)['\"]?\s*\)", text, flags=re.I)
    urls += re.findall(r"@import\s+['\"]([^'\"]+)['\"]", text, flags=re.I)
    return [url.strip() for url in urls if not url.strip().lower().startswith(("data:", "#"))]


def verify_snapshot(root, manifest):
    seen = set()
    for item in manifest["files"]:
        name = item["path"]
        if name in seen:
            raise ValueError("Duplicate snapshot asset: " + name)
        seen.add(name)
        file = local_path(root, root, name)
        data = file.read_bytes()
        if digest(data) != item["sha256"] or len(data) != item["size"]:
            raise ValueError("Snapshot hash mismatch: " + name)
    return seen


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def asset_mime(name):
    if name.rsplit("/", 1)[-1].upper().endswith("LICENSE"):
        return "text/plain"
    types = {".js": "application/javascript", ".css": "text/css", ".json": "application/json",
             ".svg": "image/svg+xml", ".ttf": "font/ttf", ".woff": "font/woff", ".woff2": "font/woff2",
             ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".txt": "text/plain"}
    suffix = Path(name).suffix.lower()
    if suffix not in types:
        raise ValueError("No declared MIME type for asset: " + name)
    return types[suffix]


def stylesheet_dependencies(name, data, published):
    result = set()
    for reference in css_references(data.decode("utf-8")):
        url = urlsplit(reference)
        if url.scheme or url.netloc or url.path.startswith("/") or "\\" in reference:
            raise ValueError("External/absolute stylesheet dependency: " + reference)
        target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path)))
        if not target.startswith("workbench/") or target not in published:
            raise ValueError("Unpublished stylesheet dependency: " + target)
        result.add(target)
    return sorted(result)


_SCRIPT_GLOBALS = r"""
try {
const fs=require('node:fs'), request=JSON.parse(fs.readFileSync(0,'utf8'));
const babel=require(request.babel_path);
if(babel.version!=='7.29.0')throw Error('Unexpected dependency analyzer Babel version');
const browser=new Set(('window self globalThis document location history navigator console localStorage sessionStorage '+
  'setTimeout clearTimeout setInterval clearInterval requestAnimationFrame cancelAnimationFrame queueMicrotask getComputedStyle '+
  'addEventListener removeEventListener dispatchEvent scrollTo matchMedia URL URLSearchParams Blob File FileReader FormData '+
  'AbortController fetch ResizeObserver MutationObserver Event CustomEvent PopStateEvent HTMLElement Element Node DOMParser DOMException '+
  'TextEncoder TextDecoder XMLSerializer performance crypto CSS Intl innerWidth innerHeight devicePixelRatio pageYOffset scrollX scrollY module exports require define').split(' '));
const windows=new Set(['window','self','globalThis']);
// 0: local value; 1: proven browser root; 2: a possible root with ambiguous provenance.
const merge=values=>values.includes(2) || (values.includes(1) && values.includes(0))?2:values.includes(1)?1:0;
function browserGuard(p){
  if(!p.isBinaryExpression() || !['==','===','!=','!=='].includes(p.node.operator))return null;
  let type=p.get('left'), value=p.get('right');
  if(value.isUnaryExpression({operator:'typeof'}))[type,value]=[value,type];
  if(!type.isUnaryExpression({operator:'typeof'}) || !value.isStringLiteral())return null;
  const arg=type.get('argument');
  if(!arg.isIdentifier() || !windows.has(arg.node.name) || arg.scope.getBinding(arg.node.name))return null;
  const equal=value.node.value==='object';
  return ['==','==='].includes(p.node.operator)?equal:!equal;
}
function parameterInputs(binding){
  const fn=binding.path.parentPath;
  if(!fn.isFunction())return [];
  const index=fn.node.params.indexOf(binding.path.node), parent=fn.parentPath;
  if(index<0)return [];
  let calls=[], escaped=false;
  if(parent.isCallExpression() && parent.get('callee')===fn)calls=[parent];
  else {
    const name=fn.isFunctionDeclaration()?fn.node.id.name:
      parent.isVariableDeclarator() && parent.get('id').isIdentifier()?parent.node.id.name:null;
    const owner=name && (fn.isFunctionDeclaration()?fn.scope.parent:parent.scope).getBinding(name);
    if(!owner)return [];
    escaped=!owner.constant;
    for(const ref of owner.referencePaths){
      if(ref.parentPath.isCallExpression() && ref.key==='callee')calls.push(ref.parentPath);
      else escaped=true;
    }
  }
  const inputs=calls.map(call=>call.get('arguments')[index]);
  if(escaped)inputs.push(null);
  return inputs;
}
function windowRoot(p, seen=new Set()){
  if(!p || !p.node)return 0;
  if(p.isThisExpression())return p.findParent(q=>q.isFunction() && !q.isArrowFunctionExpression())?0:1;
  if(p.isConditionalExpression()){
    const guard=browserGuard(p.get('test'));
    return guard===null?merge([windowRoot(p.get('consequent'),seen),windowRoot(p.get('alternate'),seen)]):
      windowRoot(p.get(guard?'consequent':'alternate'),seen);
  }
  if(p.isLogicalExpression()){
    const left=windowRoot(p.get('left'),seen), right=windowRoot(p.get('right'),seen);
    return left===1?(p.node.operator==='&&'?right:1):merge([left,right]);
  }
  if(p.isSequenceExpression())return windowRoot(p.get('expressions').slice(-1)[0],seen);
  if(p.isAssignmentExpression({operator:'='}))return windowRoot(p.get('right'),seen);
  if(!p.isIdentifier())return 0;
  const binding=p.scope.getBinding(p.node.name);
  if(!binding)return windows.has(p.node.name)?1:0;
  if(seen.has(binding))return 0;
  const next=new Set(seen);next.add(binding);
  const inputs=binding.path.isVariableDeclarator() && binding.path.get('id').isIdentifier()?
    [binding.path.get('init')]:binding.kind==='param'?parameterInputs(binding):[];
  let result=merge(inputs.map(input=>windowRoot(input,next)));
  if(!binding.constant){
    const writes=binding.constantViolations.map(write=>write.isAssignmentExpression({operator:'='})?
      windowRoot(write.get('right'),next):0);
    if(result || writes.some(Boolean))result=2;
  }
  return result;
}
const rootMember=p=>{
  if(!p.isMemberExpression() && !p.isOptionalMemberExpression())return null;
  const root=windowRoot(p.get('object'));
  if(root===2)throw Error('Ambiguous script global alias: '+p.get('object').toString());
  if(!root)return null;
  const property=p.get('property');
  if(p.node.computed && !property.isStringLiteral())throw Error('Unresolved dynamic script global: '+p.toString());
  return property.isIdentifier()?property.node.name:property.isStringLiteral()?property.node.value:null;
};
const reports=request.sources.map(item=>{
  if(item.known)return {path:item.path,provides:item.known.provides,reads:item.known.reads};
  const provides=new Set(), reads=new Set();
  babel.transform(item.code,{filename:item.path,sourceType:'script',code:false,ast:false,plugins:[()=>({visitor:{
    Program(p){Object.keys(p.scope.bindings).forEach(name=>provides.add(name));},
    ReferencedIdentifier(p){if(!p.scope.hasBinding(p.node.name))reads.add(p.node.name);},
    AssignmentExpression(p){const name=rootMember(p.get('left'));if(name)provides.add(name);},
    'MemberExpression|OptionalMemberExpression'(p){const name=rootMember(p);if(name)reads.add(name);}
  }})]});
  return {path:item.path,provides:[...provides],reads:[...reads]};
});
const owners=new Map();
for(const item of reports)for(const name of item.provides){
  if(owners.has(name))throw Error('Duplicate script global provider: '+name);
  owners.set(name,item.path);
}
const result={};
for(const item of reports){
  const dependencies=new Map(), missing=[];
  for(const symbol of item.reads){
    const owner=owners.get(symbol);
    if(owner===item.path || browser.has(symbol))continue;
    if(!owner){missing.push(symbol);continue;}
    if(!dependencies.has(owner))dependencies.set(owner,new Set());
    dependencies.get(owner).add(symbol);
  }
  if(missing.length)throw Error('Unresolved script globals in '+item.path+': '+missing.sort().join(', '));
  result[item.path]=[...dependencies].sort(([a],[b])=>a.localeCompare(b,'en'))
    .map(([asset,symbols])=>({path:asset,symbols:[...symbols].sort()}));
}
process.stdout.write(JSON.stringify(result));
} catch(error) {
  process.stderr.write(error.message+'\n');
  process.exitCode=1;
}
"""


def script_dependencies(node, babel_path, payload, load_order, vendor_scripts):
    if len(vendor_scripts) != 2:
        raise ValueError("Expected exactly the pinned React and ReactDOM UMD assets")
    known = {vendor_scripts[0]: {"provides": ["React"], "reads": []},
             vendor_scripts[1]: {"provides": ["ReactDOM"], "reads": ["React"]}}
    request = {"babel_path": str(babel_path), "sources": [
        {"path": name, "code": payload[name].decode("utf-8"), "known": known.get(name)} for name in load_order]}
    result = subprocess.run([node, "-e", _SCRIPT_GLOBALS], input=json.dumps(request),
                            text=True, encoding="utf-8", capture_output=True)
    if result.returncode:
        raise ValueError("Script dependency analysis failed: " + result.stderr.strip())
    evidence = json.loads(result.stdout)
    indices = {name: index for index, name in enumerate(load_order)}
    for name, references in evidence.items():
        references.sort(key=lambda item: item["path"])
        for reference in references:
            if reference["path"] not in indices or indices[reference["path"]] >= indices[name]:
                raise ValueError("Script dependency must load earlier: " + name + " -> " + reference["path"])
    return evidence


def license_origin(root, component, identifiers, source, distributed, scope, provenance=None):
    data = (root / source).read_bytes()
    for identifier in identifiers:
        if identifier.encode("ascii") not in data:
            raise ValueError("License identifier not found in local notice: " + source)
    result = {"component": component, "status": "documented", "identifiers": identifiers,
              "requires_review": False, "scope": scope,
              "source": {"path": source, "sha256": digest(data), "asset_path": distributed}}
    if provenance:
        result["provenance"] = provenance
    return result


def unknown_license(component, sources, reason):
    return {"component": component, "status": "unknown", "identifiers": [], "requires_review": True,
            "source": None, "scope": "Only the listed source content; no license inferred from dependencies.",
            "source_files": sources, "reason": reason}
