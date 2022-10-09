import os
import sys
import typing
import traceback
import subprocess
import copy
import json
import texttable as tt
from gixy.parser.nginx_parser import NginxParser
from enum import Flag
from collections import OrderedDict
from pathlib import Path
from decimal import Decimal


# Constants
class C_():
    SERVER_CMD = ('status','list', 'test', 'start', 'stop', 'reload', 'restart')
    SITE_CMD = ('enable', 'disable', 'start', 'stop', 'config', 'status')
    WSGI_CMD = ('status', 'start', 'stop', 'restart')
    PATH_SITES_A = '/etc/nginx/sites-available'
    PATH_SITES_E = '/etc/nginx/sites-enabled'
    TYPES_PRIMITIVE = {str, int, float, complex, bool, bytes, bytearray, memoryview, Decimal}
    TYPES_PRIMITIVE_STR = {'str', 'int', 'float', 'complex', 'bool', 'bytes', 'bytearray', 'memoryview', 'Decimal'}
    TYPES_COMPLEX = {list, tuple, range, dict, set, frozenset}
    TYPES_COMPLEX_STR = {'list', 'tuple', 'range', 'dict', 'set', 'frozenset'}
    CHAR_BULLET = '\u25E6'
    NGINX_VER = None
    PERL_VER = None
    NGINX_RELOAD_BROKEN = False

def init():
    # pc(f" nginx ver: {get_nginx_ver()}")
    # pc(f" perl ver: {get_perl_ver()}")

    if get_nginx_ver() == '1.23.1':
        if get_perl_ver() == '5.30.0':
            # Cannot do reload of nginx because it will segfalt due to bug:
            #   . https://github.com/Perl/perl5/issues/17154
            C_.NGINX_RELOAD_BROKEN = True



def get_cmd_str(cmd, past:bool=False):
    if past:
        if cmd in ('enable', 'disable'): return f'{cmd}d'
        if cmd == 'stop': return 'stopped'
        return f"{cmd}ed"
    else:
        if cmd in ('status', 'list', 'test', 'config'): 
            return f'get {cmd}'
        return cmd
    




class BadSiteInfo():
    def __init__(self, path:bool, target:bool, name:str, reason:str): 
        self._path = path
        self._target = target
        self._name = name
        self._reason = reason
    @property
    def path(self):
        return self._path
    @property
    def target(self):
        return self._target
    @property
    def name(self):
        return self._name
    @property
    def reason(self):
        return self._reason
    def __str__(self):
        return f"Bad: {self.reason} - {self.name} ({self.path}/{self.name})"
    def __repr__(self):
        return self.__str__()

class SiteStatus(Flag):
    AVAILABLE = 1
    ENABLED = 2
    BAD = 4

AVAILABLE, ENABLED, BAD = (1,2,4)

class Site():
    def __init__(self, name, status:SiteStatus, bsi:BadSiteInfo=None):
        self.name = name
        self.status = status
        self.bsi = bsi
        self.site_name = None

        if self.status & BAD:
            self.site_cfg = None

        else:
            # Read config
            self.site_cfg = SiteConfig(self.name)


