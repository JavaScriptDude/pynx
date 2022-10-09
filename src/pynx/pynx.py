#########################################
# .: pynx.py :.
# cli tool for managing nginx daemon, sites and associated wsgi services
# Author: Timothy C. Quinn (javascriptdude at protonmail.com)
# Home: tbd
# Licence: MIT

# Note: To run as root in visual studio. Open Python debug console, run % sudo su
#         Now each run in this console will be as root

# TODO:
# [.] Figure out how to get install working via `pip install`.
#     This is non-trivial because of requirement for root
# [.] Move nginx paths to a config file instead of hardcoded defaults
# [.] Publish to github
# [.] Write readme.md
#########################################
import sys
import getpass
from . import util
from .util import pc, noop, C_

assert sys.version_info >= (3, 7, 9), f"Minimum python version supported is 3.7.9. Current version is: {sys.version}"

def print_cli(msg:str = None):
    print("""pynx - python nginx manager
 Server commands (pynx <cmd>):
    status - Show status of nginx daemon
      list - List all available and enabled sites
      test - Verify site configs
     start - Start nginx daemon
      stop - Stop nginx daemon
    reload - Reload nginx daemon
   restart - Restart nginx daemon
 Site commands (pynx <site> <cmd>):
    status - Show status for site
     start - Enables site if not enabled an reload nginx
      stop - Disables site if enabled an reload nginx
    enable - Enables site> if not enabled. Will prompt for reload
   disable - Disables site if enabled. Will prompt for reload
    config - Prints config summary for site
 WSGI commands (pynx <cmd> wsgi:<site>):
    status - Show status for site wsgi
     start - Starts site wsgi if stopped
      stop - Stops site wsgi if started
   restart - Restart site wsgi
 """)

    if not isinstance(msg, str) or msg.strip() == '':
        if C_.NGINX_RELOAD_BROKEN:
            print(f"""nginx note: `systemctl reload nginx` is not recommended on your system because
                of a segfault bug in perl: https://github.com/Perl/perl5/issues/17154
                Use `systemctl restart nginx` instead. (nginx: v{C_.NGINX_VER}, perl: v{C_.PERL_VER})""")

    if not msg is None: print(msg)

    sys.exit(0)


