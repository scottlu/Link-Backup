#!/usr/bin/python
"""
Copyright (c) 2006 Joe Beda, Scott Ludwig
http://www.eightypercent.net
http://www.scottlu.com

This is a simple web based viewer of the backups created by link-backup:

http://www.scottlu.com/Content/Link-Backup.html

To configure:

1. This script expects lb.py to be in /usr/local/bin. To change this
   assumption, search for /usr/local/bin in this script and change
   as appropriate.

2. Search for BACKUP_DIRECTORY in this script for instructions on configuring
   one or more backup directories to view.

3. Put this script in your cgi-bin directory. This may require root access.
   The cgi-bin location differs from system to system. On Debian the default
   cgi-bin directory is /usr/lib/cgi-bin.

4. Make this script executable by issuing this command from the command line:

   chmod +x viewlb.cgi

5. To access this script in the default cgi-bin directory from a web browser,
   use this url: http://yourserver/cgi-bin/viewlb.cgi

Note: This script has not been hardened against malicious users. Don't make
      this script accessible from the public internet.

History:

v 0.1 06/17/2006
  - initial release

License:

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re
import os
import cgi
import cgitb; cgitb.enable()
import sys
sys.path.append('/usr/local/bin')
import lb
import stat
import time
import math
import urllib

def abbr_number(n,k=1000):
    """Take a number and abbreviate it using psuedo SI units (31M, 27G, etc.)
    Stolen from http://mail.python.org/pipermail/python-list/2001-July/057120.html"""
    if n==0:
        return '0'
    nk, rk = divmod(math.log(abs(n)), math.log(k))
    nkr = max(-9, min(int(nk), 9))
    suffix = 'kyzafpnum kMGTPEZYk'[nkr+9] + (abs(nkr)==9)*("^%d" % (nk,) )
    sr = ("%1.1f" % (math.exp(rk),))
    adjlen = len(sr) - 2*(sr[-1]=='0' or len(sr)>3)
    return '-'*(n<0) + sr[0:adjlen] + suffix