class SiteConfig():
    def __init__(self, name):
        self.name = name
        self.parse_ok = False
        self.config_lines=[]
        self.listens = []
        self.locations = []
        self.wsgi_sockets = []
        self.server_name = None

        _config_path = f"{C_.PATH_SITES_A}/{self.name}"
        with open(_config_path) as fp:
            for line in fp:
                _ls = line.strip()
                if _ls.find('#') == 0 or _ls == '': continue
                self.config_lines.append(line.replace('\t', '  ').replace('\n',''))
                
        raw_clean = '\n'.join(self.config_lines)
        

        try:
            nxp = NginxParser(cwd='', allow_includes=False)
            try:
                tree = nxp.parse(raw_clean)
            except Exception as ex:
                pc(f"Failed while parsing {_config_path}: {dumpCurExcept()}")

            _server = None
            for node in tree.children:
                if node.is_block and node.name == 'server':
                    _server = node
                    break

            for node in _server.children:
                if node.is_block:
                    if node.name == 'location':
                        location = node
                        self.locations.append(location.path)
                        for l_node in location.children:
                            if l_node.name == 'proxy_pass':
                                proxy_pass = l_node.args[0]
                                if proxy_pass.find('http://unix:') > -1:
                                    socket_path = proxy_pass[12:]
                                    self.wsgi_sockets.append((socket_path, os.path.isfile(socket_path)))

                    continue
                
                if node.name == 'listen':
                    self.listens.append(node.args)

                elif node.name == 'server_name':
                    self.server_name = node.args[0]


        except Exception as ex:
            pc(f"Failed during processing of NginxParser for config {_config_path}: {dumpCurExcept()}")

        if len(self.listens) > 0:
            self.parse_ok = True

        # rp = RawParser()
        # rp.parse(raw_clean)

        noop()


def find_site(site) -> tuple:
    sites=Sites(site_find=site)
    if site in sites._enab: return (True, sites._enab[site])
    if site in sites._avail: return (True, sites._avail[site])
    if site in sites._bad: return (True, sites._bad[site])
    return (False, None)
            

class Sites():
    def __init__(self, site_find:str=None):
        (a_sites, a_sites_bad) = self._get_sites(AVAILABLE, site_find=site_find)
        (e_sites, e_sites_bad) = self._get_sites(ENABLED, site_find=site_find)
        
        self._enab = OrderedDict()
        self._avail = OrderedDict()
        self._bad = OrderedDict()
        self._site_find = site_find

        for name in e_sites:
            site = Site(name, ENABLED)
            self._enab[name] = site

        for name in a_sites:
            if not name in self._enab:
                site = Site(name, AVAILABLE)
                self._avail[name] = site

        for badlink in e_sites_bad:
            assert not badlink.Name in e_sites, f"FATAL - bad enabled site should not be also in e_sites!"
            site = Site(badlink.Name, ENABLED|BAD, badlink)
            self._bad[name] = site

        for badlink in a_sites_bad:
            assert not badlink.Name in a_sites, f"FATAL - bad available site should not be also in a_sites!"
            site = Site(badlink.Name, AVAILABLE|BAD, badlink)
            self._bad[name] = site
        
        # a_sites_use = []
        # for a_site in a_sites:
        #     if not a_site in e_sites:
        #         a_sites_use.append(a_site)
            
        # self._avail = a_sites_use
        # self._enab = e_sites
        # self._bad = a_sites_bad + e_sites_bad

    @property
    def Avail(self) -> OrderedDict:
        return self._avail

    @property
    def Enabled(self) -> OrderedDict:
        return self._enab

    @property
    def Bad(self) -> OrderedDict:
        return self._bad

    def _get_sites(self, type:SiteStatus, site_find:str=None):
        if type == AVAILABLE:
            dir = C_.PATH_SITES_A
        elif type == ENABLED:
            dir = C_.PATH_SITES_E
        else:
            raise Exception(f"Invalid type: {type}")

        _path = Path(dir)
        good = []
        bad = []
        for fname in _path.rglob(site_find if isinstance(site_find, str) else '*'):
            if fname.is_symlink():
                full_path = fname._str
                if os.path.exists(full_path):
                    good.append(fname.name)
                else:
                    bad.append(BadSiteInfo(full_path, os.path.realpath(full_path), fname.name, "Broken Link"))

            elif fname.is_file():
                good.append(fname.name)
        
        return (good, bad)

