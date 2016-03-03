#!/usr/bin/env python
"""
Fetch Web of Science Citation profile by driving Chrome Browser.

Results are processed using LaTeX and BibTeX.

Call search function with the following inputs:
    Web of Science query (e.g. AU=Last,F* for an author search)
    name of the PDF file to be generated
    new (boolean) - force new databse fetch, or use old data if exists
    full (boolean) - list all citing papers or just the counts for each paper

BibTex data might not be available for some papers. These will be listed at the
end of the PDF file.
"""

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select
from time import sleep
import os

import bibtexparser


# TODO
#   add argparse
#   separate tex template

class WebOfScience(object):

    """ Walk through Web of Science website. """

    def __init__(self):
        """ Initialize Chrome driver. """
        path = os.getcwd()
        chrome_options = webdriver.ChromeOptions()
        prefs = {
            "download": {"default_directory": path,
                         "directory_upgrade": True,
                         "extensions_to_open": ""},
            "switches": ["-silent", "--disable-logging"],
            "chromeOptions": {"args": ["-silent", "--disable-logging"]}
        }
        chrome_options.add_experimental_option("prefs", prefs)
        from sys import platform
        self.platform = platform
        try:
            driver = webdriver.Chrome(chrome_options=chrome_options)
        except:
            driver = webdriver.Chrome(executable_path=path+'/chromedriver',
                                      chrome_options=chrome_options)
        driver.implicitly_wait(5)
        self.driver = driver
        self.results = {
            'citing': set(),
            'papers': bibtexparser.loads(""),
            'citingbib': bibtexparser.loads(""),
            'errors': [],
        }

    def search(self, query):
        """ Execute main search. """
        self.results['query'] = query
        driver = self.driver
        driver.get("http://apps.webofknowledge.com")

        # activate Advanced Search
        driver.find_element_by_class_name('icon-dd-active-block-search').click()
        driver.find_element_by_xpath("//a[@title='Advanced Search']").click()

        # execute search and open results
        driver.find_element_by_id('value(input1)').send_keys(query)
        driver.find_element_by_id('searchButton').click()
        driver.find_element_by_xpath("//div[@id='set_1_div']/a").click()
        self.main = driver.window_handles[0]

    def open_in_tab(self, link):
        """ Open link in new tab and focus on that tab. """
        old = set(self.driver.window_handles)
        CTRL = Keys.COMMAND if "darwin" in self.platform else Keys.CONTROL
        ActionChains(self.driver).move_to_element(link) \
            .key_down(CTRL).key_down(Keys.SHIFT).click() \
            .key_up(CTRL).key_up(Keys.SHIFT).perform()
        sleep(0.5)
        # find new tab
        new = set(self.driver.window_handles)
        new.difference_update(old)
        self.driver.switch_to_window(new.pop())

    def report(self):
        """ Get report data and citing papers. """
        driver = self.driver
        el = driver.find_element_by_xpath("//a[@alt='View Citation Report']")
        self.open_in_tab(el)
        self.results['number'] = driver.find_element_by_id('RESULTS_FOUND').text
        self.results['citations'] = \
            driver.find_element_by_id('GRAND_TOTAL_TC').text
        self.results['citationsnoself'] = \
            driver.find_element_by_id('TOTAL_TC_NO_SC').text
        self.results['h-index'] = driver.find_element_by_id('H_INDEX').text
        driver.find_element_by_id('GRAND_TOTAL_TC3').click()

        # get list of citing papers as txt, then scrape for UT WOS:numbers
        citing = driver.find_element_by_id('hitCount.top').text
        select = Select(driver.find_element_by_name('saveToMenu'))
        select.select_by_value("other")
        driver.find_element_by_name('value(record_select_type)').click()
        driver.find_element_by_name('markFrom').send_keys('1')
        driver.find_element_by_name('markTo').send_keys(citing)
        select = Select(driver.find_element_by_id('saveOptions'))
        select.select_by_value("fieldtagged")
        sleep(0.5)
        driver.find_element_by_xpath(
            "//span[@class='quickoutput-action']/input[@title='Send']").click()
        sleep(5)  # wait for download to finish
        papers = set()
        with open('savedrecs.txt', 'r') as f:
            for line in f.readlines():
                if 'UT WOS:' in line:
                    papers.add(line[7:-1])
        self.results['citing'] = papers
        os.unlink('savedrecs.txt')
        driver.close()
        driver.switch_to_window(self.main)

    def papers(self):
        """ Fetch data for all papers. """
        # need to resort to get correct order!
        select = Select(self.driver.find_element_by_id('selectSortBy_.top'))
        select.select_by_index(1)
        select = Select(self.driver.find_element_by_id('selectSortBy_.top'))
        select.select_by_index(0)
        while True:
            sleep(1)
            papers = self.driver.find_elements_by_xpath(
                "//span[@id='records_chunks']//a[@class='smallV110']")
            for p in papers:
                text = p.text
                try:
                    self.paper(p)
                except:
                    self.driver.close()
                    self.driver.switch_to_window(self.main)
                    print 'Error: Could not fetch publication: ', text
                    self.results['errors'].append(text)
                    try:
                        os.unlink('saverecs.txt')
                    except:
                        pass
                    try:
                        os.unlink('saverecs.bib')
                    except:
                        pass

            try:
                self.driver.find_element_by_xpath(
                    "//a[@title='Next Page']").click()
            except:
                break

    def cleanup_bibtex(self, entry):
        """ Make a good looking bibtex entry. """
        entry['ID'] = entry['ID'][4:]
        try:
            entry['title'] = '{' + entry['title'] + '}'
            entry['journal'] = entry['journal-iso']
        except:
            pass
        good_keys = {'author', 'title', 'journal', 'number', 'volume', 'pages',
                     'year', 'ID', 'ENTRYTYPE', 'editor', 'booktitle', 'series',
                     'doi'}
        good_keys.intersection_update(entry.keys())
        entry = {k: entry[k] for k in good_keys}
        return entry

    def paper(self, link):
        """ Fetch data for a single paper. """
        self.open_in_tab(link)
        # get bibtex
        select = Select(self.driver.find_element_by_name('saveToMenu'))
        select.select_by_value("other")
        select = Select(self.driver.find_element_by_name('fields_selection'))
        select.select_by_index(2)
        select = Select(self.driver.find_element_by_id('saveOptions'))
        select.select_by_value("bibtex")
        sleep(0.5)
        self.driver.find_element_by_xpath(
            "//span[@class='quickoutput-action']/input[@title='Send']").click()
        sleep(3)
        with open('savedrecs.bib') as f:
            bibtex = f.read()
        os.unlink('savedrecs.bib')
        paper = bibtexparser.loads(bibtex)
        entry = self.cleanup_bibtex(paper.entries[0])
        self.driver.find_element_by_class_name('quickoutput-cancel-action') \
            .click()
        # add impact factors
        self.driver.find_element_by_link_text('View Journal Information') \
            .click()
        IFs = self.driver.find_elements_by_xpath(
            "//table[@class='Impact_Factor_table']//td")
        IFtypes = self.driver.find_elements_by_xpath(
            "//table[@class='Impact_Factor_table']//th")
        for t, i in zip(IFtypes, IFs):
            entry['impact' + t.text.replace(' ', '')] = i.text
        # add citing papers
        entry['cited'] = '0'
        entry['citednoself'] = '0'
        self.driver.find_element_by_xpath(
            "//a[@title='Hide journal information']").click()
        sleep(1)
        try:
            assert int(self.driver.find_element_by_xpath(
                "//div[@class='block-text-content']//"
                "span[@class='TCcountFR']").text)
            self.driver.find_element_by_xpath(
                "//div[@class='block-text-content']//a//"
                "span[@class='TCcountFR']/..").click()
            # get bibtex file with citing papers
            citing = self.driver.find_element_by_id('hitCount.top').text
            select = Select(self.driver.find_element_by_name('saveToMenu'))
            select.select_by_value("other")
            self.driver.find_element_by_name('value(record_select_type)') \
                .click()
            self.driver.find_element_by_name('markFrom').send_keys('1')
            self.driver.find_element_by_name('markTo').send_keys(citing)
            select = Select(
                self.driver.find_element_by_name('fields_selection'))
            select.select_by_index(2)
            select = Select(self.driver.find_element_by_id('saveOptions'))
            select.select_by_value("bibtex")
            sleep(0.5)
            self.driver.find_element_by_xpath(
                "//span[@class='quickoutput-action']"
                "/input[@title='Send']").click()
            sleep(3)
            with open('savedrecs.bib') as f:
                bibtex = f.read()
            os.unlink('savedrecs.bib')
            bibtex = bibtexparser.loads(bibtex)
            bibtex.entries = [self.cleanup_bibtex(e) for e in bibtex.entries]
            entry['cited'] = str(len(bibtex.entries))
            entry['citing'] = ','.join([e['ID'] for e in bibtex.entries])
            noself = [e['ID'] for e in bibtex.entries
                      if e['ID'] in self.results['citing']]
            entry['citednoself'] = str(len(noself))
            self.results['citingbib'].entries.extend(bibtex.entries)
        except:
            # no citations
            pass
        self.results['papers'].entries.append(entry)
        self.driver.close()
        self.driver.switch_to_window(self.main)

    def finish(self):
        """ Cleanup data and close browser driver. """
        unique = {e['ID']: e for e in self.results['citingbib'].entries}
        self.results['citingbib'].entries = unique.values()
        self.driver.quit()

    def latex(self, name='results', **options):
        """ Generate file with results. """
        from bibtex import BibTex
        bib = BibTex(authorStyle='textbf', titleStyle='textit')
        bib2 = BibTex(genBibitems=True, IncludeDOIURL='Exclude')
        parsed = bibtexparser.loads("")
        f = open(name + '.tex', 'w')
        # totals
        print >>f, r"""
\documentclass[12pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage[bookmarks=false,unicode,colorlinks,urlcolor=red,citecolor=red,
linkcolor=blue]{hyperref}
\renewcommand{\refname}{\normalfont\selectfont\normalsize Citing papers:
\vspace{-0.3cm}}
\newcommand{\doi}[1]{

 \href{http://dx.doi.org/#1}{doi:#1}}
\begin{document}

\section{Query}
\verb|%s|
\section{Citation counts}
\begin{itemize}
\item Number of papers: %s
\item Total number of citations: %s
\item Total number of citations without self-citations: %s
\item h-index: %s
\end{itemize}
\section{Papers}
\begin{enumerate}""" % (self.results['query'], self.results['number'],
                        self.results['citations'],
                        self.results['citationsnoself'],
                        self.results['h-index'])
        # each paper
        if not self.results['papers'].entries:
            print >>f, r'\item Fetching failed for all papers.'
        for paper in self.results['papers'].entries:
            parsed.entries = [paper]
            data = bib.run(bibtexparser.dumps(parsed))
            print >>f, r'\item ' + data
            print >>f, '\n Journal impact factors: ',
            for k, v in paper.items():
                if 'impact' in k:
                    print >>f, k.replace('impact', '') + ': ' + str(v) + '.',
            print >>f, ''
            print >>f, '\n Cited by {} papers. Excluding self-citations: {}\n' \
                .format(paper['cited'], paper['citednoself'])
            if int(paper['cited']) and \
                    ('full' not in options or options['full']):
                parsed.entries = [e for e in self.results['citingbib'].entries
                                  if e['ID'] in paper['citing']]
                data = bib2.run(bibtexparser.dumps(parsed))
                print >>f, r'\vspace{-0.5cm}\begin{thebibliography}{99}'
                print >>f, r'\setlength{\itemsep}{0pt}'
                print >>f, data
                print >>f, r'\end{thebibliography}'
        # any errors
        if self.results['errors']:
            print >>f, r'\end{enumerate}'
            print >>f, r"\section{Couldn't fetch papers:}"
            print >>f, r'\begin{enumerate}'
            for e in self.results['errors']:
                print >>f, r'\item ' + e
        # finish latex
        print >>f, r"""
\end{enumerate}

\end{document}
"""
        f.close()
        os.system('pdflatex {}.tex'.format(name))
        os.system('pdflatex {}.tex'.format(name))
        os.unlink(name + '.log')
        os.unlink(name + '.aux')


def search(query, name='results', new=False, **options):
    """ Execute search. """
    wos = WebOfScience()
    import pickle
    try:
        if new:
            os.unlink(name + '.dat')
        with open(name + '.dat', 'r') as f:
            wos.results = pickle.load(f)
        wos.driver.quit()
    except:
        wos.search(query)
        wos.report()
        wos.papers()
        wos.finish()
        with open(name + '.dat', 'w') as f:
            pickle.dump(wos.results, f, protocol=-1)
    wos.latex(name, **options)


if __name__ == '__main__':
    search('AU=siudeja,b*', 'SiudejaB', new=False, full=True)