def main(args):
    util.init()
    
    if len(args) == 0 or  args[0] == '-h' or args[0] == '--help': print_cli()

    if getpass.getuser() != 'root': print_cli(f"Must be run as root")

    cmd = site = None

    bNginx = bSite = bWsgi = False
    
    if len(args) == 1:
        cmd = args[0]
        if not cmd in C_.SERVER_CMD: print_cli(f"Invalid command: `{cmd}`")
        bNginx = True

    elif len(args) == 2:
        site = args[0]
        cmd = args[1]
        if site.find('wsgi:') == 0:
            bWsgi = True
            site = site[5:]
            if site.strip() == '': print_cli("Invalid site")
        else:
            bSite = True

        if bWsgi:
            if not cmd in C_.WSGI_CMD:
                print_cli(f"Invalid wsgi command {cmd}")
        else:
            if not cmd in C_.SITE_CMD:
                print_cli(f"Invalid site command {cmd}")
    else:
        print_cli("Invalid number of args passed")


    if bNginx: # server command

        # ================================
        # % pynx status
        # ================================
        if cmd == 'status':
            (status, out, summary, data) = util.get_sytemd_nginx_status()
            if status in ('active', 'inactive'):
                pc(f"nginx status:")
                pc(f"  status: {summary}")
                pc(f"     pid: {data['Main PID']}")
                pc(f"  memory: {data['Memory']}")
                pc(f"   tasks: {data['Tasks']}")
                pc(f"     cli: {data['CLI']}")
                    
            else:
                if out is None:
                    pc(f"{status} - nginx status is not ok because: {summary}")
                else:
                    pc(f"{status} - nginx status is {summary}\n\n {util.pre(out)}")


        # ================================
        # % pynx list
        # ================================
        elif cmd == 'list':

            sites = util.Sites()

            table = util.build_table()
            for site_info in sites.Enabled.values(): 
                util.table_add_ok_row(table, site_info)

            for site_info in sites.Avail.values():
                util.table_add_ok_row(table, site_info)

            for site_info in sites.Bad.values(): 
                util.table_add_bad_row(table, site_info)
            
            pc(f"\n{table.draw()}\n")


        # ================================
        # % pynx test
        # ================================
        elif cmd == 'test':
            nginx = util.Nginx()
            if nginx.ok:
                pc(f"Pass - nginx and site configs ok")

            else:
                pc(f"nginx config issues:")
                for row in nginx.badrows:
                    pc(f"  {row}")

                if not nginx.reason is None:
                    pc(f"  (pynx parsing Issue: {nginx.reason}")

            noop()

        # ================================
        # % pynx start
        # ================================
        elif cmd == 'start':
            (status, out, summary_start, data) = util.get_sytemd_nginx_status()
            if status == 'active':
                pc(f"Server already running ({summary_start})")

            elif status == 'inactive':
                (ok, reason) = util.start_service('nginx')
                if not ok:
                    pc(f"nginx not started because {reason}")

                else:
                    (status, out, summary, data) = util.get_sytemd_nginx_status()
                    if status == 'active':
                        pc(f"done - {summary}")
                    else:
                        pc(f"nginx was not started - {summary}")


        # ================================
        # % pynx stop
        # ================================
        elif cmd == 'stop':
            (status, out, summary_start, data) = util.get_sytemd_nginx_status()
            if status == 'inactive':
                pc(f"Server already inactive ({summary_start})")

            elif status == 'active':
                (ok, reason) = util.stop_service('nginx')

                if not ok:
                    pc(f"nginx not stopped because {reason}")

                else:
                    (status, out, summary, data) = util.get_sytemd_nginx_status()
                    if status == 'inactive':
                        pc(f"done - {summary}")
                    else:
                        pc(f"nginx was not stopped - {summary}")


        # ================================
        # % pynx reload
        # ================================
        elif cmd == 'reload':
            (status, out, summary_start, data) = util.get_sytemd_nginx_status()
            if status == 'inactive':
                pc(f"Server is inactive ({summary_start})")
                pc(f"Please use `pynx start`")

            elif status == 'active':
                (ok, reason) = util.reload_nginx()

                if not ok:
                    pc(f"nginx not reloaded because {reason}")

                else:
                    (status, out, summary_after, data) = util.get_sytemd_nginx_status()
                    if status == 'active':
                        pc(f"done - {summary_after}")
                    else:
                        pc(f"nginx was not relaoded - {summary_after}")


        # ================================
        # % pynx restart
        # ================================
        elif cmd == 'restart':
            (status, out, summary_start, data) = util.get_sytemd_nginx_status()
            if status == 'inactive':
                pc(f"Server is inactive ({summary_start})")
                pc(f"Please use `pynx start`")

            elif status == 'active':
                (ok, reason) = util.restart_service('nginx')

                if not ok:
                    pc(f"nginx not restarted because {reason}")

                else:
                    (status, out, summary_after, data) = util.get_sytemd_nginx_status()
                    if status == 'active':
                        pc(f"done - {summary_after}")
                    else:
                        pc(f"nginx was not restarted - {summary_after}")


    elif bSite: # Site command

        def _site_table(site_info):
            table = util.build_table()
            if site_info.status == util.BAD:
                util.table_add_bad_row(table, site_info)
            else:
                util.table_add_ok_row(table, site_info)

            return table.draw()

        sites=util.Sites()
        (ok, site_info) = util.find_site(site)
        if not ok:
            pc(f"Site not found: {site}")
            return


        # ================================
        # % pynx config <site>
        # ================================
        if cmd == 'config':
            site_cfg = site_info.site_cfg
            if site_cfg is None:
                pc(f"Sorry, config for site '{site}' could not be read")
            else:
                pc(f"Config for site {site}:")
                for line in site_cfg.config_lines:
                    pc(f"  {line}")
            return


        if cmd in ('start', 'stop', 'enable', 'disable') and site_info.status == util.BAD:
            pc(f"command {cmd} cannot be run for site")
            for line in _site_table(site_info).split('\n'): pc(f"  {line}")
            return
            

        # ================================
        # % pynx status <site>
        # ================================
        if cmd == 'status':
            # Maybe more info can be displayed?
            for line in _site_table(site_info).split('\n'): pc(f"  {line}")


        # ================================
        # % pynx start|enable <site>
        # ================================
        elif cmd in ('start', 'enable'):
            if site_info.status == util.ENABLED:
                pc(f"Site is already {util.get_cmd_str(cmd, past=True)}:")
                for line in _site_table(site_info).split('\n'): pc(f"  {line}")
                if cmd == 'start':
                    pc(f"run `pynx reload` if site is not running")
            else:
                assert site_info.status == util.AVAILABLE, f"Unexpected site status: {site_info.status}"
                (ok, reason) = util.enable_site(site)
                if not ok:
                    pc(f"site {site} could not be {util.get_cmd_str(cmd, past=True)} because {reason}")
                else:
                    (ok, site_info_after) = util.find_site(site)
                    assert ok, f"Site not found: {site} after {cmd}"

                    if cmd == 'start':
                        (ok, reason) = util.reload_nginx()
                        if not ok:
                            pc(f"site {site} could not be {util.get_cmd_str(cmd, past=True)} because {reason}")
                            return
                            
                    pc(f"site {site} {util.get_cmd_str(cmd, past=True)}")
                    for line in _site_table(site_info_after).split('\n'): pc(f"  {line}")


        # ================================
        # % pynx stop|disable <site>
        # ================================
        elif cmd in ('stop', 'disable'):
            if site_info.status == util.AVAILABLE:
                pc(f"Site is already {util.get_cmd_str(cmd, past=True)}:")
                for line in _site_table(site_info).split('\n'):pc(f"  {line}")
                if cmd == 'start':
                    pc(f"run `pynx reload` if site is still running")

            else:
                assert site_info.status == util.ENABLED, f"Unexpected site status: {site_info.status}"
                (ok, reason) = util.disable_site(site)
                if not ok:
                    pc(f"site {site} could not be {util.get_cmd_str(cmd, past=True)} because {reason}")
                else:
                    (ok, site_info_after) = util.find_site(site)
                    assert ok, f"Site not found: {site} after {cmd}"

                    if cmd == 'stop':
                        (ok, reason) = util.reload_nginx()
                        if not ok:
                            pc(f"site {site} could not be {util.get_cmd_str(cmd, past=True)} because {reason}")
                            return

                    pc(f"site {site} {util.get_cmd_str(cmd, past=True)}")
                    for line in _site_table(site_info_after).split('\n'): pc(f"  {line}")


        else:
            raise Exception(f"Unexpected site cmd: '{cmd}'")



    elif bWsgi: # WSGI command
        wsgi = site
        if cmd == 'status':
            # Eg, if there is a daemon with site name (eg gnunicorn), then detect and show information
            # Check to see if daemon exists by using `sudo systemctl list-unit-files <site>.service`
            (status, out, summary, data) = util.get_sytemd_wsgi_status(wsgi)
            if status in ('active', 'inactive'):
                pc(f"{status} - ({wsgi} - {summary})")
            else:
                if out is None:
                    pc(f"{status} - WSGI {wsgi} status is not ok because: {summary}")
                else:
                    pc(f"{status} - WSGI {wsgi} status is {summary}\n\n {util.pre(out)}")

        # ================================
        # % pynx wsgi:<site> start|stop|restart
        # ================================
        elif cmd in ('start', 'restart'):
            
            (status, out, summary_start, data) = util.get_sytemd_wsgi_status(wsgi)
            if status == 'active':
                if cmd == 'start':
                    pc(f"WSGI is already active ({wsgi} - {summary_start})")

                else: # restart
                    (ok, reason) = util.restart_service(wsgi)

                    if not ok:
                        pc(f"WSGI {wsgi} not restarted because {reason}")

                    else:
                        (status, out, summary_after, data) = util.get_sytemd_wsgi_status(wsgi)
                        if status == 'active':
                            pc(f"WSGI {util.get_cmd_str(cmd, past=True)} ({wsgi} - {summary_after})")
                        else:
                            pc(f"WSGI was not restarted ({wsgi} - {summary_after})")

            else:
                if cmd == 'restart':
                    pc(f"WSGI is inactive ({wsgi} - {summary_start})")
                    pc(f"Please use `pynx WSGI {wsgi} start`")

                else: # start
                    (ok, reason) = util.start_service(wsgi)
                    if not ok:
                        pc(f"WSGI {wsgi} not started because {reason}")

                    else:
                        (status, out, summary_after, data) = util.get_sytemd_wsgi_status(wsgi)
                        if status == 'active':
                            pc(f"WSGI {util.get_cmd_str(cmd, past=True)} ({wsgi} - {summary_after})")
                        else:
                            pc(f"WSGI {wsgi} was not started ({wsgi} - {summary_after})")



        # ================================
        # % pynx wsgi:<site> stop
        # ================================
        elif cmd == 'stop':
            (status, out, summary_start, data) = util.get_sytemd_wsgi_status(wsgi)
            if status == 'active':
                (ok, reason) = util.stop_service(wsgi)

                if not ok:
                    pc(f"WSGI {wsgi} not stopped because {reason}")

                else:
                    (status, out, summary_after, data) = util.get_sytemd_wsgi_status(wsgi)
                    if status == 'inactive':
                        pc(f"WSGI stopped ({wsgi} - {summary_after})")
                    else:
                        pc(f"WSGI was not stopped - ({wsgi} - {summary_after})")

            elif status == 'inactive':
                pc(f"WSGI already inactive ({wsgi} - {summary_start})")

            else:
                pc(f"WSGI is not active ({wsgi} - {summary_start})")



        else:
            print_cli(f"Invalid wsgi command: {cmd}")


    # main end


# Entry point for tool.poetry.scripts
# WIP
def cli(args=None):
    if not args: args = sys.argv[1:]  
    main(args)