class Nginx():
    def __init__(self):
        self._status_ok = False
        self._bad_rows = []
        self._reason = None

        with PExec(['nginx', '-t']) as p:
            if p.code > 1:
                raise Exception("Err occured while running `nginx -t`: {}. Code: {}, stdout: {}".format(p.err, p.code, p.out))
            elif len(p.out):
                # Note nginx -t returns message to stderr instead of stdout
                # return code is 0 (no error), but there is a message in stdout which is unexpeced for nginx -t
                pc("`nginx -t` return code is 0 but had stdout msg: {}. stderr: {}".format(p.out, p.err))

            out = p.err.strip()

            # nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
            # nginx: configuration file /etc/nginx/nginx.conf test is successful

            rows = out.split('\n')

            self._rows = rows

            if len(rows) < 2:
                self._status_ok = False
                self._reason =  f"Got unexpected output from % nginx -t . rows:\n'{pre(rows, 6)}'"
                return

            a_bad_rows = []
            for i, row in enumerate(rows):
                row = row.strip()
                iF = row.find('nginx:')
                if iF == 0: row = row[6:].strip()
                bFound = False
                for j in range(0, 2):
                    if j == 0:
                        (s1, s2) = ('the configuration file', ' syntax is ok')
                    else:
                        (s1, s2) = ('configuration file ', ' test is successful')

                    iFind = row.find(s1)
                    if iFind == -1: 
                        continue
                    iFind = row.find(s2, len(s1))
                    if iFind == -1:
                        continue
                    bFound = True
                    break

                if not bFound: a_bad_rows.append(row)
                
            self._status_ok = len(a_bad_rows) == 0
            self._bad_rows = a_bad_rows


    @property
    def ok(self) -> bool:
        return self._status_ok
    @property
    def badrows(self) -> list:
        return self._bad_rows
    @property
    def reason(self) -> str:
        return self._reason



def build_table():
    table = tt.Texttable(max_width=250)
    table.header(        ['Site', 'Enabled', 'Name','Listens', 'Notes'])
    table.set_cols_align(['l'   , 'c'      ,'l'    ,'l'      , 'l'])
    table.set_cols_dtype(['t'   , 't'      ,'t'    ,'t'      , 't'])
    table.set_deco(table.VLINES)
    return table

def _get_site_name_listens(_site):
    if _site.site_cfg is None or not _site.site_cfg.parse_ok: return ('-', '-')
    _sn = _site.site_cfg.server_name
    _sn = '-' if _sn is None else _sn

    _lstn = _site.site_cfg.listens
    _lstn = '\n'.join([' '.join(a) for a in (_lstn if isinstance(_lstn, list) else [])])
    # _lstn = '\n'.join(_lstn) if isinstance(_lstn, list) else '-'
    return (_sn, _lstn)

def table_add_ok_row(table, site):
    if site.site_cfg is None or not site.site_cfg.parse_ok:
        _sn, _lstn = ('-', '-')
    else:
        _sn = site.site_cfg.server_name
        _sn = '-' if _sn is None else _sn

        _lstn = site.site_cfg.listens
        _lstn = '\n'.join([' '.join(a) for a in (_lstn if isinstance(_lstn, list) else [])])

    table.add_row([site.name, 'x' if site.status == ENABLED else '-', _sn, _lstn, '-'])

def table_add_bad_row(table, site):
    bsi = site.bsi
    pad = ' ' * (len(bsi.Reason) + 1)
    table.add_row([bsi.Name, '(bad)', '-', '-' , f'{bsi.Reason} - {bsi.Path}\n{pad}~~> {bsi.Target}'])

def get_paths(name:str):
    assertNotBlank('name', name)
    return (f"{C_.PATH_SITES_A}/{name}", f"{C_.PATH_SITES_E}/{name}")
    
