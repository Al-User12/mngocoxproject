from __future__ import print_function
import cmd
import json
import os
import re
import sqlite3
import subprocess
import sys
import __builtin__
# prep python path for supporting modules
sys.path.append('./libs/')
import dragons

#=================================================
# FRAMEWORK CLASS
#=================================================

class Framework(cmd.Cmd):

    def __init__(self, params):
        cmd.Cmd.__init__(self)
        self.prompt = (params[0])
        self.modulename = params[1]
        self.ruler = '-'
        self.spacer = '  '
        self.nohelp = '%s[!] No help on %%s%s' % (R, N)
        self.do_help.__func__.__doc__ = '''Displays this menu'''
        self.doc_header = 'Commands (type [help|?] <topic>):'
        self.global_options = __builtin__.global_options
        self.keys = __builtin__.keys
        self.workspace = __builtin__.workspace
        self.home = __builtin__.home
        self.rpc_cache = []

    #==================================================
    # CMD OVERRIDE METHODS
    #==================================================

    def default(self, line):
        self.do_shell(line)

    def emptyline(self):
        # disables running of last command when no command is given
        # return flag to tell interpreter to continue
        return 0

    def precmd(self, line):
        if __builtin__.load:
            print('\r', end='')
        if __builtin__.script:
            print('%s' % (line))
        if __builtin__.record:
            recorder = open(__builtin__.record, 'ab')
            recorder.write(('%s\n' % (line)).encode('utf-8'))
            recorder.flush()
            recorder.close()
        if __builtin__.spool:
            __builtin__.spool.write('%s%s\n' % (self.prompt, line))
            __builtin__.spool.flush()
        return line

    def onecmd(self, line):
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if line == 'EOF':
            # reset stdin for raw_input
            sys.stdin = sys.__stdin__
            __builtin__.script = 0
            __builtin__.load = 0
            return 0
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if cmd == '':
            return self.default(line)
        else:
            try:
                func = getattr(self, 'do_' + cmd)
            except AttributeError:
                return self.default(line)
            return func(arg)

    # make help menu more attractive
    def print_topics(self, header, cmds, cmdlen, maxcol):
        if cmds:
            self.stdout.write("%s\n"%str(header))
            if self.ruler:
                self.stdout.write("%s\n"%str(self.ruler * len(header)))
            for cmd in cmds:
                self.stdout.write("%s %s\n" % (cmd.ljust(15), getattr(self, 'do_' + cmd).__doc__))
            self.stdout.write("\n")

    #==================================================
    # SUPPORT METHODS
    #==================================================

    def to_unicode_str(self, obj, encoding='utf-8'):
        # checks if obj is a string and converts if not
        if not isinstance(obj, basestring):
            obj = str(obj)
        obj = self.to_unicode(obj, encoding)
        return obj

    def to_unicode(self, obj, encoding='utf-8'):
        # checks if obj is a unicode string and converts if not
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj

    def is_writeable(self, filename):
        try:
            fp = open(filename, 'ab')
            fp.close()
            return True
        except IOError:
            return False

    #==================================================
    # OUTPUT METHODS
    #==================================================

    def error(self, line):
        '''Formats and presents errors.'''
        if not re.search('[.,;!?]$', line):
            line += '.'
        line = line[:1].upper() + line[1:]
        print('%s[!] %s%s' % (R, self.to_unicode(line), N))

    def output(self, line):
        '''Formats and presents normal output.'''
        print('%s[*]%s %s' % (B, N, self.to_unicode(line)))

    def alert(self, line):
        '''Formats and presents important output.'''
        print('%s[*]%s %s' % (G, N, self.to_unicode(line)))

    def verbose(self, line):
        '''Formats and presents output if in verbose mode.'''
        if self.global_options['verbose']:
            self.output(line)

    def heading(self, line, level=1):
        '''Formats and presents styled banner text'''
        line = self.to_unicode(line)
        print('')
        if level == 0:
            print(self.ruler*len(line))
            print(line.upper())
            print(self.ruler*len(line))
        if level == 1:
            print('%s%s' % (self.spacer, line.title()))
            print('%s%s' % (self.spacer, self.ruler*len(line)))

    def table(self, data, header=[]):
        '''Accepts a list of rows and outputs a table.'''
        tdata = list(data)
        if header:
            tdata.insert(0, header)
        if len(set([len(x) for x in tdata])) > 1:
            raise FrameworkException('Row lengths not consistent.')
        lens = []
        cols = len(tdata[0])
        for i in range(0,cols):
            lens.append(len(max([self.to_unicode_str(x[i]) if x[i] != None else '' for x in tdata], key=len)))
        # build ascii table
        if len(tdata) > 0:
            separator_str = '%s+-%s%%s-+' % (self.spacer, '%s---'*(cols-1))
            separator_sub = tuple(['-'*x for x in lens])
            separator = separator_str % separator_sub
            data_str = '%s| %s%%s |' % (self.spacer, '%s | '*(cols-1))
            # top of ascii table
            print('')
            print(separator)
            # ascii table data
            if header:
                rdata = tdata.pop(0)
                data_sub = tuple([rdata[i].center(lens[i]) for i in range(0,cols)])
                print(data_str % data_sub)
                print(separator)
            for rdata in tdata:
                data_sub = tuple([self.to_unicode_str(rdata[i]).ljust(lens[i]) if rdata[i] != None else ''.ljust(lens[i]) for i in range(0,cols)])
                print(data_str % data_sub)
            # bottom of ascii table
            print(separator)
            print('')

    #==================================================
    # DATABASE METHODS
    #==================================================

    def query(self, query, values=()):
        '''Queries the database and returns the results as a list.'''
        if self.global_options['debug']: self.output(query)
        conn = sqlite3.connect('%s/data.db' % (self.workspace))
        cur = conn.cursor()
        if values:
            if self.global_options['debug']: self.output(repr(values))
            cur.execute(query, values)
        else:
            cur.execute(query)
        # a rowcount of -1 typically refers to a select statement
        if cur.rowcount == -1:
            rows = cur.fetchall()
            results = rows
        # a rowcount of 1 == success and 0 == failure
        else:
            conn.commit()
            results = cur.rowcount
        conn.close()
        return results

    #==================================================
    # OPTIONS METHODS
    #==================================================

    def register_option(self, name, value, reqd, desc):
        self.options.init_option(name=name.lower(), value=value, required=reqd, description=desc)
        # needs to be optimized rather than ran on every register
        self.load_config()

    def validate_options(self):
        for option in self.options:
            # if value type is bool or int, then we know the options is set
            if not type(self.options[option]) in [bool, int]:
                if self.options.required[option].lower() == 'yes' and not self.options[option]:
                    raise FrameworkException('Value required for the \'%s\' option.' % (option))
        return

    def load_config(self):
        config_path = '%s/config.dat' % (self.workspace)
        # don't bother loading if a config file doesn't exist
        if os.path.exists(config_path):
            # retrieve saved config data
            config_file = open(config_path, 'rb')
            try:
                config_data = json.loads(config_file.read())
            except ValueError:
                # file is corrupt, nothing to load, exit gracefully
                pass
            else:
                # set option values
                for key in self.options:
                    try:
                        self.options[key] = config_data[self.modulename][key]
                    except KeyError:
                        # invalid key, contnue to load valid keys
                        continue
            finally:
                config_file.close()

    def save_config(self):
        config_path = '%s/config.dat' % (self.workspace)
        # create a config file if one doesn't exist
        open(config_path, 'ab').close()
        # retrieve saved config data
        config_file = open(config_path, 'rb')
        try:
            config_data = json.loads(config_file.read())
        except ValueError:
            # file is empty or corrupt, nothing to load
            config_data = {}
        config_file.close()
        # overwrite the old config data with option values
        config_data[self.modulename] = dict(self.options)
        for key in config_data[self.modulename].keys():
            if config_data[self.modulename][key] is None:
                del config_data[self.modulename][key]
        # write the new config data to the config file
        config_file = open(config_path, 'wb')
        json.dump(config_data, config_file, indent=4)
        config_file.close()

    #==================================================
    # API KEY METHODS
    #==================================================

    def list_keys(self):
        tdata = []
        for key in sorted(self.keys):
            tdata.append([key, self.keys[key]])
        if tdata:
            self.table(tdata, header=['Name', 'Value'])
        else: self.output('No API keys stored.')

    def save_keys(self):
        key_path = '%s/keys.dat' % (self.home)
        key_file = open(key_path, 'wb')
        json.dump(self.keys, key_file)
        key_file.close()

    def get_key(self, name):
        try:
            return self.keys[name]
        except KeyError:
            raise FrameworkException('API key \'%s\' not found. Add API keys with the \'keys add\' command.' % (name))

    def add_key(self, name, value):
        self.keys[name] = value
        self.save_keys()

    def delete_key(self, name):
        try:
            del self.keys[name]
        except KeyError:
            raise FrameworkException('API key \'%s\' not found.' % (name))
        else:
            self.save_keys()

    #==================================================
    # REQUEST METHODS
    #==================================================

    def request(self, url, method='GET', timeout=None, payload=None, headers=None, cookiejar=None, auth=None, content='', redirect=True):
        request = dragons.Request()
        request.user_agent = self.global_options['user-agent']
        request.debug = self.global_options['debug']
        request.proxy = self.global_options['proxy']
        request.timeout = timeout or self.global_options['timeout']
        request.redirect = redirect
        return request.send(url, method=method, payload=payload, headers=headers, cookiejar=cookiejar, auth=auth, content=content)

    #==================================================
    # SHOW METHODS
    #==================================================

    def get_show_names(self):
        # Any method beginning with "show_" will be parsed
        # and added as a subcommand for the show command.
        prefix = 'show_'
        return [x[len(prefix):] for x in self.get_names() if x.startswith(prefix)]

    def show_modules(self, param):
        # process parameter according to type
        if type(param) is list:
            modules = param
        elif param:
            modules = [x for x in __builtin__.loaded_modules if x.startswith(param)]
            if not modules:
                self.error('Invalid module category.')
                return
        else:
            modules = __builtin__.loaded_modules
        # display the modules
        key_len = len(max(modules, key=len)) + len(self.spacer)
        last_category = ''
        for module in sorted(modules):
            category = module.split('/')[0]
            if category != last_category:
                # print header
                last_category = category
                self.heading(last_category)
            # print module
            print('%s%s' % (self.spacer*2, module))
        print('')

    def show_workspaces(self):
        dirnames = []
        path = '%s/workspaces' % (self.home)
        for name in os.listdir(path):
            if os.path.isdir('%s/%s' % (path, name)):
                dirnames.append([name])
        self.table(dirnames, header=['Workspaces'])

    def show_dashboard(self):
        # display activity table
        self.heading('Activity Summary')
        rows = self.query('SELECT * FROM dashboard ORDER BY 1')
        tdata = []
        for row in rows:
            tdata.append(row)
        if rows:
            self.table(tdata, header=['Module', 'Runs'])
        else:
            print('\n%sThis workspace has no record of activity.' % (self.spacer))
        # display sumary results table
        self.heading('Results Summary')
        tables = [x[0] for x in self.query('SELECT name FROM sqlite_master WHERE type=\'table\'')]
        tdata = []
        for table in tables:
            if not table in ['leaks', 'dashboard']:
                count = self.query('SELECT COUNT(*) FROM "%s"' % (table))[0][0]
                tdata.append([table.title(), count])
        self.table(tdata, header=['Category', 'Quantity'])

    def show_schema(self):
        '''Displays the database schema'''
        tables = [x[0] for x in self.query('SELECT name FROM sqlite_master WHERE type=\'table\'')]
        for table in tables:
            columns = [(x[1],x[2]) for x in self.query('PRAGMA table_info(\'%s\')' % (table))]
            name_len = len(max([x[0] for x in columns], key=len))
            type_len = len(max([x[1] for x in columns], key=len))
            print('')
            print('%s+%s+' % (self.spacer, self.ruler*(name_len+type_len+5)))
            print('%s| %s |' % (self.spacer, table.center(name_len+type_len+3)))
            print('%s+%s+' % (self.spacer, self.ruler*(name_len+type_len+5)))
            for column in columns:
                print('%s| %s | %s |' % (self.spacer, column[0].ljust(name_len), column[1].center(type_len)))
            print('%s+%s+' % (self.spacer, self.ruler*(name_len+type_len+5)))
        print('')

    def show_options(self):
        '''Lists options'''
        spacer = self.spacer
        if self.options:
            pattern = '%s%%s  %%s  %%s  %%s' % (spacer)
            key_len = len(max(self.options, key=len))
            if key_len < 4: key_len = 4
            val_len = len(max([self.to_unicode_str(self.options[x]) for x in self.options], key=len))
            if val_len < 13: val_len = 13
            print('')
            print(pattern % ('Name'.ljust(key_len), 'Current Value'.ljust(val_len), 'Req', 'Description'))
            print(pattern % (self.ruler*key_len, (self.ruler*13).ljust(val_len), self.ruler*3, self.ruler*11))
            for key in sorted(self.options):
                value = self.options[key] if self.options[key] != None else ''
                reqd = self.options.required[key]
                desc = self.options.description[key]
                print(pattern % (key.upper().ljust(key_len), self.to_unicode_str(value).ljust(val_len), reqd.ljust(3), desc))
            print('')
        else:
            print('')
            print('%sNo options available for this module.' % (spacer))
            print('')

    #==================================================
    # COMMAND METHODS
    #==================================================

    def do_exit(self, params):
        '''Exits current prompt level'''
        return True

    # alias for exit
    def do_back(self, params):
        '''Exits current prompt level'''
        return True

    def do_set(self, params):
        '''Sets module options'''
        options = params.split()
        if len(options) < 2:
            self.help_set()
            return
        name = options[0].lower()
        if name in self.options:
            value = ' '.join(options[1:])
            self.options[name] = value
            print('%s => %s' % (name.upper(), value))
            self.save_config()
        else: self.error('Invalid option.')

    def do_unset(self, params):
        '''Unsets module options'''
        self.do_set('%s %s' % (params, 'None'))

    def do_keys(self, params):
        '''Manages framework API keys'''
        if not params:
            self.help_keys()
            return
        params = params.split()
        arg = params.pop(0).lower()
        if arg == 'list':
            self.list_keys()
        elif arg in ['add', 'update']:
            if len(params) == 2:
                self.add_key(params[0], params[1])
                self.output('Key \'%s\' added.' % (params[0]))
            else: print('Usage: keys [add|update] <name> <value>')
        elif arg == 'delete':
            if len(params) == 1:
                try:
                    self.delete_key(params[0])
                except FrameworkException as e:
                    self.error(e.__str__())
                else:
                    self.output('Key \'%s\' deleted.' % (params[0]))
            else: print('Usage: keys delete <name>')
        else:
            self.help_keys()

    def do_query(self, params):
        '''Queries the database'''
        if not params:
            self.help_query()
            return
        conn = sqlite3.connect('%s/data.db' % (self.workspace))
        cur = conn.cursor()
        if self.global_options['debug']: self.output(params)
        try: cur.execute(params)
        except sqlite3.OperationalError as e:
            self.error('Invalid query. %s %s' % (type(e).__name__, e.message))
            return
        if cur.rowcount == -1 and cur.description:
            tdata = cur.fetchall()
            if not tdata:
                self.output('No data returned.')
            else:
                header = tuple([x[0] for x in cur.description])
                self.table(tdata, header=header)
                self.output('%d rows returned' % (len(tdata)-1)) # -1 to account for header row
        else:
            conn.commit()
            self.output('%d rows affected.' % (cur.rowcount))
        conn.close()

    def do_show(self, params):
        '''Shows various framework items'''
        if not params:
            self.help_show()
            return
        params = params.lower().split()
        arg = params[0]
        params = ' '.join(params[1:])
        if arg in self.get_show_names():
            func = getattr(self, 'show_' + arg)
            if arg == 'modules':
                func(params)
            else:
                func()
        elif arg in [x[0] for x in self.query('SELECT name FROM sqlite_master WHERE type=\'table\'')]:
            self.do_query('SELECT * FROM "%s" ORDER BY 1' % (arg))
        else:
            self.help_show()

    def do_search(self, params):
        '''Searches available modules'''
        if not params:
            self.help_search()
            return
        text = params.split()[0]
        self.output('Searching for \'%s\'...' % (text))
        modules = [x for x in __builtin__.loaded_modules if text in x]
        if not modules:
            self.error('No modules found containing \'%s\'.' % (text))
        else:
            self.show_modules(modules)

    def do_record(self, params):
        '''Records commands to a resource file'''
        if not params:
            self.help_record()
            return
        arg = params.lower()
        if arg.split()[0] == 'start':
            if not __builtin__.record:
                if len(arg.split()) > 1:
                    filename = ' '.join(arg.split()[1:])
                    if not self.is_writeable(filename):
                        self.output('Cannot record commands to \'%s\'.' % (filename))
                    else:
                        __builtin__.record = filename
                        self.output('Recording commands to \'%s\'.' % (__builtin__.record))
                else: self.help_record()
            else: self.output('Recording is already started.')
        elif arg == 'stop':
            if __builtin__.record:
                self.output('Recording stopped. Commands saved to \'%s\'.' % (__builtin__.record))
                __builtin__.record = None
            else: self.output('Recording is already stopped.')
        elif arg == 'status':
            status = 'started' if __builtin__.record else 'stopped'
            self.output('Command recording is %s.' % (status))
        else:
            self.help_record()

    def do_spool(self, params):
        '''Spools output to a file'''
        if not params:
            self.help_spool()
            return
        arg = params.lower()
        if arg.split()[0] == 'start':
            if not __builtin__.spool:
                if len(arg.split()) > 1:
                    filename = ' '.join(arg.split()[1:])
                    if not self.is_writeable(filename):
                        self.output('Cannot spool output to \'%s\'.' % (filename))
                    else:
                        __builtin__.spool = open(filename, 'ab')
                        self.output('Spooling output to \'%s\'.' % (__builtin__.spool.name))
                else: self.help_spool()
            else: self.output('Spooling is already started.')
        elif arg == 'stop':
            if __builtin__.spool:
                self.output('Spooling stopped. Output saved to \'%s\'.' % (__builtin__.spool.name))
                __builtin__.spool = None
            else: self.output('Spooling is already stopped.')
        elif arg == 'status':
            status = 'started' if __builtin__.spool else 'stopped'
            self.output('Output spooling is %s.' % (status))
        else:
            self.help_spool()

    def do_shell(self, params):
        '''Executes shell commands'''
        proc = subprocess.Popen(params, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        self.output('Command: %s' % (params))
        stdout = proc.stdout.read()
        stderr = proc.stderr.read()
        if stdout: print('%s%s%s' % (O, stdout, N), end='')
        if stderr: print('%s%s%s' % (R, stderr, N), end='')

    def do_resource(self, params):
        '''Executes commands from a resource file'''
        if not params:
            self.help_resource()
            return
        if os.path.exists(params):
            sys.stdin = open(params)
            __builtin__.script = 1
        else:
            self.error('Script file \'%s\' not found.' % (params))

    def do_load(self, params):
        '''Loads selected module'''
        if not params:
            self.help_load()
            return
        # finds any modules that contain params
        modules = [params] if params in __builtin__.loaded_modules else [x for x in __builtin__.loaded_modules if params in x]
        # notify the user if none or multiple modules are found
        if len(modules) != 1:
            if not modules:
                self.error('Invalid module name.')
            else:
                self.output('Multiple modules match \'%s\'.' % params)
                self.show_modules(modules)
            return
        import StringIO
        # compensation for stdin being used for scripting and loading
        if __builtin__.script:
            end_string = sys.stdin.read()
        else:
            end_string = 'EOF'
            __builtin__.load = 1
        sys.stdin = StringIO.StringIO('load %s\n%s' % (modules[0], end_string))
        return True
    do_use = do_load

    #==================================================
    # HELP METHODS
    #==================================================

    def help_keys(self):
        print('Usage: keys [list|add|delete|update]')

    def help_load(self):
        print('Usage: [load|use] <module>')
    help_use = help_load

    def help_record(self):
        print('Usage: record [start <filename>|stop|status]')

    def help_spool(self):
        print('Usage: spool [start <filename>|stop|status]')

    def help_resource(self):
        print('Usage: resource <filename>')

    def help_query(self):
        print('Usage: query <sql>')
        print('')
        print('SQL Examples:')
        print('%s%s' % (self.spacer, 'SELECT columns|* FROM table_name'))
        print('%s%s' % (self.spacer, 'SELECT columns|* FROM table_name WHERE some_column=some_value'))
        print('%s%s' % (self.spacer, 'DELETE FROM table_name WHERE some_column=some_value'))
        print('%s%s' % (self.spacer, 'INSERT INTO table_name (column1, column2,...) VALUES (value1, value2,...)'))
        print('%s%s' % (self.spacer, 'UPDATE table_name SET column1=value1, column2=value2,... WHERE some_column=some_value'))

    def help_search(self):
        print('Usage: search <string>')

    def help_set(self):
        print('Usage: set <option> <value>')
        self.show_options()

    def help_unset(self):
        print('Usage: unset <option>')
        self.show_options()

    def help_shell(self):
        print('Usage: [shell|!] <command>')
        print('...or just type a command at the prompt.')

    def help_show(self):
        options = sorted(self.get_show_names() + ['<table>'])
        print('Usage: show [%s]' % ('|'.join(options)))

    #==================================================
    # COMPLETE METHODS
    #==================================================

    def complete_keys(self, text, line, *ignored):
        args = line.split()
        options = ['list', 'add', 'delete', 'update']
        if len(args) > 1:
            if args[1].lower() in options[2:]:
                return [x for x in self.keys.keys() if x.startswith(text)]
            if args[1].lower() in options[:2]:
                return
        return [x for x in options if x.startswith(text)]

    def complete_load(self, text, *ignored):
        return [x for x in __builtin__.loaded_modules if x.startswith(text)]
    complete_use = complete_load

    def complete_record(self, text, *ignored):
        return [x for x in ['start', 'stop', 'status'] if x.startswith(text)]
    complete_spool = complete_record

    def complete_set(self, text, *ignored):
        return [x.upper() for x in self.options if x.upper().startswith(text.upper())]
    complete_unset = complete_set

    def complete_show(self, text, line, *ignored):
        args = line.split()
        if len(args) > 1 and args[1].lower() == 'modules':
            if len(args) > 2: return [x for x in __builtin__.loaded_modules if x.startswith(args[2])]
            else: return [x for x in __builtin__.loaded_modules]
        tables = [x[0] for x in self.query('SELECT name FROM sqlite_master WHERE type=\'table\'')]
        options = set(self.get_show_names() + tables)
        return [x for x in options if x.startswith(text)]

#=================================================
# SUPPORT CLASSES
#=================================================

class FrameworkException(Exception):
    pass

class Options(dict):

    def __init__(self, *args, **kwargs):
        self.required = {}
        self.description = {}
        
        super(Options, self).__init__(*args, **kwargs)
           
    def __setitem__(self, name, value):
        super(Options, self).__setitem__(name, self._autoconvert(value))
           
    def __delitem__(self, name):
        super(Options, self).__delitem__(name)
        if name in self.required:
            del self.required[name]
        if name in self.description:
            del self.description[name]
        
    def _boolify(self, value):
        # designed to throw an exception if value is not a string representation of a boolean
        return {'true':True, 'false':False}[value.lower()]

    def _autoconvert(self, value):
        if value in (None, True, False):
            return value
        elif (isinstance(value, basestring)) and value.lower() in ('none', "''", '""'):
            return None
        orig = value
        for fn in (self._boolify, int, float):
            try:
                value = fn(value)
                break
            except ValueError: pass
            except KeyError: pass
            except AttributeError: pass
        if type(value) is int and '.' in str(orig):
            return float(orig)
        return value
        
    def init_option(self, name, value=None, required=False, description=''):
        self[name] = value
        self.required[name] = required
        self.description[name] = description

    def serialize(self):
        data = {}
        for key in self:
            data[key] = self[key]
        return data