class Page:
    def __init__(self, params, dirs):
        self.out_params = {}
        self.in_params = params
        self.manager = None
        self.dirs = dirs
        self.page_vars = {}

    def render_page(self):
	# If not back dirs, tell the user what to do
	if len(dirs) == 1 and dirs[0] == 'replaceme':
	    self.page_vars['page_name'] = "Link-Backup Backup Viewer"
	    self.print_header()
	    self.out(__doc__)
	    self.print_footer()
	    return
        
        # First figure out the directory
        params = self.in_params
        if not params.has_key('dir'):
            self.show_dirs()
            return

        dir_index = int(params['dir'])
        if dir_index < 0 or dir_index >= len(dirs):
            self.show_dirs(dirs)
            return

        self.out_params['dir'] = dir_index

        self.manager = lb.Manager(dirs[dir_index])

        if not params.has_key('view'):
            self.show_backups()
            return

        view_functions = {
            'month_detail': self.show_month,
            'catalog' : self.show_catalog,
            'catalog_month' : self.show_catalog_month,
            'catalog_new' : self.show_catalog_new,
            'catalog_copy' : self.show_catalog_copy,
            'catalog_file' : self.show_catalog_file,
            'backup_new' : self.show_backup_new,
            'backup_copy' : self.show_backup_copy,
            'backup_link' : self.show_backup_link,
            'backup_tree' : self.show_backup_tree,
	    'scaled_image' : self.show_scaled_image,
	    'scaled_catalog_image' : self.show_scaled_catalog_image,
            'file' : self.show_file,
            }

        #print params['view']
        func = view_functions.get(params['view'])
        if func:
            func()
        else:
            self.show_backups()        

    def make_link(self, **params):
        params.update(self.out_params)
        # allow parameters to be cleared by setting to None
        params = dict([(k,v) for (k,v) in params.items() if v != None]) 
        return "viewlb.cgi?%s" % urllib.urlencode(params)

    def print_header(self):
        self.out("Content-type: text/html\n\n")
        self.out("<HTML>")
        self.out("<HEAD><TITLE>%(page_name)s</TITLE></HEAD>")
        self.out("<BODY><H1>%(page_name)s</H1><PRE>")

    def print_footer(self):
        self.out("</PRE></HTML>")

    def out(self, template, **extra_vars):
        extra_vars.update(self.page_vars);
        sys.stdout.write(template % extra_vars)

    def show_dirs(self):
        self.page_vars['page_name'] = "Backup Sets"
        self.print_header()
        for (i, dir) in enumerate(self.dirs):
            self.out('<a href="%(link)s">%(dir)s</a>\n',
                     link=self.make_link(dir=i),
                     dir=dir)
        self.print_footer()

    def show_backups(self):
        backups = self.manager.get_backups()

        self.page_vars['page_name'] = "Backups"
        self.print_header()

        self.out('<a href="%(link)s">Catalog</a>\n\n',
                 link=self.make_link(view='catalog'))
        
        dated = self.get_month_counts(backups)
        months = dated.keys()
        months.sort()
        if len(months) > 1:
            self.output_months_summary(backups, months[-1])
            self.out('\n')

        self.out('<b>Current month: %s</b>\n' % self.format_date(months[-1]))
        self.output_month_detail(backups, months[-1])
        self.print_footer()

    def format_date(self, date):
        return "%s/%s" % (date[4:], date[:4])

    def output_months_summary(self, backups, monthstop):
        dated = self.get_month_counts(backups)
        months = dated.keys()
        months.sort()
        for month in months:
            if month == monthstop:
                break
            self.out('<a href="%(link)s">%(date)s</a> %(backup_count)s backups\n',
                     link=self.make_link(arg=month, view='month_detail'),
                     date=self.format_date(month),
                     backup_count=dated[month])
            
    def output_month_detail(self, backups, month):
        for backup in backups:
            tbackup = backup.get_date()
            if month == '%04d%02d' % (tbackup[0], tbackup[1]):
                self.out_params['backup'] = backup.get_dirname()
                
                self.out('<a href="%(link)s">%(text)s</a>:',
                         link=self.make_link(view='backup_tree'),
                         text=backup.get_dirname())
                parse = backup.parse_log()

                new = 0
                copy = 0
                link = 0
                for item in backup.parse_log():
                    if item[0] == 'copy':
                        copy += 1
                    elif item[0] == 'new':
                        new += 1
                    elif item[0] == 'link':
                        link += 1

                if new != 0:
                    self.output_justified_link(9, "%d new" % new,
                                               self.make_link(view='backup_new'))
                else:
                    self.out("%(text)9s", text='0 new')

                if copy != 0:
                    self.output_justified_link(12, "%d copied" % copy,
                                               self.make_link(view='backup_copy'))
                else:
                    self.out("%(text)12s", text='0 copied')

                if link != 0:
                    self.output_justified_link(12, "%d linked" % link,
                                               self.make_link(view='backup_link'))
                else:
                    self.out("%(text)12s", text='0 linked')

                self.out("\n")


    def output_justified_link(self, length, text, link):
        prefix = length - len(text)
        if prefix < 0: prefix = 0
        self.out('%(prefix)s<a href="%(link)s">%(text)s</a>',
                 prefix=' '*prefix,
                 link=link,
                 text=text)

    def get_month_counts(self, backups):
        dated = {}
        for backup in backups:
            t = backup.get_date()
            month = '%04d%02d' % (t[0], t[1]) 
            if not dated.has_key(month):
                dated[month] = 1
            else:
                dated[month] = dated[month] + 1
        return dated
    
    def show_month(self):
        backups = self.manager.get_backups()

        month = self.in_params['arg']

        self.page_vars['page_name'] = "Backups for %s" % self.format_date(month)
        self.print_header()
        
        self.output_month_detail(backups, month)
        self.print_footer()

    def show_backup_new(self):
        self.show_backup('new')

    def show_backup_copy(self):
        self.show_backup('copy')

    def show_backup_link(self):
        self.show_backup('link')

    def decode_backup(self):
        if self.in_params.has_key('backup'):
            backup = self.manager.get_backup(params['backup'])
        else:
            backup = self.manager.get_backups()[-1]
        return backup

    def translate_view_arg(self, view, filename):
        type = filename[-3:]
        if type != 'jpg' and type != 'JPG':
	    return view
	agent = os.environ.get("HTTP_USER_AGENT", "N/A")
	if agent.find('AppleWebKit') == -1:
	    return view
	if view == 'file':
	    return 'scaled_image'
	if view == 'catalog_file':
	    return 'scaled_catalog_image'
	return view

    def show_backup(self, filter):
        backup = self.decode_backup()
        self.out_params['backup'] = backup.get_dirname()
                
        self.page_vars['page_name'] = "Backup for %s" % backup.get_dirname()
        self.print_header()

        self.out("<B>Type: %(type)s</B>\n\n", type=filter)
        
        size = 0
        parse = backup.parse_log()
        for item in parse:
            if item[0] != filter:
                continue
            file = item[1]

            s = os.stat(os.path.join(backup.get_treepath(), file))
	    view = self.translate_view_arg('file', file)

            self.out('%(size)5s  <a href="%(link)s">%(text)s</a>\n',
                     link=self.make_link(view=view, file=file),
                     text=cgi.escape(file),
                     size=abbr_number(s.st_size))
            
            size += s.st_size

        self.out("\nTotal Size: %(size)s", size=abbr_number(size))
        self.print_footer()

    def show_backup_tree(self):
        backup = self.decode_backup()
        self.out_params['backup'] = backup.get_dirname()

        path = self.in_params.get('path', '')

        self.page_vars['page_name'] = "Backup tree for %s" % backup.get_dirname()
        self.print_header()

        fullpath = os.path.join(backup.get_treepath(), path)
        size = 0
        for item in os.listdir(fullpath):
            file = os.path.join(path, item)
            s = os.stat(os.path.join(fullpath, item))
            if stat.S_ISDIR(s.st_mode):
                self.out('D %(size)5s  <a href="%(link)s">%(text)s</a>\n',
                         size=' ',
                         link=self.make_link(view='backup_tree', path=file),
                         text=cgi.escape(file))
            else:
		view = self.translate_view_arg('file', file)
                self.out('F %(size)5s  <a href="%(link)s">%(text)s</a>\n',
                         size=abbr_number(s.st_size),
                         link=self.make_link(view=view, file=file),
                         text=cgi.escape(file))
        self.print_footer()

    def show_scaled_image(self):
	backup = self.decode_backup()
	path = self.in_params.get('file', '')
	filename = os.path.join(backup.get_treepath(), path)
	self.show_scaled_image_impl(filename)

    def show_scaled_image_impl(self, filename):
	link = self.make_link(view='file', file=filename)
	self.page_vars['page_name'] = ""
	self.print_header()
	self.out('<IMG SRC="%(link)s" height="600">', link=link)
	self.print_footer()

    def show_file(self):
        backup = self.decode_backup()
        path = self.in_params.get('file', '')
        filename = os.path.join(backup.get_treepath(), path)
        self.show_file_impl(filename)

    def show_file_impl(self, filename):
        type = self.in_params.get('type', filename[-3:])

        if type == 'jpg' or type == 'JPG':
            self.out('Content-Type: image/jpeg\n\n')
        elif type == 'avi' or type == 'AVI':
            self.out('Content-Type: video/x-msvideo\n\n')
        elif type == 'mp3' or type == 'MP3':
            self.out('Content-Type: audio/x-mp3\n\n')
        else:
            self.out('Content-Type: text/plain\n\n')
        sys.stdout.flush()
        file = open(filename)
        while True:
            bytes = file.read(1024 * 1024)
            if len(bytes) == 0:
                break
            sys.stdout.write(bytes)
        sys.stdout.flush()
        file.close()

    def show_catalog(self):
        catalog = self.manager.catalog
        self.page_vars['page_name'] = "Catalogs"

        self.print_header()

        logfiles = catalog.get_logfiles()
        dated = self.get_catalog_month_counts(logfiles)
        months = dated.keys()
        months.sort()
        if len(months) > 1:
            self.output_catalog_months_summary(logfiles, months[-1])
            self.out('\n')

        self.out('<b>Current month: %s</b>\n' % self.format_date(months[-1]))
        self.output_catalog_month_detail(catalog, logfiles, months[-1])               

        self.print_footer()
        
    def get_catalog_month_counts(self, logfiles):
        dated = {}
        for t, logfile in logfiles:
            month = '%04d%02d' % (t[0], t[1]) 
            if not dated.has_key(month):
                dated[month] = 1
            else:
                dated[month] = dated[month] + 1
        return dated

    def output_catalog_months_summary(self, logfiles, monthstop):
        dated = self.get_catalog_month_counts(logfiles)
        months = dated.keys()
        months.sort()
        for month in months:
            if month == monthstop:
                break
            self.out('<a href="%(link)s">%(date)s</a> %(count)s updates\n',
                     link=self.make_link(arg=month, view='catalog_month'),
                     date=self.format_date(month),
                     count=dated[month])

    def output_catalog_month_detail(self, catalog, logfiles, month):
        for tbackup, logfile in catalog.get_logfiles():
            if month == '%04d%02d' % (tbackup[0], tbackup[1]):
                new = 0
                copy = 0
                session = catalog.parse_log(logfile)
                if len(session) == 0:
                    continue
                
                for item in session:
                    if item[0] == 'copy':
                        copy += 1
                    elif item[0] == 'new':
                        new += 1

                datestr = time.strftime('%Y.%m.%d-%H.%M.%S', tbackup)
                self.out_params['arg'] = datestr

                self.out('%(date)s: ', date=datestr)
                
                if new != 0:
                    self.output_justified_link(9, "%d new" % new,
                                               self.make_link(view='catalog_new'))
                else:
                    self.out("%(text)9s", text='0 new')

                if copy != 0:
                    self.output_justified_link(12, "%d copied" % copy,
                                               self.make_link(view='catalog_copy'))
                else:
                    self.out("%(text)12s", text='0 copied')

                self.out('\n')
                
    def show_catalog_month(self):
        catalog = self.manager.catalog

        month = self.in_params['arg']

        self.page_vars['page_name'] = "Catalog for %s" % self.format_date(month)
        self.print_header()
        
        self.output_catalog_month_detail(catalog, catalog.get_logfiles(), month)
        self.print_footer()

    def show_catalog_new(self):
        self.show_catalog_session('new')

    def show_catalog_copy(self):
        self.show_catalog_session('copy')

    def show_catalog_session(self, filter):
        catalog = self.manager.catalog
        datestr = self.in_params['arg']
        
        self.page_vars['page_name'] = "Catalog session for %s" % datestr
        self.print_header()

        self.out("<B>Type: %(type)s</B>\n\n", type=filter)

        size = 0
        for tbackup, logfile in catalog.get_logfiles():
            if datestr != time.strftime('%Y.%m.%d-%H.%M.%S', tbackup):
                continue
            for line in catalog.parse_log(logfile):
                if line[0] != filter:
                    continue
                catalog_file = line[2]
                for_file = line[3]
                type = for_file[-3:]

                s = os.stat(os.path.join(self.manager.get_path(), '.catalog', catalog_file))
		view = self.translate_view_arg('catalog_file', type)
                self.out('%(size)5s  <a href="%(link)s">%(text)s</a>\n',
                         link=self.make_link(view=view, file=catalog_file, type=type),
                         text=cgi.escape(for_file),
                         size=abbr_number(s.st_size))
            
                size += s.st_size
                
        self.out("\nTotal Size: %(size)s", size=abbr_number(size))
        self.print_footer()

    def show_catalog_file(self):
        filename = os.path.join(self.manager.get_path(), '.catalog', self.in_params['file'])
        self.show_file_impl(filename)

    def show_scaled_catalog_image(self):
        filename = os.path.join(self.manager.get_path(), '.catalog', self.in_params['file'])
        self.show_scaled_image_impl(filename)

# Main

if __name__ == '__main__':
    params = dict([(key, cgi.FieldStorage()[key].value) for key in cgi.FieldStorage()])

    # BACKUP_DIRECTORY
    # Enter one or more backup directories below, for example:
    # dirs = ['/mnt/backup1', '/mnt/backup2']

    dirs = ['replaceme']

    page = Page(params, dirs)
    page.render_page()