def enable_site(name) -> tuple:
    assertNotBlank('name', name)

    (_path_avail, _path_enabled) = get_paths(name)
    _pa = Path(_path_avail)
    if not _pa.is_symlink() and not _pa.is_file():
        raise Exception(f"site is not a file or symlink: {_path_avail}")

    assert not (Path(_path_enabled)).exists(), f"sites-enabled path exists: {_path_enabled}"

    cmd = ['ln', '-s', _path_avail, _path_enabled]
    with PExec(cmd) as p:
        if p.code > 1:
            raise Exception("Err occured while running `{}`: {}. Code: {}, stdout: {}".format(cmd, p.err, p.code, p.out))
        elif len(p.err):
            # return code is 0 (no error), but there is a message in stderr
            pc("`{}` return code is 0 but had stderr msg: {}. stdout: {}".format(cmd, p.err, p.out))

        out = p.out.strip()

        if out != '':
            if (Path(_path_enabled)).is_symlink():
                print("Note active-sites symlink was created ok but `ln -s` returned an unexpected message: {out}")
                return (True, None)
            else:
                return (False, f"Symlink not created and got unexpected output from `ln -s`: {out}")

        return (True, None)


def start_service(name:str) -> tuple:
    assertNotBlank('name', name)

    cmd = ['systemctl', 'start', name]
    with PExec(cmd) as p:
        if p.code > 1:
            raise Exception("Err occured while running `{}`: {}. Code: {}, stdout: {}".format(' '.join(cmd), p.err, p.code, p.out))
        elif len(p.err):
            # return code is 0 (no error), but there is a message in stderr
            pc("`{}` returned code 0 but had stderr msg: {}. stdout: {}".format(' '.join(cmd), p.err, p.out))

        out = p.out.strip()

        if out != '': return (False, f"service {name} could not be started: {out}")

        return (True, None)


def stop_service(name:str) -> tuple:
    assertNotBlank('name', name)

    cmd = ['systemctl', 'stop', name]
    with PExec(cmd) as p:
        if p.code > 1:
            raise Exception("Err occured while running `{}`: {}. Code: {}, stdout: {}".format(' '.join(cmd), p.err, p.code, p.out))
        elif len(p.err):
            # return code is 0 (no error), but there is a message in stderr
            pc("`{}` returned code 0 but had stderr msg: {}. stdout: {}".format(' '.join(cmd), p.err, p.out))

        out = p.out.strip()

        if out != '': return (False, f"service {name} could not be started: {out}")

        return (True, None)


def restart_service(name:str) -> tuple:
    assertNotBlank('name', name)

    cmd = ['systemctl', 'restart', name]
    with PExec(cmd) as p:
        if p.code > 1:
            raise Exception("Err occured while running `{}`: {}. Code: {}, stdout: {}".format(' '.join(cmd), p.err, p.code, p.out))
        elif len(p.err):
            # return code is 0 (no error), but there is a message in stderr
            pc("`{}` returned code 0 but had stderr msg: {}. stdout: {}".format(' '.join(cmd), p.err, p.out))

        out = p.out.strip()

        if out != '': return (False, f"service {name} could not be restarted: {out}")

        return (True, None)


def reload_nginx() -> tuple:
    if C_.NGINX_RELOAD_BROKEN:
        pc(f'nginx could not be reloaded (see pynx -h)')
        yn = input(f"{C_.CHAR_BULLET} Do you want to restart nginx instead (y|N)?")
        if yn.lower() == 'y':
            (ok, reason) = restart_service('nginx')
            if ok:
                pc(f'nginx restarted')
            else:
                return (False, reason)
        else:
            return (False, f'{C_.CHAR_BULLET} restart skipped. Please run manually: % sudo systemctl restart nginx')

        return (True, None)
    
    cmd = ['systemctl', 'reload', 'nginx']
    with PExec(cmd) as p:
        if p.code > 1:
            raise Exception("Err occured while running `{}`: {}. Code: {}, stdout: {}".format(' '.join(cmd), p.err, p.code, p.out))
        elif len(p.err):
            # return code is 0 (no error), but there is a message in stderr
            pc("`{}` returned code 0 but had stderr msg: {}. stdout: {}".format(' '.join(cmd), p.err, p.out))

        out = p.out.strip()

        if out != '':
            return (False, f"nginx could not be reloaded: {out}")

        return (True, None)


def get_sytemd_wsgi_status(wsgi) -> tuple:
    return _get_sytemd_service_status(wsgi, ['Loaded', 'Main PID', 'Tasks', 'Memory', 'CGroup'])

def get_sytemd_nginx_status() -> tuple:
    return _get_sytemd_service_status('nginx', ['Loaded', 'Process', 'Main PID', 'Tasks', 'Memory', 'CGroup'])


def _get_sytemd_service_status(name, data_keys) -> tuple:
    assertNotBlank('name', name)
    assert isinstance(data_keys, list), f"data_keys must be a list but got {getClassName(data_keys)}"

    cmd = ['systemctl', 'status', name, '--no-pager']
    data = OrderedDict()
    with PExec(cmd) as p:
        if p.code == 3:
            pass
        elif p.code > 1:
            raise Exception(f"Err occured while running `systemctl status {name}`: {p.err}. Code: {p.code}, stdout: {p.out}")
        elif len(p.err):
            # return code is 0 (no error), but there is a message in stderr
            pc(f"`systemctl status {name}` returned code 0 but had stderr msg: {p.err}. stdout: {p.out}")

        out = p.out.strip()

        if out == '':
            return (False, None, None, f"No output from systemctl status nginx")

        rows = out.split('\n')

        data = OrderedDict()

        active_status = None
        active_row = None

        for i, row in enumerate(rows):
            row = row.strip()
            if row == '': break
            iF = row.find(':')
            if iF == -1: continue
            key = row[0:iF].strip()
            val = row[iF+1:].strip()
            if key in data_keys:
                data[key] = val

            if key == 'CGroup':
                # try grabbing next row and storing everything after ├─ ... / as CLI
                try:
                    _next = rows[i+1].strip()
                    iF = _next.find('├─')
                    if iF > -1:
                        iF = _next.find('/')
                        if iF > -1:
                            data['CLI'] = _next[iF-1:].strip()
                except Exception as ex:
                    pass

            elif key == 'Main PID':
                iF = val.find(' (')
                if iF > -1:
                    val = val[:iF]
                    try:
                        data[key] = int(val)
                    except Exception as ex:
                        pass


            elif key == 'Active':
                active_row = val              
                if active_row.find('active (running)') == 0:
                    active_status = 'active'
                else:
                    find = active_row.find('(')
                    active_status = active_row[:find-1]
                    active_row = val

        if active_row is None:
            return ('-', out, 'Line that contains `Active: `. Not found in output!', data)
        else:
            return (active_status, out, active_row, data)


def disable_site(site):
    (_path_avail, _path_enabled) = get_paths(site)

    if not (Path(_path_enabled)).is_symlink():
        return (False, f"Symlink in sites-enabled does not exist or is not a symlink: {_path_enabled}")

    os.remove(_path_enabled)

    return (True, None)



# ==============================================
# Start General Utilities
# (code snips from qlib.py)
# written using fail fast principles
# ==============================================


def pc(*args):
    if len(args) == 0: return
    if len(args) == 1: print(f"{C_.CHAR_BULLET} {args[0]}"); return
    a = []
    for i, v in enumerate(args): a.append( ( v if i == 0 or isinstance(v, (int, float, complex, str)) else str(v) ) )
    print(f"{C_.CHAR_BULLET} {a[0].format(*a[1:])}")


# No operation lambda/function dropin or breakpoint marker for VSC
def noop(*args, **kwargs):
    if len(args): return args[0]


def get_nginx_ver():
    if C_.NGINX_VER is None:
        p = subprocess.Popen(['nginx', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        s = err.decode('utf-8')
        a = s.split('nginx/')
        C_.NGINX_VER = a[1].strip()
    return C_.NGINX_VER


def get_perl_ver():
    if C_.PERL_VER is None:
        p = subprocess.Popen(['perl', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        s = out.decode('utf-8').strip().split('\n')[0]
        s = s.split(' (v')[1]
        C_.PERL_VER = s.split(')')[0]
    return C_.PERL_VER

def isStr(v, has_chars:str=None):
    if v is None: return False
    if not isinstance(v, str): return False
    if isStr(has_chars):
        for c in has_chars:
            if v.find(c) == -1: return False
    
    return True


def isPrimitive(o, from_str:bool=False, incl_complex:bool=False):
    if from_str:
        assertNotBlank('o (from_str = True)', o)
        c = o if isinstance(o, type) else o.__class__
        if c in C_.TYPES_PRIMITIVE_STR or (incl_complex and c in C_.TYPES_COMPLEX_STR): 
            return True
    else:
        c = o if isinstance(o, type) else o.__class__
        if c in C_.TYPES_PRIMITIVE or (incl_complex and c in C_.TYPES_COMPLEX): 
            return True
    return False

def isBuiltIn(v):
    if v is None: return False
    return (type(v).__name__ == 'builtin_function_or_method')

# strict: ensure first character is non-numeric
def isAlphaNum(s:str, chars:str = None, strict:bool=True) -> bool:
    assertNotBlank('s', s)
    if strict and s[0].isnumeric(): return False
    if not chars is None:
        assertIsStr('chars', chars)
        for c in chars: s = s.replace(c, '')
    return s.isalnum()

def assertIsStr(alias, o):
    assertNotNull(alias, o)
    assert isStr(o),\
        f"Argument {alias} is not an String. Got: {getClassName(o, True)}"
    return o

def assertNotNull(alias, o):
    assert not o is None, "Argument {0} must not be None.".format(alias)
    return o

# Works on str or list(of str)
def assertNotBlank(alias, o, cstr:bool = False):
    if isStr(o):
        s = o
    elif cstr:
        if not isPrimitive(o):
            raise AssertionError("Argument {} is not a primitive (cstr=true). Got: {}".format(alias, getClassName(o)))
        s = str(o)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            if isStr(v):
                assert not v.strip() == '',\
                    "Argument {0} has a item in list that is blank at index {1}. Values are required.".format(alias, i)
            else:
                raise AssertionError("Argument {0} has a item in list that is not a String at index {1}. Got: {2}".format(alias, i, getClassName(v)))
        return o

    else:
        raise AssertionError("Argument {} is not a str. Got: {}".format(alias, getClassName(o)))
        
    assert not o.strip() == '',\
        "Argument {0} must not be a non-blank string.".format(alias)
    return o

def assertIsDef(alias, o):
    assert not o is None, "Argument {0} must be defined. Its (none)".format(alias)
    return o

def getClassName(o):
    if o is None: return None
    return type(o).__name__

def objToDict(o):
    assertIsDef("o", o)
    if isinstance(o, (dict, JSDict)):
        r = copy(o)
    else:
        r = {}
        r.update(o.__dict__)
    return r

# Universal Join - Works on any types and list or tuples. Calls str() for values
def join(l:typing.Union[list, tuple], s: str) -> str:
    return s.join([str(v) for v in l])

def dumpCurExcept(chain:bool=True):
    ety, ev, etr = sys.exc_info()
    s = ''.join(traceback.format_exception(ety, ev, etr, chain=chain))
    iF = s.find('\n')
    return s[iF+1:] if iF > -1 else s

def pre(s, iChars=2, pfx=None):
    if not isinstance(pfx, str) or pfx == '':
        pfx = ' ' * iChars
    iF = s.find('\n')
    if iF == -1:
        return pfx + s
    sb = []
    iFL = 0
    while iF > -1:
        sb.append(pfx + s[iFL:iF])
        iFL = iF + 1
        iF = s.find('\n', iF + 1)
    sb.append('' if iF == len(s) else pfx + s[iFL:])
    return '\n'.join(sb)


# JavaScript like Dictionaries
# dict wrapper for json to make operate like JS
# . usage: Q_.JSDict(<json>)
ILLEGAL_DICT_ATTR = set(dir({}))
__aa=None
def _JSDict__aa(k, s=None):
    return AttributeError('Illegal Attribute: {}'.format(k) if s is None else '{}. Attr: {}'.format(s,k))


# JSDict - Dictionary Wrapper that emulates JavaScript Dicts (Objects)
def _JSDict__check(k):
    if not isinstance(k, str): 
        return (False, "Key is not a String. Type is {}".format(type(k)))
    if k in ILLEGAL_DICT_ATTR:
        return (False, "Key is reserved: {}".format(k))
    return (True, None)
# Note, to have Json Auto Trim Strings being set use: Q_.AUTOTRIM_JSON = True before instantiating
AUTOTRIM_JSON = False

class JSDict(dict):
    def __init__(self, *args, **kwargs):
        l_a = len(args)
        assert l_a < 2, f"Must only have 0 or 1 args. Got: {l_a} args"
        if l_a == 0:
            d = kwargs

        elif l_a == 1:
            assert isBuiltIn(getattr(args[0], 'keys')), \
                "argument must be a dict like object that contains keys() method"
            d = dict(args[0])

        super().__init__(d)
        
        for k in list(d.keys()):
            (ok, msg) = __check(k)
            if not ok: raise __aa(k, msg)

    @staticmethod
    def fromObj(o1, o2):
        assertIsDef("o1", o1)
        d = {}
        d.update(objToDict(o1))
        if not o2 is None:
            d.update(objToDict(o2))
        return JSDict(d)

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            attr_error=__aa(k, "Unknown Attribute")
            raise attr_error

    def __setattr__(self, k, v):
        (ok, msg) = __check(k)
        if not ok: raise __aa(k, msg)
        self[k] = v.strip() if AUTOTRIM_JSON and isinstance(v, str) else v

    def __delattr__(self, k):
        try:
            del self[k]
        except KeyError:
            if not isinstance(k, str): raise __aa(k, 'Attribute must be a String')
            raise __aa(k)

    def __hash__(self):
        return hash(str(self))

    def toJsonStr(self) -> str:
        return json.dumps(self)


    # Makes shallow clone of object
    def clone(self, attr:list=None, ign_attr:list=None, private:bool=True):
        if not attr is None and not ign_attr is None:
            raise AssertionError("Only specify one of attr -or- ign_attr")
        if not attr is None: 
            _a = attr
        elif not ign_attr is None: 
            _a = list(filter(lambda k: not k in ign_attr, self.keys()))
        else:
            _a = self.keys()

        if not private:
            _a = list(filter(lambda k: (attr is None or not k in attr) and not k[:1] == '_', _a))

        r = JSDict({})
        for k in _a: 
            if not k in self: raise KeyError("Key {} not found in self".format(k))
            r[k] = self[k]
        return r

    def __bool__(self): return True

__check=None
# END JSDict

            
class PExec():
    def __init__(self, cmd, fPrint=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, outencoding='utf-8', shell=False, cwd:str=None):
        self._cmd=list(map(lambda c: str(c), cmd))
        self._stdout = stdout
        self._stderr = stderr
        self._fPrint = fPrint
        self._outenc = outencoding
        self._shell = shell

        if cwd and not os.path.isdir(cwd):
            raise AssertionError("cwd parameter passed does not exist or is not accessible: {}".format(dump(cwd, True)))
        self._cwd = cwd

    def __enter__(self):
        p = subprocess.Popen(self._cmd,stdout=self._stdout, stderr=self._stderr, shell=self._shell, cwd=self._cwd)
        sbStdout=[]
        if self._fPrint:
            while True:
                line = p.stdout.readline()
                if not line: 
                    break
                line=line.decode().strip()
                sbStdout.append(line)
                self._fPrint("Popen: {}".format(line))
            stdout='\n'.join(sbStdout)
            stdout_ignore, stderr = p.communicate()
        else:
            stdout, stderr = p.communicate()
            stdout=stdout.decode(self._outenc)

        stderr=stderr.decode(self._outenc)
        

        return JSDict({"out": stdout, "err": stderr, "code": p.returncode})
    def __exit__(self, *args): None
    def __bool__(self): return True


